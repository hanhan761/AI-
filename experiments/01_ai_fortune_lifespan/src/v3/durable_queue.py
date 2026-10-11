"""Restart-safe bounded queue for authorized pure-generation tasks.
Driver contract: factory() -> object with invoke(task, journal), optional reconcile(task,journal).
Only a verified, validated response may return a string. Drivers raise Failure with a category.
"""
import argparse,concurrent.futures,contextlib,hashlib,importlib,json,os,random,sqlite3,time
from pathlib import Path
class Failure(Exception):
    def __init__(self,kind,raw=None,retry_after=0):
        if kind not in ('transient','limited','ambiguous','invalid','fatal'):raise ValueError('bad failure category')
        super().__init__(kind);self.kind=kind;self.raw=raw;self.retry_after=retry_after
@contextlib.contextmanager
def run_lock(path):
    # Kernel lock survives neither process death nor reboot; file existence is not ownership.
    f=open(path,'a+b');f.seek(0);f.write(b'0');f.flush();f.seek(0)
    try:
        if os.name=='nt':
            import msvcrt;msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl;fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:f.close()
def atomic(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8');os.replace(tmp,path)
class Queue:
    def __init__(self,root,tasks,driver,workers=10,max_attempts=5,replay_ambiguous=False,clock=time.time,base_delay=5,max_delay=1800):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.clock=clock;self.driver=driver
        self.fatal=False;self.workers=workers;self.target=workers;self.max_attempts=max_attempts;self.replay=replay_ambiguous;self.base_delay=base_delay;self.max_delay=max_delay
        if workers<1 or max_attempts<1 or base_delay<0 or max_delay<base_delay:raise ValueError('invalid bounds')
        self.db=sqlite3.connect(self.root/'queue.sqlite3');self.db.row_factory=sqlite3.Row
        self.db.execute('pragma journal_mode=WAL');self.db.execute('pragma synchronous=FULL')
        self.db.executescript('create table if not exists meta(key text primary key,value text); create table if not exists tasks(id text primary key,payload text,status text,attempts integer,due real,raw text); create table if not exists attempts(task_id text,n integer,state text,raw text,journal text,started real,finished real,primary key(task_id,n)); create table if not exists health(model text primary key,failures integer,until real);')
        payload=json.dumps(tasks,sort_keys=True,ensure_ascii=False,separators=(',',':'));digest=hashlib.sha256(payload.encode()).hexdigest()
        ids=[t['id'] for t in tasks]
        if len(set(ids))!=len(ids):raise ValueError('duplicate task IDs')
        for t in tasks:
            if any(d not in ids for d in t.get('depends_on',[])):raise ValueError('unknown dependency')
        old=self.db.execute("select value from meta where key='input_hash'").fetchone()
        if old and old[0]!=digest:raise ValueError('frozen input changed')
        policy=json.dumps({'max_attempts':max_attempts,'replay_ambiguous':replay_ambiguous},sort_keys=True)
        old_policy=self.db.execute("select value from meta where key='policy'").fetchone()
        if old_policy and old_policy[0]!=policy:raise ValueError('retry policy changed; use a new audited queue')
        with self.db:
            self.db.execute("insert or ignore into meta values('input_hash',?)",(digest,));self.db.execute("insert or ignore into meta values('policy',?)",(policy,))
            self.db.executemany('insert or ignore into tasks values(?,?,?,0,0,null)',[(t['id'],json.dumps(t,ensure_ascii=False),'pending') for t in tasks])
    def _finish(self,row,result):
        ok,kind,raw,journal,after=result;attempt=row['attempts'];now=self.clock()
        if ok:state='done';due=0
        elif kind=='fatal':state='failed';due=0;self.fatal=True
        elif kind=='ambiguous' and not self.replay:state='uncertain';due=0
        elif attempt>=self.max_attempts:state='exhausted';due=0
        else:
            state='retry';due=now+max(after,min(self.max_delay,self.base_delay*2**min(attempt-1,20))*random.uniform(.75,1.25))
        model=json.loads(row['payload']).get('model','default')
        h=self.db.execute('select failures,until from health where model=?',(model,)).fetchone();failures,until=tuple(h) if h else (0,0)
        if ok:failures=0;until=0
        elif kind in ('transient','ambiguous','limited'):
            failures+=1
            if failures>=3 or kind=='limited':until=max(until,now+max(after,min(self.max_delay,max(1,self.base_delay)*2**min(failures,10))))
        if kind=='limited':self.target=max(1,self.target//2)
        with self.db:
            self.db.execute('update tasks set status=?,due=?,raw=? where id=?',(state,due,raw if ok else None,row['id']))
            self.db.execute('update attempts set state=?,raw=?,journal=?,finished=? where task_id=? and n=?',(kind if not ok else 'done',raw,json.dumps(journal,ensure_ascii=False),now,row['id'],attempt))
            self.db.execute('insert or replace into health values(?,?,?)',(model,failures,until))
    def _work(self,row):
        task=json.loads(row['payload']);jp=self.root/'journals'/hashlib.sha256(row['id'].encode()).hexdigest();jp.mkdir(parents=True,exist_ok=True);path=jp/(str(row['attempts'])+'.json');journal={}
        def save(update):journal.update(update);atomic(path,journal)
        try:
            raw=self.driver.invoke(task,save)
            if not isinstance(raw,str) or not raw.strip():raise Failure('invalid',raw=raw if isinstance(raw,str) else None)
            return True,'done',raw,journal,0
        except Failure as e:return False,e.kind,e.raw,journal,e.retry_after
        except Exception:
            # A driver programming error is not evidence that an upstream retry is safe.
            return False,'fatal',None,journal,0
    def _recover(self):
        for row in self.db.execute("select * from tasks where status='running'").fetchall():
            path=self.root/'journals'/hashlib.sha256(row['id'].encode()).hexdigest()/(str(row['attempts'])+'.json')
            journal=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
            raw=None
            if hasattr(self.driver,'reconcile'):
                try:raw=self.driver.reconcile(json.loads(row['payload']),journal)
                except Exception:pass
            result=(True,'done',raw,journal,0) if isinstance(raw,str) and raw.strip() else (False,'ambiguous',None,journal,0)
            self._finish(row,result)
    def counts(self):return dict(self.db.execute('select status,count(*) from tasks group by status'))
    def run(self,max_seconds=86400):
        deadline=self.clock()+max_seconds
        with run_lock(self.root/'run.lock'):
            self._recover();inflight={};stopping=False
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
                while True:
                    stopping=stopping or self.fatal or (self.root/'STOP_REQUESTED').exists() or self.clock()>=deadline
                    states={r['id']:r['status'] for r in self.db.execute('select id,status from tasks')}
                    rows=self.db.execute("select * from tasks where status in ('pending','retry') order by due,id").fetchall()
                    for row in rows:
                        if stopping or len(inflight)>=self.target:break
                        task=json.loads(row['payload']);deps=task.get('depends_on',[])
                        if any(states[d] in ('failed','exhausted','uncertain','blocked') for d in deps):
                            with self.db:self.db.execute("update tasks set status='blocked' where id=?",(row['id'],))
                            continue
                        if any(states[d]!='done' for d in deps) or row['due']>self.clock():continue
                        model=task.get('model','default');h=self.db.execute('select until from health where model=?',(model,)).fetchone()
                        if h and h[0]>self.clock():continue
                        # Half-open one call per blocked model until success resets its circuit.
                        if h and h[0]>0 and any(json.loads(r['payload']).get('model','default')==model for r in inflight.values()):continue
                        with self.db:
                            self.db.execute("update tasks set status='running',attempts=attempts+1 where id=?",(row['id'],))
                            self.db.execute("insert into attempts values(?,?, 'running',null,'{}',?,null)",(row['id'],row['attempts']+1,self.clock()))
                        claimed=dict(row);claimed['attempts']+=1;inflight[pool.submit(self._work,claimed)]=claimed
                    if inflight:
                        finished,_=concurrent.futures.wait(inflight,timeout=1,return_when=concurrent.futures.FIRST_COMPLETED)
                        for f in finished:self._finish(inflight.pop(f),f.result())
                    counts=self.counts();atomic(self.root/'progress.json',{'counts':counts,'workers':self.target,'complete':counts.get('done',0)==len(states),'updated':self.clock()})
                    if not inflight:
                        if stopping:return 0 if counts.get('done',0)==len(states) else 2
                        if not any(counts.get(s,0) for s in ('pending','retry')):return 0 if counts.get('done',0)==len(states) else 3
                        # Cyclic or otherwise impossible dependencies are terminal, not endless polling.
                        states={r['id']:r['status'] for r in self.db.execute('select id,status from tasks')}
                        remaining=self.db.execute("select * from tasks where status in ('pending','retry')").fetchall()
                        if not any(all(states[d]=='done' for d in json.loads(r['payload']).get('depends_on',[])) for r in remaining):
                            with self.db:self.db.execute("update tasks set status='blocked' where status in ('pending','retry')")
                            continue
                        time.sleep(.1 if self.base_delay==0 else 1)
    def close(self):self.db.close()
def main():
    p=argparse.ArgumentParser();p.add_argument('--tasks',type=Path,required=True);p.add_argument('--run-dir',type=Path,required=True);p.add_argument('--driver',required=True,help='module:factory');p.add_argument('--workers',type=int,default=10);p.add_argument('--max-attempts',type=int,default=5);p.add_argument('--max-seconds',type=int,default=86400);p.add_argument('--replay-ambiguous-pure-generation',action='store_true');a=p.parse_args()
    module,factory=a.driver.split(':');driver=getattr(importlib.import_module(module),factory)()
    tasks=json.loads(a.tasks.read_text(encoding='utf8'));q=Queue(a.run_dir,tasks,driver,a.workers,a.max_attempts,a.replay_ambiguous_pure_generation)
    try:return q.run(a.max_seconds)
    finally:q.close()
if __name__=='__main__':raise SystemExit(main())

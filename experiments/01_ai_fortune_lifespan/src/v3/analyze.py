import json,sqlite3,collections,statistics,hashlib,time,sys
from pathlib import Path
from prompt import parse
from research_stats import avg,VALUE,concordance,paired,association_permutation,holm,mean_ci
R=Path(__file__).resolve().parents[2]
def read(f):return json.loads((R/f).read_text(encoding='utf8'))
def write(f,o):
 p=R/f;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf8');tmp.replace(p)
def main(final=False):
 P=read('config/v3/protocol.json');I=read('data/v3/inventory.json');G=read('data/v3/gold.private.json');gd={g['id']:g for g in G};E=[g for g in G if g['split']=='evaluation']
 db=R/'runs/v3/queue/queue.sqlite3';answers=[];counts={};first=collections.Counter();by_model=collections.defaultdict(collections.Counter)
 if db.exists():
  c=sqlite3.connect('file:'+db.as_posix()+'?mode=ro',uri=True);counts=dict(c.execute('select status,count(*) from tasks group by status'))
  for payload,state,n in c.execute("select payload,status,attempts from tasks where status!='pending'"):
   t=json.loads(payload);by_model[t['model']][state]+=1
  for payload,state,raw,n in c.execute('select t.payload,a.state,a.raw,a.n from tasks t join attempts a on t.id=a.task_id where a.n=1'):
   t=json.loads(payload);first[state]+=1
   if state!='done' or not raw:continue
   try:o=parse(raw)
   except (ValueError,KeyError):continue
   g=gd[t['case_id']];tendency=o['longevity']['tendency'];identity=o['identity_recognized']
   answers.append({**{k:t[k] for k in ('id','model','arm','case_id','repeat')},'rating':g['rating'],'tendency':tendency,'value':None if identity else VALUE.get(tendency),'identity':identity,'age':g['death_age'],'stratum':[g['sex'],int(g['birth'][:4])//50],'boundary':g['time_boundary_5min'],'external_death':any(code in ('Death by Accident','Death by Homicide','Death by Execution','Death by Suicide','Death by War') for code in g['death_codes'])})
  c.close()
 admission=read('runs/v3/admission.json') if (R/'runs/v3/admission.json').exists() else None
 progress=read('runs/v3/queue/progress.json') if (R/'runs/v3/queue/progress.json').exists() else {'phase':'not_started','counts':counts}
 terminal=not any(counts.get(s,0) for s in ('pending','retry','running')) and bool(counts)
 result={'updated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'inventory':I,'protocol':P,'progress':progress,'counts':counts,'first_attempts':dict(first),'by_model':dict(by_model),'admission':admission,'execution_terminal':terminal,'final_inference':bool(final and terminal),'aggregates':[],'paired':[],'associations':[],'process':[],'warning':'运行中只显示数据建设和执行进度，避免把前几个回答当大样本结论。'}
 result['calibration_baseline']={'n_people':sum(g['split']=='calibration' for g in G),'method':'Training-only means for sex and 50-year birth cohort, smoothing by overall calibration mean; within these same strata baseline is constant, yielding tied concordance 0.5.'}
 calibration_groups=collections.defaultdict(list)
 for g in G:
  if g['split']=='calibration':calibration_groups[(g['sex'],int(g['birth'][:4])//50)].append(g['death_age'])
 result['calibration_baseline']['stratum_means']={str(k):avg(v) for k,v in calibration_groups.items()}
 result['cohort']={'birth_century':dict(collections.Counter(str(int(g['birth'][:4])//100+1)+'世纪' for g in E)),'sex':dict(collections.Counter('男' if g['sex'] else '女' for g in E)),'age_bins':dict(collections.Counter(g['death_label'] for g in E)),'country_top10':collections.Counter(g['country'] for g in E).most_common(10),'source_rating_note':'AA/A为Astrodatabank的资料评级，未逐份独立验出生证；首字母C样本且已故人物，不能代表一般人口。'}
 def records(rows):
  by=collections.defaultdict(list)
  for r in rows:
   if r['value'] is not None:by[r['case_id']].append(r)
  return [{'id':pid,'value':avg([r['value'] for r in rr]),'age':rr[0]['age'],'stratum':rr[0]['stratum'],'repeats':len(rr),'sd':statistics.stdev([r['value'] for r in rr]) if len(rr)>1 else None} for pid,rr in by.items()]
 if final and terminal:
  result['warning']='统计仅适用于本资料集和冻结规则。尚未独立校准自动评委；无姓名输入不能排除命盘记忆。'
  for pop in ('AA','all','AA_no_boundary','AA_non_external'):
   eligible=[g for g in E if (pop=='all' or g['rating']=='AA') and (pop!='AA_no_boundary' or not g['time_boundary_5min']) and (pop!='AA_non_external' or not any(code in ('Death by Accident','Death by Homicide','Death by Execution','Death by Suicide','Death by War') for code in g['death_codes']))]
   ids={g['id'] for g in eligible}
   for model in P['models']:
    lookup={}
    for arm in P['arms']:
     rows=[r for r in answers if r['model']==model and r['arm']==arm and r['case_id'] in ids];rr=records(rows);lookup[arm]=rr
     s=concordance(rr);s.pop('influence',None);result['aggregates'].append({'population':pop,'model':model,'arm':arm,**s,'planned_people':len(ids),'n_answers_valid':len(rows),'n_answers_covered':sum(r['value'] is not None for r in rows),'coverage':sum(r['value'] is not None for r in rows)/(len(ids)*P['repeats']) if ids else None,'repeat_sd_mean':avg([r['sd'] for r in rr if r['sd'] is not None]),'n_people_repeated':sum(r['sd'] is not None for r in rr),'tendencies':dict(collections.Counter(r['tendency'] for r in rows))})
    result['paired'].append({'population':pop,'model':model,**paired(lookup['true_chart'],lookup['shuffled_chart'])})
    if pop=='AA':result['associations'].append({'model':model,**(association_permutation(lookup['true_chart']) or {'p':None,'residual_r':None})})
  corrected=holm({a['model']:a.get('p') for a in result['associations']})
  for a in result['associations']:a['p_holm']=corrected[a['model']]
 judge_db=R/'runs/v3/judges/queue.sqlite3'
 if judge_db.exists():
  c=sqlite3.connect('file:'+judge_db.as_posix()+'?mode=ro',uri=True);result['judge_counts']=dict(c.execute('select status,count(*) from tasks group by status'));votes=[]
  for payload,raw in c.execute("select payload,raw from tasks where status='done'"):
   t=json.loads(payload);o=parse(raw);votes.append({'answer_model':t['answer_model'],'judge':t['model'],'case_id':t['case_id'],'repeat':t['repeat'],'scores':o['scores']})
  c.close()
  for am in P['models']:
   for jm in ('qwen3.8-max','DeepSeek-V3-2'):
    for dim in ('F1','F2','F3','F4','F5','F6'):
     grouped=collections.defaultdict(list)
     for v in votes:
      if v['answer_model']==am and v['judge']==jm:grouped[v['case_id']].append(v['scores'][dim])
     vals=[avg(v) for v in grouped.values()];result['process'].append({'model':am,'judge':jm,'dimension':dim,'mean':avg(vals),'ci':mean_ci(vals),'n_people':len(vals),'n_votes':sum(len(v) for v in grouped.values()),'self_review':am==jm})
  result['judge_limit']='评委盲于回答型号、姓名、生平和客观结果。两位评委分别显示，不能视作人工金标准；同型号自评标记。'
 write('reports/v3/results.aggregate.json',result)
 template=(R/'src/v3/report_template.html').read_text(encoding='utf8');embedded=json.dumps(result,ensure_ascii=False).replace('<','\\u003c')
 out=R/'reports/AI命理_大样本研究汇报_20261006.html';tmp=out.with_suffix('.tmp');tmp.write_text(template.replace('__DATA__',embedded),encoding='utf8');tmp.replace(out)
 print(json.dumps({'terminal':terminal,'inference':result['final_inference'],'counts':counts,'first_attempt':dict(first),'report':out.name},ensure_ascii=True))
if __name__=='__main__':main('--final' in sys.argv)

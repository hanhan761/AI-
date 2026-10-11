import json,hashlib,collections,datetime as dt
from pathlib import Path
R=Path(__file__).resolve().parents[2]
P=json.loads((R/'config/v3/protocol.json').read_text(encoding='utf8'));G=json.loads((R/'data/v3/gold.private.json').read_text(encoding='utf8'));M=json.loads((R/'data/v3/shuffle.private.json').read_text(encoding='utf8'))
E=sorted([g for g in G if g['split']=='evaluation'],key=lambda g:hashlib.sha256(('order:'+g['id']).encode()).hexdigest());tasks=[]
for rep in range(1,4):
 for g in E:
  for arm in P['arms']:
   for model in P['models']:
    tasks.append({'id':str(len(tasks)).zfill(7)+'-'+hashlib.sha256(('v3'+g['id']+arm+model+str(rep)).encode()).hexdigest()[:12],'model':model,'arm':arm,'case_id':g['id'],'chart_id':g['id'] if arm=='true_chart' else M[g['id']],'repeat':rep})
(R/'runs/v3').mkdir(parents=True,exist_ok=True)
for f,o in [('runs/v3/tasks.json',tasks),('runs/v3/gate_tasks.json',tasks[:3*2*len(P['models'])])]: (R/f).write_text(json.dumps(o,ensure_ascii=False),encoding='utf8')
print(json.dumps({'tasks':len(tasks)}))

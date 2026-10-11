import json,sqlite3,hashlib,re
from pathlib import Path
from prompt import CHARTS,selected_rules,parse,PROTOCOL
R=Path(__file__).resolve().parents[2]
G=json.loads((R/'data/v3/gold.private.json').read_text(encoding='utf8'));cases=sorted([g for g in G if g['split']=='evaluation' and g['rating']=='AA'],key=lambda g:hashlib.sha256(('review:'+g['id']).encode()).hexdigest())[:32];ids={g['id'] for g in cases};rubric=json.loads((R/'config/v3/rubric.json').read_text(encoding='utf8'))
c=sqlite3.connect('file:'+(R/'runs/v3/queue/queue.sqlite3').as_posix()+'?mode=ro',uri=True);tasks=[];skipped=[]
for payload,raw in c.execute("select t.payload,a.raw from tasks t join attempts a on t.id=a.task_id where a.n=1 and a.state='done'"):
 t=json.loads(payload)
 if t['case_id'] not in ids or t['arm']!='true_chart':continue
 o=parse(raw)
 # Do not pass recognized names to another model; preserve the original in the answering ledger.
 if o['identity_recognized'] or any(g['name'].casefold() in raw.casefold() for g in G if len(g['name'])>=6):skipped.append(t['id']);continue
 chart=CHARTS[t['chart_id']];rules=selected_rules(chart)
 prompt='你是匿名理论推导审查员。只核对命盘、给定规则和回答，不识别身份，不猜回答型号，不看生平或客观成绩。按量表F1-F6逐维给0至4整数；每维给一句具体证据。观点不同不能替代必要条件审查；引用存在不等于规则成立。正确承认不足不扣预测分；本任务只判断定性寿夭倾向，不能擅自要求年龄概率。只返回JSON，结构为scores包含F1到F6，evidence包含对应六个非空字符串。\n量表：'+json.dumps(rubric['dimensions'],ensure_ascii=False)+'\n匿名命盘：'+json.dumps(chart,ensure_ascii=False)+'\n固定规则：'+json.dumps([{k:r[k] for k in ('id','source','text')} for r in rules],ensure_ascii=False)+'\n待审回答：'+raw
 for jm in rubric['judge']['models']:tasks.append({'id':'judge-'+hashlib.sha256((t['id']+jm).encode()).hexdigest()[:24],'model':jm,'kind':'judge','case_id':t['case_id'],'repeat':t['repeat'],'answer_id':t['id'],'answer_model':t['model'],'prompt':prompt})
c.close();p=R/'runs/v3/judge_tasks.json';p.write_text(json.dumps(tasks,ensure_ascii=False),encoding='utf8');(R/'runs/v3/judge_manifest.json').write_text(json.dumps({'hash':hashlib.sha256(p.read_bytes()).hexdigest(),'planned_people':len(ids),'sample_ids':sorted(ids),'tasks':len(tasks),'identity_skipped_answers':skipped}),encoding='utf8')
print(json.dumps({'judge_tasks':len(tasks),'prespecified_people':32,'identity_skipped':len(skipped)}))

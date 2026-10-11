import sys,json,sqlite3,collections,statistics,hashlib,time,os,argparse
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'src/v3'))
from prompt import parse,validate
from research_stats import avg,VALUE,concordance,paired,association_permutation,holm
ap=argparse.ArgumentParser(description='Original supplemental analysis; requires authorized private cohort and completed ledgers.')
ap.add_argument('--ledgers',type=Path,nargs='+',required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
OUT=args.out;OUT.mkdir(parents=True,exist_ok=True)
MODELS=json.loads((BASE/'data/supplemental.aggregate.json').read_text(encoding='utf8'))['models']
PATHS=[p.resolve().as_posix() for p in args.ledgers]
G=json.loads((BASE/'data/v3/gold.private.json').read_text(encoding='utf8'));gd={g['id']:g for g in G};E=[g for g in G if g['split']=='evaluation']
answers=[];seen=set();sources=[]
for path in PATHS:
 c=sqlite3.connect('file:'+path+'?mode=ro',uri=True);n=0
 for tid,payload,raw in c.execute("select id,payload,raw from tasks where status='done'"):
  t=json.loads(payload)
  if t.get('kind')=='judge' or t['model'] not in MODELS:continue
  assert tid not in seen,tid;seen.add(tid);o=parse(raw);validate(o,t);g=gd[t['case_id']];v=o['longevity']['tendency']
  answers.append({**{k:t[k] for k in ('id','model','arm','case_id','repeat')},'rating':g['rating'],'tendency':v,'value':None if o['identity_recognized'] else VALUE.get(v),'identity':o['identity_recognized'],'age':g['death_age'],'stratum':[g['sex'],int(g['birth'][:4])//50],'boundary':g['time_boundary_5min'],'external':any(x in ('Death by Accident','Death by Homicide','Death by Execution','Death by Suicide','Death by War') for x in g['death_codes'])});n+=1
 c.close();sources.append({'batch':len(sources)+1,'valid_unique':n})
assert len(answers)==154080
result={'analysis':'supplemental_first_valid_across_all_attempts','primary_unchanged':True,'created_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'models':MODELS,'n_people':1712,'valid_answers':len(answers),'source_ledgers':sources,'aggregates':[],'paired':[],'associations':[],'limitations':['Selected 15 models by operational availability, not outcome','Not the preregistered original first-attempt primary analysis','Structurally valid answers may abstain or identify; neither enters numerical prediction','C-initial deceased-public-figure convenience cohort','AA/A are publisher source ratings; not independent certificate verification','Person-cluster stratified influence bootstrap 2000, linearization approximation']}
def records(rows):
 grouped=collections.defaultdict(list)
 for r in rows:
  if r['value'] is not None:grouped[r['case_id']].append(r)
 return [{'id':pid,'value':avg([r['value'] for r in rr]),'age':rr[0]['age'],'stratum':rr[0]['stratum'],'repeats':len(rr),'sd':statistics.stdev([r['value'] for r in rr]) if len(rr)>1 else None} for pid,rr in grouped.items()]
for pop in ('AA','all','AA_no_boundary','AA_non_external'):
 for model in MODELS:
  lookup={};elig=[g for g in E if (pop=='all' or g['rating']=='AA') and (pop!='AA_no_boundary' or not g['time_boundary_5min']) and (pop!='AA_non_external' or not any(x in ('Death by Accident','Death by Homicide','Death by Execution','Death by Suicide','Death by War') for x in g['death_codes']))];ids={g['id'] for g in elig}
  for arm in ('true_chart','shuffled_chart'):
   rows=[r for r in answers if r['model']==model and r['arm']==arm and r['case_id'] in ids];rr=records(rows);lookup[arm]=rr;s=concordance(rr);s.pop('influence',None)
   result['aggregates'].append({'population':pop,'model':model,'arm':arm,**s,'planned_people':len(ids),'valid_answers':len(rows),'covered_answers':sum(r['value'] is not None for r in rows),'coverage':sum(r['value'] is not None for r in rows)/(len(ids)*3),'repeat_sd_mean':avg([r['sd'] for r in rr if r['sd'] is not None]),'n_people_repeated':sum(r['sd'] is not None for r in rr),'tendencies':dict(collections.Counter(r['tendency'] for r in rows))})
  result['paired'].append({'population':pop,'model':model,**paired(lookup['true_chart'],lookup['shuffled_chart'])})
  if pop=='AA':result['associations'].append({'model':model,**association_permutation(lookup['true_chart'])})
  print(json.dumps({'population':pop,'model':model,'complete':True}),flush=True)
pvals={a['model']:a['p'] for a in result['associations']};pvals.update({m:None for m in json.loads((BASE/'config/v3/protocol.json').read_text(encoding='utf8'))['models'] if m not in pvals});adjusted=holm(pvals)
for a in result['associations']:a['p_holm_18']=adjusted[a['model']]
result['multiplicity']='Holm over original 18-model family; missing 3 treated as p=1 for adjustment only'
(OUT/'supplemental.aggregate.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({'complete':True,'valid_answers':len(answers)}))

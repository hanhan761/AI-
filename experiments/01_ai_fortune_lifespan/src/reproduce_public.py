"""Offline verification and plotting from public aggregate data; no model calls."""
import csv,json,math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
R=Path(__file__).resolve().parents[1]
D=json.loads((R/'data/supplemental.aggregate.json').read_text(encoding='utf8'))
P=json.loads((R/'data/primary.aggregate.json').read_text(encoding='utf8'))
assert D['n_people']==1712 and len(D['models'])==15 and D['valid_answers']==154080
assert sum(r['valid_answers'] for r in D['aggregates'] if r['population']=='all')==154080
A={r['model']:r for r in D['aggregates'] if r['population']=='AA' and r['arm']=='true_chart'}
B={r['model']:r for r in D['paired'] if r['population']=='AA'}
assert all(r['planned_people']==1501 for r in A.values())
assert all(r['ci'][0]<0<r['ci'][1] for r in B.values())
assert all(0<=r['coverage']<=1 and r['covered_answers']<=r['valid_answers'] for r in D['aggregates'])
assert len({r['model'] for r in P['aggregates']})==18
rows=[]
for m in D['models']:
 a,b=A[m],B[m]
 rows.append({'model':m,'concordance_percent':a['mean']*100,'concordance_ci_low':a['ci'][0]*100,'concordance_ci_high':a['ci'][1]*100,'paired_difference_pp':b['mean']*100,'paired_ci_low':b['ci'][0]*100,'paired_ci_high':b['ci'][1]*100,'prediction_coverage_percent':a['coverage']*100,'paired_people':b['n_people']})
with (R/'data/model_results.csv').open(encoding='utf-8-sig') as f:original=list(csv.DictReader(f))
assert len(original)==len(rows)
for old,new in zip(original,rows):
 for k,v in new.items():assert old[k]==v if isinstance(v,str) else math.isclose(float(old[k]),v,rel_tol=1e-12,abs_tol=1e-12),(new['model'],k)
with (R/'data/reproduced_model_results.csv').open('w',newline='',encoding='utf-8-sig') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
fig,axs=plt.subplots(1,2,figsize=(15,9),layout='constrained')
for ax,key,base,title in [(axs[0],A,50,'True chart: lifespan concordance (%)'),(axs[1],B,0,'True minus shuffled (percentage points)')]:
 vals=[key[m] for m in D['models']]
 ax.errorbar([x['mean']*100 for x in vals],range(15),xerr=[[(x['mean']-x['ci'][0])*100 for x in vals],[(x['ci'][1]-x['mean'])*100 for x in vals]],fmt='o',color='#152D27',capsize=4)
 ax.axvline(base,color='#EA815E',ls='--');ax.set_yticks(range(15),D['models']);ax.invert_yaxis();ax.set_title(title);ax.grid(axis='x',alpha=.2)
fig.suptitle('15 available models | AA cohort n=1501 | person-cluster 95% CI')
fig.savefig(R/'figures/reproduced_results.png',dpi=160);plt.close(fig)
print(json.dumps({'verification':'passed','models':len(rows),'people':1712,'valid_answers':154080,'AA_concordance_range_percent':[min(x['mean']*100 for x in A.values()),max(x['mean']*100 for x in A.values())],'all_AA_paired_intervals_cross_zero':True,'scope':'aggregate replot; individual-level CI cannot be recomputed without private records'},indent=2))

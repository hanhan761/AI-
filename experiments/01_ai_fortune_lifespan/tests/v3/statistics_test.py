import sys
from pathlib import Path
R=Path(__file__).resolve().parents[2];sys.path.insert(0,str(R/'src/v3'))
from research_stats import concordance,paired,holm,association_permutation
x=[{'id':str(i),'value':i,'age':40+i,'stratum':[1,38]} for i in range(25)]
y=[{**r,'value':-r['value']} for r in x];z=[{**r,'value':0} for r in x]
assert concordance(x)['mean']==1 and concordance(y)['mean']==0 and concordance(z)['mean']==.5
assert concordance(x)['ci']==[1,1] and paired(x,y)['mean']==1
assert paired(x,x)['ci']==[0,0]
assert association_permutation(z)['p'] is None
assert holm({'a':.01,'b':.04,'c':None})=={'a':.03,'b':.08,'c':None}
assert concordance([x[0]])['mean'] is None
assert concordance([{**r,'age':50} for r in x])['mean'] is None
print('PASS: ordinal concordance, tie credit, missing, paired clusters, Holm, constant-score test')

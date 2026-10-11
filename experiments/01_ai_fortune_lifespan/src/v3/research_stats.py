import random,math,collections,statistics
SEED=20261006
VALUE={'long':1,'short':-1,'balanced':0}
def avg(x):return sum(x)/len(x) if x else None
def concordance(records):
 # Pair kernel checks relative lifespan ordering, not invented absolute death ages.
 n=len(records);groups=collections.defaultdict(list);credits=[0.0]*n;partners=[0]*n;total=0;num=0
 for i,r in enumerate(records):groups[tuple(r['stratum'])].append(i)
 for ids in groups.values():
  for pos,i in enumerate(ids):
   for j in ids[pos+1:]:
    a=records[i]['age']-records[j]['age']
    if a==0:continue
    pred=records[i]['value']-records[j]['value'];v=.5 if abs(pred)<1e-12 else float(a*pred>0)
    credits[i]+=v;credits[j]+=v;partners[i]+=1;partners[j]+=1;num+=v;total+=1
 if not total:return {'mean':None,'n_people':n,'n_informative_people':0,'n_pairs':0,'ci':None,'influence':[]}
 u=num/total;influence=[n*(credits[i]-u*partners[i])/total for i in range(n)]
 # Strata sizes are conditioned on; remove each stratum's influence mean.
 for ids in groups.values():
  m=avg([influence[i] for i in ids])
  for i in ids:influence[i]-=m
 return {'mean':u,'n_people':n,'n_informative_people':sum(z>0 for z in partners),'n_pairs':total,'ci':influence_ci(u,influence,groups),'influence':influence}
def influence_ci(estimate,influence,groups,B=2000):
 if estimate is None or len(influence)<2:return None
 rng=random.Random(SEED);n=len(influence);boot=[]
 for _ in range(B):
  perturb=sum(sum(influence[rng.choice(ids)] for _ in ids) for ids in groups.values())/n
  boot.append(estimate+perturb)
 boot.sort();return [boot[int(.025*(B-1))],boot[int(.975*(B-1))]]
def paired(real,wrong):
 a={r['id']:r for r in real};b={r['id']:r for r in wrong};ids=sorted(a.keys()&b.keys());x=[a[i] for i in ids];y=[b[i] for i in ids]
 u,v=concordance(x),concordance(y)
 if u['mean'] is None:return {'mean':None,'ci':None,'n_people':len(ids),'n_pairs':0}
 groups=collections.defaultdict(list)
 for i,r in enumerate(x):groups[tuple(r['stratum'])].append(i)
 gain=u['mean']-v['mean'];psi=[aa-bb for aa,bb in zip(u['influence'],v['influence'])]
 return {'mean':gain,'ci':influence_ci(gain,psi,groups),'n_people':len(ids),'n_pairs':u['n_pairs']}
def association_permutation(records,B=2000):
 if len(records)<20:return None
 groups=collections.defaultdict(list)
 for i,r in enumerate(records):groups[tuple(r['stratum'])].append(i)
 xv=[];yv=[]
 for r in records:xv.append(r['value']);yv.append(r['age'])
 for ids in groups.values():
  xm=avg([xv[i] for i in ids]);ym=avg([yv[i] for i in ids])
  for i in ids:xv[i]-=xm;yv[i]-=ym
 denom=math.sqrt(sum(v*v for v in xv)*sum(v*v for v in yv))
 if denom<1e-12:return {'residual_r':None,'p':None,'reason':'constant score within cohorts; no ordering information'}
 observed=sum(a*b for a,b in zip(xv,yv));rng=random.Random(SEED);count=0
 for _ in range(B):
  score=0
  for ids in groups.values():
   shuffled=[yv[i] for i in ids];rng.shuffle(shuffled);score+=sum(xv[i]*v for i,v in zip(ids,shuffled))
  if score>=observed-1e-12:count+=1
 return {'residual_r':observed/denom,'p':(count+1)/(B+1),'permutations':B,'note':'within-sex/birth-cohort permutation tests positive residual covariance; this p-value does not directly test the concordance gap'}
def holm(pvalues):
 ordered=sorted((p if p is not None else 1,k) for k,p in pvalues.items());out={};last=0;m=len(ordered)
 for i,(p,k) in enumerate(ordered):last=max(last,min(1,(m-i)*p));out[k]=last if pvalues[k] is not None else None
 return out
def mean_ci(values):
 if len(values)<2:return None
 rng=random.Random(SEED);n=len(values);b=sorted(sum(rng.choice(values) for _ in values)/n for _ in range(2000));return [b[49],b[1949]]

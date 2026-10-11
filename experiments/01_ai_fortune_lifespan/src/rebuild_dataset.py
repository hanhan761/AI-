import json,datetime as dt,hashlib,re,collections,random,xml.etree.ElementTree as E,argparse
from pathlib import Path
from lunar_python import Solar
R=Path(__file__).resolve().parents[1];D=R/'data/v3';D.mkdir(parents=True,exist_ok=True)
ap=argparse.ArgumentParser(description='Rebuild private v3 cohort from a locally authorized Astrodatabank export.')
ap.add_argument('--xml',type=Path,required=True);a=ap.parse_args();x=E.parse(a.xml).getroot()
def write(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding='utf8')
reason=collections.Counter();ratings=collections.Counter();gold=[];eventcount=0;deathcodes=collections.Counter()
def jdn(y,m,d,julian=False):
 a=(14-m)//12;y+=4800-a;m+=12*a-3
 return d+(153*m+2)//5+365*y+y//4+(-32083 if julian else -y//100+y//400-32045)
def getdate(el):
 if el is None:return None
 try:
  y,m,d=(int(el.get(k)) for k in ('iyear','imonth','iday'))
  if y<1600 or m<1 or d<1:return None
  date=dt.date(y,m,d)
  if el.get('ccalendar')=='j':date=dt.date(1970,1,1)+dt.timedelta(days=jdn(y,m,d,True)-2440588)
  elif el.get('ccalendar')!='g':return None
  return date
 except (ValueError,TypeError,OverflowError):return None
def degree(s):
 m=re.fullmatch(r'(\d+)([ew])(\d+)(?:[\x27:](\d+))?',s.lower())
 if not m:raise ValueError('longitude')
 return (int(m[1])+int(m[3])/60+int(m[4] or 0)/3600)*(1 if m[2]=='e' else -1)
def utcday(jd):return dt.datetime(1970,1,1)+dt.timedelta(seconds=round((float(jd)-2440587.5)*86400))
def age(b,d):return d.year-b.year-((d.month,d.day)<(b.month,b.day))
def label(a):return 'under40' if a<40 else '40s' if a<50 else '50s' if a<60 else '60s' if a<70 else '70s' if a<80 else '80plus'
for e in x.findall('adb_entry'):
 p=e.find('public_data');rating=p.findtext('roddenrating');ratings[rating]+=1
 if p.find('datatype').get('sdatatype')!='Public Figure':reason['non_public_person']+=1;continue
 if rating not in ('AA','A'):reason['rating_not_A_AA']+=1;continue
 if p.find('gender').get('csex') not in ('m','f'):reason['unsupported_gender']+=1;continue
 b=p.find('bdata');birth=getdate(b.find('sbdate'))
 if birth is None or b.find('sbdate').get('ccalendar')!='g':reason['birth_calendar_or_date']+=1;continue
 if e.findall('.//bdata_alt'):reason['alternative_birth']+=1;continue
 try:
  ut=utcday(b.find('sbtime').get('jd_ut'));lon=degree(b.find('place').get('slong'))
  if abs((ut.date()-birth).days)>2:raise ValueError('jd mismatch')
 except (TypeError,ValueError,OverflowError):reason['invalid_birth_instant']+=1;continue
 deaths=[];events=[]
 for ev in e.findall('./research_data/events/event'):
  code=ev.get('sevcode','');date=getdate(ev.find('./event_data/sbdate'));eventcount+=1
  if date:events.append({'event_id':ev.get('evn_id'),'code':code,'date':date.isoformat(),'source':e.findtext('./text_data/adb_link')})
  if code=='Death, Cause unspecified' or code.startswith('Death by '):
   deathcodes[code]+=1
   if date:deaths.append((date,code))
 if not deaths:reason['no_full_death_date']+=1;continue
 if len(set(d for d,c in deaths))!=1:reason['conflicting_death_dates']+=1;continue
 death=deaths[0][0];da=age(birth,death)
 if not 0<=da<=120 or death>dt.date(2026,10,6):reason['implausible_death_age']+=1;continue
 mean=ut+dt.timedelta(minutes=lon*4)
 # Export JD is rounded at 0.0864 s precision; original birth clocks are minute resolution.
 mean=mean.replace(second=0,microsecond=0)+dt.timedelta(minutes=round(mean.second/60))
 # Recompute rounding before replacing seconds.
 precise=ut+dt.timedelta(minutes=lon*4);mean=precise.replace(second=0,microsecond=0)+dt.timedelta(minutes=round(precise.second/60))
 bj=ut+dt.timedelta(hours=8)
 def ec(t):
  q=Solar.fromYmdHms(t.year,t.month,t.day,t.hour,t.minute,t.second).getLunar().getEightChar();q.setSect(2);return q
 local,instant=ec(mean),ec(bj);sex=1 if p.find('gender').get('csex')=='m' else 0
 pillars=[instant.getYear(),instant.getMonth(),local.getDay(),local.getTime()]
 stems='甲乙丙丁戊己庚辛壬癸';elems=[0,0,1,1,2,2,3,3,4,4];dm=stems.index(local.getDayGan())
 def tg(st):
  k=stems.index(st);return {0:('比肩','劫财'),1:('食神','伤官'),2:('偏财','正财'),3:('七杀','正官'),4:('偏印','正印')}[(elems[k]-elems[dm])%5][0 if k%2==dm%2 else 1]
 hs=[instant.getYearHideGan(),instant.getMonthHideGan(),local.getDayHideGan(),local.getTimeHideGan()]
 chart={'sex':'男' if sex else '女','pillars':pillars,'hidden_stems':hs,'stem_ten_gods':[tg(z[0]) if i!=2 else '日主' for i,z in enumerate(pillars)],'hidden_ten_gods':[[tg(z) for z in a] for a in hs],'dayun':[{'start_age_nominal':z.getStartAge()-1,'end_age_nominal':z.getEndAge()-1,'pillar':z.getGanZhi()} for z in instant.getYun(sex,2).getDaYun(13) if z.getGanZhi()],'convention':'节令年/月由UTC+8出生瞬间确定；日/时用地方平太阳时，0点换日；分钟分辨率；大运年龄按库虚岁减1近似周岁，无流年。'}
 pid='P'+hashlib.sha256(('v2:'+e.get('adb_id')).encode()).hexdigest()[:12]
 split='calibration' if int(hashlib.sha256(('split:'+pid).encode()).hexdigest()[:8],16)%5==0 else 'evaluation'
 gold.append({'id':pid,'adb_id':e.get('adb_id'),'name':p.findtext('name'),'rating':rating,'birth':birth.isoformat(),'birth_time':b.findtext('sbtime'),'birth_utc':ut.isoformat(),'birth_mean_time':mean.isoformat(),'longitude':lon,'sex':sex,'country':b.findtext('country'),'source':e.findtext('./text_data/adb_link'),'collector':p.findtext('scollector'),'birth_source_type':p.find('datatype').get('sdatasource'),'death':death.isoformat(),'death_age':da,'death_label':label(da),'death_codes':list(set(c for d,c in deaths)),'split':split,'time_boundary_5min':min((mean.hour*60+mean.minute-60)%120,(60-mean.hour*60-mean.minute)%120)<=5,'chart':chart,'events':events})
assert len({g['adb_id'] for g in gold})==len(gold)
write(D/'gold.private.json',gold)
charts=[{'id':g['id'],'chart':g['chart']} for g in gold];write(D/'charts.anonymous.json',charts)
evalgold=[g for g in gold if g['split']=='evaluation'];groups=collections.defaultdict(list)
for g in evalgold:groups[(g['sex'],dt.date.fromisoformat(g['birth']).year//50)].append(g['id'])
# Merge singleton bins by sex before derangement; mapping does not include true event labels.
singles=[ids[0] for ids in groups.values() if len(ids)==1]
for key in list(groups):
 if len(groups[key])==1:del groups[key]
for sex in (0,1):
 ids=[i for i in singles if next(g['sex'] for g in evalgold if g['id']==i)==sex]
 if len(ids)==1:
  key=next(k for k in groups if k[0]==sex);groups[key]+=ids
 elif ids:groups[(sex,'singleton_pool')]=ids
rng=random.Random(20261006);mapping={}
for ids in groups.values():
 rng.shuffle(ids)
 for i,pid in enumerate(ids):mapping[pid]=ids[(i+1)%len(ids)]
assert len(mapping)==len(evalgold) and all(k!=v for k,v in mapping.items())
write(D/'shuffle.private.json',mapping)
write(D/'inventory.json',json.loads((R/'data/inventory.json').read_text(encoding='utf8')))
print(json.dumps({'eligible_people':len(gold),'evaluation_people':len(evalgold),'calibration_people':len(gold)-len(evalgold),'private_output':'data/v3 (gitignored)'},ensure_ascii=False))

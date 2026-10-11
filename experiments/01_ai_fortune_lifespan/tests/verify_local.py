import json,sys,re,collections
from pathlib import Path
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'src/v3'))
from prompt import render,selected_rules
G=json.loads((R/'data/v3/gold.private.json').read_text(encoding='utf8'));M=json.loads((R/'data/v3/shuffle.private.json').read_text(encoding='utf8'));by={g['id']:g for g in G}
assert len(G)==2173 and sum(g['split']=='evaluation' for g in G)==1712
assert set(M)==set(M.values()) and all(k!=v and by[k]['sex']==by[v]['sex'] for k,v in M.items())
assert sum(int(by[k]['birth'][:4])//50!=int(by[v]['birth'][:4])//50 for k,v in M.items())==4
for g in G:
 p=render({'chart_id':g['id']});assert g['name'] not in p and g['birth'] not in p
 assert not re.search(r'https?://|\b\d{4}-\d{2}-\d{2}\b|P[0-9a-f]{12}|adb_id|country|longitude',p)
 assert len(selected_rules(g['chart']))==6
 y,m,d=map(int,g['birth_mean_time'][:10].split('-'));a=(14-m)//12;yy=y+4800-a;mm=m+12*a-3;j=d+(153*mm+2)//5+365*yy+yy//4-yy//100+yy//400-32045;n=(j-2451551)%60
 assert g['chart']['pillars'][2]=='甲乙丙丁戊己庚辛壬癸'[n%10]+'子丑寅卯辰巳午未申酉戌亥'[n%12]
print('PASS: 2173 people, 1712 evaluation, anonymity, day pillars, shuffle and 4 disclosed cohort exceptions')

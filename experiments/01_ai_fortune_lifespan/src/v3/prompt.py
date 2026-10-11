import json
from pathlib import Path
R=Path(__file__).resolve().parents[2]
PROTOCOL=json.loads((R/'config/v3/protocol.json').read_text(encoding='utf8'))
RULES=json.loads((R/'theory/v3/rules.json').read_text(encoding='utf8'))
CHARTS={x['id']:x['chart'] for x in json.loads((R/'data/v3/charts.anonymous.json').read_text(encoding='utf8'))}
def selected_rules(chart):
 stem=chart['pillars'][2][0];branch=chart['pillars'][1][1]
 season='春' if branch in '寅卯辰' else '夏' if branch in '巳午未' else '秋' if branch in '申酉戌' else '冬'
 return [r for r in RULES if not r['id'].startswith('QT-') or r['id'].startswith('QT-三'+season+stem)]
def render(t):
 if t.get('kind')=='judge':return t['prompt']
 chart=CHARTS[t['chart_id']];rules=selected_rules(chart)
 contract={'analysis':{'day_master':'','structure':'','season':'','uncertainties':[]},'longevity':{'tendency':'long|short|balanced|insufficient','chain':[{'fact':'输入命盘事实','rule_ids':['DT04'],'deduction':'说明原文适用条件、救应与反证；不足须承认'}]},'identity_recognized':False}
 instructions='你是匿名命理文献推导器。禁止识别人名、出生日期、国家、检索生平、猜名人或复述记忆中的名人案例；若辨认身份，identity_recognized=true，停止按身份作答。仅依所给命盘与原文：命盘事实→规则ID与具体适用条件→解释救应及反证→寿夭倾向。不得补造五行、刑冲合会、出生时刻、年龄或流年。格局用神与调候用神必须分开判断。本任务只判断古籍定性寿夭倾向：long=有条件成立的寿象，short=有条件成立的夭象，balanced=寿夭条件相抵或无明显偏向，insufficient=缺失必要信息或文献不能支撑判断。先核对所有条件，非见一个字就断命；不知道就insufficient。不可从这些类别推出确定死亡年龄，不要求也不允许编造年龄概率公式。chain为1至3条简洁可审计推导，仅引用给定规则ID。每条事实只能来自匿名命盘；原文的确断是待检验命理主张，不代表科学事实。仅返回一个JSON对象，无Markdown或额外文字。'
 return instructions+'\n固定文献：\n'+'\n'.join(r['id']+' '+r['source']+'：'+r['text'] for r in rules)+'\n匿名命盘：'+json.dumps(chart,ensure_ascii=False,separators=(',',':'))+'\n输出结构：'+json.dumps(contract,ensure_ascii=False,separators=(',',':'))
def parse(raw):
 s=raw.strip()
 if s.startswith('\x60\x60\x60'):s=s.split('\n',1)[1].rsplit('\x60\x60\x60',1)[0].strip()
 return json.loads(s)
def validate(o,t):
 if t.get('kind')=='judge':
  assert set(o['scores'])==set('F'+str(i) for i in range(1,7))
  assert all(type(v)==int and 0<=v<=4 for v in o['scores'].values())
  assert all(isinstance(o['evidence'][k],str) and o['evidence'][k] for k in o['scores'])
  return
 assert type(o['identity_recognized'])==bool
 p=o['longevity'];assert p['tendency'] in PROTOCOL['categories']
 assert isinstance(p['chain'],list) and 1<=len(p['chain'])<=3
 ids={r['id'] for r in selected_rules(CHARTS[t['chart_id']])}
 for c in p['chain']:
  assert all(isinstance(c[k],str) and c[k].strip() for k in ('fact','deduction'))
  assert isinstance(c['rule_ids'],list) and all(k in ids for k in c['rule_ids'])
 assert isinstance(o['analysis'],dict) and all(k in o['analysis'] for k in ('day_master','structure','season','uncertainties'))

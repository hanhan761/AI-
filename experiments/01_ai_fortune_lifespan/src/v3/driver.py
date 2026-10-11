import sys,json,hashlib,threading,time,os
from pathlib import Path
from durable_queue import Failure
from prompt import render,parse,validate,PROTOCOL
R=Path(__file__).resolve().parents[2]
sys.path.insert(0,os.environ['BAZI_GATEWAY_DIR'])  # Authorized native gateway installed separately.
from remote_direct_gateway import RemoteDirectCaller
class BaziNativeCaller(RemoteDirectCaller):
 def preflight(self,model):
  # Exact frozen native-catalog whitelist, including the authorized Moonshot family.
  if model not in PROTOCOL['models'] or model not in self.routes or any(z in model.lower() for z in ('gpt','openai')):
   raise RuntimeError('Model is not in frozen authorized non-GPT catalog')
class Driver:
 def __init__(self):
  self.caller=BaziNativeCaller(R/'runs/v3/transport.jsonl');self.local=threading.local()
  original=self.caller.client.trace
  def trace(action,elapsed,status):
   original(action,elapsed,status)
   if hasattr(self.local,'stages'):self.local.stages.append({'action':action,'status':status})
  self.caller.client.trace=trace
 def invoke(self,t,journal):
  prompt=render(t);journal({'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'phase':'started','model':t['model']})
  self.local.stages=[];raw=None
  try:
   raw=self.caller([{'role':'user','content':prompt}],model=t['model'])
  except Exception as e:
   stages=self.local.stages;journal({'phase':'upstream_failure','stages':stages,'exception_type':type(e).__name__})
   codes={s['status'] for s in stages}
   if codes&{'HTTP_401','HTTP_403'}:raise Failure('fatal')
   if 'HTTP_429' in codes:raise Failure('limited',retry_after=60)
   # Nothing may be replayed after Chat without reliable completion evidence.
   if any(s['action']=='Chat' for s in stages):raise Failure('ambiguous')
   if type(e).__name__=='GatewayConfigurationError' or codes&{'HTTP_400','HTTP_404'}:raise Failure('fatal')
   raise Failure('transient')
  journal({'phase':'raw_saved','raw':raw,'raw_sha256':hashlib.sha256(raw.encode()).hexdigest(),'stages':self.local.stages})
  try:validate(parse(raw),t)
  except (ValueError,KeyError,TypeError,AssertionError,IndexError):
   journal({'phase':'invalid'});raise Failure('invalid',raw=raw)
  journal({'phase':'validated'});return raw
 def reconcile(self,t,journal):
  raw=journal.get('raw')
  if journal.get('phase') in ('raw_saved','validated') and raw:
   validate(parse(raw),t);return raw
  return None
def factory():return Driver()

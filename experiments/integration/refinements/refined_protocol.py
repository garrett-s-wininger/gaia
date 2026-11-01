"""Sequential request client with generation-tagged frontend facts events."""
import json,select,sys,time,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace'))
from protocol import Host as BaseHost,admit,require,sha

class Host(BaseHost):
 def __init__(self,path,work,refined=False):super().__init__(path,work);self.refined=refined;self.pending=bytearray()
 def request(self,value,on_facts=None):
  self.process.stdin.write(json.dumps(value)+'\n');self.process.stdin.flush();error=None
  deadline=time.monotonic()+120
  while True:
   while b'\n' not in self.pending:
    timeout=deadline-time.monotonic()
    if timeout<=0 or not select.select([self.process.stdout],[],[],timeout)[0]:raise TimeoutError('host/event response')
    chunk=os.read(self.process.stdout.fileno(),65536)
    if not chunk:raise RuntimeError('host closed before final response')
    self.pending.extend(chunk)
    if len(self.pending)>16*1024*1024:raise RuntimeError('host response bound')
   end=self.pending.index(b'\n');line=bytes(self.pending[:end]);del self.pending[:end+1];response=json.loads(line)
   if response.get('event')=='frontend_facts':
    try:
     if response['generation']!=value.get('generation') or response['target']!=value.get('target'):raise ValueError('stale/misrouted frontend facts')
     if on_facts:on_facts(response['facts'])
    except BaseException as e:error=e
    continue
   if error:raise error
   return response

def normalized(root,command,analysis):
 args=list(command);output=root/args[args.index('-o')+1];args[args.index('-o')+1]=str(output)
 if analysis:args[args.index('-MF')+1]+='.editor'
 return args,output

def request(host,root,command,target,generation,context='configuration-0',analysis=False,on_facts=None):
 args,output=normalized(root,command,analysis)
 value=dict(args=args,cwd=str(root),output=str(output),target=target,generation=generation,context=context,mode='observed',analysis='off',analysis_only=analysis,logical=True,store=True)
 if host.refined:value.update(family='fixed-sdk-and-environment-v1',emit_facts=on_facts is not None)
 return require(host.request(value,on_facts=on_facts))

def scan(host,targets,generation,context='configuration-0',commands=None,root=None,analysis=False):
 value=dict(scan=targets,generation=generation,context=context)
 if host.refined and commands is not None:value.update(family='fixed-sdk-and-environment-v1',commands={t:normalized(root,commands[t],analysis)[0] for t in targets},cwd=str(root),analysis_only=analysis)
 return require(host.request(value))

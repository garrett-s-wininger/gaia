"""Private Linux JSON-line compiler adapter. No public protocol is implied."""
import json,select,subprocess,time
from pathlib import Path

def sha(body):
 import hashlib
 return hashlib.sha256(body).hexdigest()

class Host:
 def __init__(self,path,work):
  work.mkdir(parents=True,exist_ok=True);self.log=(work/'stderr.txt').open('wb');self.process=subprocess.Popen([str(path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True);self.cpu_start=self.cpu()
 def cpu(self):
  try:
   fields=Path(f'/proc/{self.process.pid}/stat').read_text().rsplit(')',1)[1].split();import os
   return (int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
  except FileNotFoundError:return 0
 def request(self,value):
  self.process.stdin.write(json.dumps(value)+'\n');self.process.stdin.flush()
  if not select.select([self.process.stdout],[],[],120)[0]:raise TimeoutError('compiler host')
  line=self.process.stdout.readline(16*1024*1024)
  if not line.endswith('\n'):raise RuntimeError('missing/bounded host response')
  return json.loads(line)
 def close(self):
  if self.process.poll() is None:self.process.stdin.close()
  try:self.process.wait(timeout=10)
  except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
  self.process.stdout.close();self.log.close()
  if self.process.returncode:raise RuntimeError('compiler host exit '+str(self.process.returncode))

def require(row):
 if not row.get('ok'):raise RuntimeError(str({k:v for k,v in row.items() if k!='observations'}))
 return row

def admit(host,root,edits,generation):
 return require(host.request(dict(edits={str(root/p):v for p,v in edits.items()},source_root=str(root),expected_generation=generation)))['generation']

def request(host,root,command,target,generation,context='configuration-0',analysis=False):
 args=list(command);output=root/args[args.index('-o')+1];args[args.index('-o')+1]=str(output)
 if analysis:
  args[args.index('-MF')+1]+='.editor'
 return require(host.request(dict(args=args,cwd=str(root),output=str(output),target=target,generation=generation,context=context,mode='observed',analysis='off',analysis_only=analysis,logical=True,store=True)))

def scan(host,targets,generation,context='configuration-0'):
 return require(host.request(dict(scan=targets,generation=generation,context=context)))

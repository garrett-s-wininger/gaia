"""Fixed-context experiment admission. Not a complete production compiler identity."""
import hashlib,json,os,subprocess
from pathlib import Path

def sha_file(path):
 digest=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(1048576),b''):digest.update(block)
 return digest.hexdigest()

def snapshot(command,project,mutable,work):
 # Private cloned project: only the declared main source may change. Include
 # all files so even previously unreferenced local headers remain fixed.
 files={str(p):sha_file(p) for p in project.rglob('*') if p.is_file() and p.resolve()!=mutable.resolve()}
 command=list(command);at=command.index('-o');command[at:at+2]=[]
 command.remove('-c');depfile=work/'context.d'
 process=subprocess.run([*command,'-M','-MF',str(depfile)],cwd=project,capture_output=True,text=True,timeout=60)
 if process.returncode:raise RuntimeError(process.stderr)
 # Fixture paths have no spaces. Reject unsupported Make escaping rather than
 # silently claiming a complete SDK closure.
 text=depfile.read_text().replace('\\\n',' ')
 if '\\' in text:raise ValueError('escaped dependency paths unsupported in this experiment')
 dependencies=text.split(':',1)[1].split()
 for name in dependencies:
  path=Path(name)
  if not path.is_absolute():path=project/path
  if path.resolve()!=mutable.resolve():files[str(path)]=sha_file(path)
 compiler=Path(command[0]).resolve();files[str(compiler)]=sha_file(compiler)
 version=subprocess.run([str(compiler),'--version'],check=True,capture_output=True,text=True).stdout
 linked=subprocess.run(['ldd',str(compiler)],check=True,capture_output=True,text=True).stdout
 for line in linked.splitlines():
  tokens=line.split();path=next((Path(v) for v in tokens if v.startswith('/')),None)
  if path and path.is_file():files[str(path)]=sha_file(path)
 return dict(project_root=str(project),mutable_source=str(mutable),project_files=sorted(str(p) for p in project.rglob('*') if p.is_file() and p.resolve()!=mutable.resolve()),files=files,environment_sha256=hashlib.sha256(json.dumps(dict(os.environ),sort_keys=True).encode()).hexdigest(),bindings={name:str(Path(name).resolve()) for name in [*files,str(command[0])]},command=list(command),compiler_version=version,compiler_linkage=linked,policy='Private project all files except selected source; baseline dependency closure; compiler and linked libraries; exact inherited environment. Fixed configuration only, not complete SDK discovery or production admission.')

def verify(context):
 if 'project_root' in context:
  root=Path(context['project_root']);mutable=Path(context['mutable_source']);current=sorted(str(p) for p in root.rglob('*') if p.is_file() and p.resolve()!=mutable.resolve())
  if current!=context['project_files']:raise ValueError('private project membership changed')
 if hashlib.sha256(json.dumps(dict(os.environ),sort_keys=True).encode()).hexdigest()!=context['environment_sha256']:raise ValueError('environment changed during experiment')
 for name,target in context['bindings'].items():
  if str(Path(name).resolve())!=target:raise ValueError('path binding changed: '+name)
 for name,digest in context['files'].items():
  if sha_file(name)!=digest:raise ValueError('fixed context changed: '+name)
 return dict(passed=True,files=len(context['files']),bytes=sum(Path(name).stat().st_size for name in context['files']))

def portable(context):
 # Preserve exact command/paths/environment digest in ignored raw data. Public review
 # metadata gives identities without copying host paths or environment values (only its hash is retained).
 encoded=json.dumps(context,sort_keys=True).encode()
 return dict(policy=context['policy'],files=len(context['files']),context_sha256=hashlib.sha256(encoded).hexdigest(),compiler_version=context['compiler_version'])

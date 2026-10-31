"""Real module-membership and dynamic Groovy semantics, all variants, normal JVM exits."""
import argparse,json,os,subprocess,zipfile
from pathlib import Path
from profile import checked,sha
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--tools',type=Path,required=True);p.add_argument('--run',type=Path,required=True);args=p.parse_args();tools=args.tools.resolve();data=json.loads(args.run.read_text());work=Path(data['work']);jdk=tools/'toolchain/jdk-25.0.5.0.3';java=jdk/'bin/java';pico=tools/'downloads/picocli-4.7.7.jar'
 classes=work/'validation-classes';classes.mkdir(exist_ok=True);checked([jdk/'bin/javac','--release','17','-d',classes,HERE/'ModuleProbe.java',HERE.parent/'GaiaExtensions.java'])
 extension=work/'extension.jar'
 with zipfile.ZipFile(extension,'w') as z:
  z.write(classes/'GaiaExtensions.class','GaiaExtensions.class');z.writestr('META-INF/groovy/org.codehaus.groovy.runtime.ExtensionModule','moduleName=gaia-jvmti-probe\nmoduleVersion=1\nextensionClasses=GaiaExtensions\nstaticExtensionClasses=\n')
 variants={'stock':tools/'downloads/groovy-6.0.0.jar',**{name:Path(v['jar']) for name,v in data['preparation']['variants'].items()}};rows=[];digest=None
 for name,jar in variants.items():
  cp=os.pathsep.join(map(str,[jar,pico,work/'phases.jar',classes]));base=[java,'-Xshare:on','-XX:SharedArchiveFile='+str(work/(name+'.jsa')),'-cp',cp]
  probe=json.loads(checked(base+['ModuleProbe']).stdout)
  if digest is None:digest=(probe['digest'],probe['table_entries'])
  if (probe['digest'],probe['table_entries'])!=digest:raise ValueError('module table mismatch')
  for mode,expected in [('records',None),('registry','ready'),('metaclass','14'),('loader','18'),('extension','hello_11')]:
   token=name+'-'+mode;command=base.copy()
   if mode=='extension':command[command.index('-cp')+1]+=os.pathsep+str(extension)
   value=json.loads(checked(command+['FrameworkPhases',mode,token,'11'],env=dict(os.environ,GAIA_REQUEST_TOKEN=token)).stdout)
   if value['token']!=token:raise ValueError('stale token')
   if expected is not None and value['result']!=expected:raise ValueError(value)
   if mode=='records' and (value['records'],value['digest'])!=(data['record_identity']['count'],data['record_identity']['sha256']):raise ValueError('descriptors')
   rows.append(dict(variant=name,mode=mode,passed=True))
  command=base+['FrameworkPhases','extension',name+'-missing','11'];missing=subprocess.run(list(map(str,command)),capture_output=True,text=True,env=dict(os.environ,GAIA_REQUEST_TOKEN=name+'-missing'),timeout=60)
  if missing.returncode==0 or 'MissingMethodException' not in missing.stderr:raise ValueError('extension removal')
  rows.append(dict(variant=name,module_probe=probe,extension_removal=True))
 result=dict(passed=True,run_sha256=sha(args.run),source_sha256={p.name:sha(p) for p in [HERE/'validate.py',HERE/'ModuleProbe.java']},rows=rows)
 (args.run.parent/'semantic-validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()

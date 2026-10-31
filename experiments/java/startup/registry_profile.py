#!/usr/bin/env python3
"""Intrusive Groovy constructor-stage diagnostic; never a latency control."""
import argparse,hashlib,json,os,subprocess,time,zipfile
from pathlib import Path
import dgm_prepare as prep
HERE=Path(__file__).resolve().parent
SOURCE='org/codehaus/groovy/runtime/metaclass/MetaClassRegistryImpl.java'

def run(args):
 d=json.loads(args.run.read_text());work=Path(d['work']);jdk=args.jdk.resolve();stock=(HERE/'_work/downloads/groovy-6.0.0.jar').resolve();sources=(HERE/'_work/downloads/groovy-6.0.0-sources.jar').resolve();args.output.mkdir(parents=True)
 with zipfile.ZipFile(sources) as z:text=z.read(SOURCE).decode()
 anchors=[('            final Class[] additionals = DefaultGroovyMethods.ADDITIONAL_CLASSES;','m[0]=System.nanoTime();'),('            Class[] pluginDGMs = VMPluginFactory.getPlugin().getPluginDefaultGroovyMethods();','m[1]=System.nanoTime();'),('            registerMethods(DefaultGroovyStaticMethods.class, false, false, map);','m[2]=System.nanoTime();'),('            ExtensionModuleScanner scanner = new ExtensionModuleScanner(new DefaultModuleListener(map), this.getClass().getClassLoader());','m[3]=System.nanoTime();'),('            refreshMopMethods(map);','m[4]=System.nanoTime();'),('        installMetaClassCreationHandle();','m[5]=System.nanoTime();')]
 text=text.replace('        this.useAccessible = useAccessible;','        this.useAccessible = useAccessible; long profileStart=System.nanoTime();long[] m=new long[9];')
 for needle,insert in anchors:
  if text.count(needle)!=1:raise ValueError('profile anchor changed: '+needle)
  text=text.replace(needle,insert+'\n'+needle)
 text=text.replace('        final MetaClass emcMetaClass = metaClassCreationHandle.create(ExpandoMetaClass.class, this);','        m[6]=System.nanoTime();\n        final MetaClass emcMetaClass = metaClassCreationHandle.create(ExpandoMetaClass.class, this);')
 text=text.replace('        ClassInfo.getClassInfo(ExpandoMetaClass.class).setStrongMetaClass(emcMetaClass);','        ClassInfo.getClassInfo(ExpandoMetaClass.class).setStrongMetaClass(emcMetaClass);m[7]=System.nanoTime();')
 needle='        });\n   }';assert text.count(needle)==1
 text=text.replace(needle,'''        });
        m[8]=System.nanoTime();
        if(Boolean.getBoolean("gaia.profile.registry")) {
            String[] names={"dgm_records_and_proxy_grouping","additional_methods","plugin_instance_methods","static_methods","extension_scan","refresh_mop_methods","creation_handle","expando_metaclass","change_listener"};
            StringBuilder s=new StringBuilder("GAIA_REGISTRY {");long before=profileStart;
            for(int i=0;i<m.length;i++){if(i>0)s.append(',');s.append('"').append(names[i]).append("\\\":").append(m[i]-before);before=m[i];}
            System.err.println(s.append('}'));
        }
   }''')
 source=args.output/'source'/SOURCE;source.parent.mkdir(parents=True);source.write_text(text);classes=args.output/'classes';classes.mkdir()
 prep.checked([jdk/'bin/javac','--release','17','-cp',stock,'-d',classes,source]);replacements={p.relative_to(classes).as_posix():p.read_bytes() for p in classes.rglob('*.class')};jar=args.output/'groovy-profile.jar'
 with zipfile.ZipFile(stock) as inp,zipfile.ZipFile(jar,'w') as out:
  for info in inp.infolist():out.writestr(info,replacements.pop(info.filename,inp.read(info)))
  if replacements:raise ValueError('extra profile classes')
 cp=str(jar)+os.pathsep+str((HERE/'_work/downloads/picocli-4.7.7.jar').resolve());names=set()
 for p in (jar,HERE/'_work/downloads/picocli-4.7.7.jar'):
  with zipfile.ZipFile(p) as z:names.update(n[:-6] for n in z.namelist() if n.endswith('.class') and not n.startswith('META-INF/') and n!='module-info.class')
 cl=args.output/'profile.classlist';cl.write_text((jdk/'lib/classlist').read_text().rstrip()+'\n'+'\n'.join(sorted(names))+'\n');archive=args.output/'profile.jsa';prep.checked([jdk/'bin/java','-Xshare:dump','-Xmixed','-XX:SharedClassListFile='+str(cl),'-XX:SharedArchiveFile='+str(archive),'-cp',cp])
 records=[]
 for i in range(args.trials):
  token='registry-profile-'+str(i);p=subprocess.run([str(jdk/'bin/java'),'-Dgaia.profile.registry=true','-Xshare:on','-XX:SharedArchiveFile='+str(archive),'-cp',cp+os.pathsep+str(work/'phases.jar'),'FrameworkPhases','registry',token,'5'],capture_output=True,text=True,env=dict(os.environ,GAIA_REQUEST_TOKEN=token))
  if p.returncode:raise ValueError(p.stdout+p.stderr)
  value=json.loads(p.stdout);assert value['token']==token
  record=json.loads(next(line[14:] for line in p.stderr.splitlines() if line.startswith('GAIA_REGISTRY ')));records.append(record)
 result=dict(scope='Intrusive source-timer diagnostic with rebuilt registry class and matching static CDS. Stage counts only; not an uninstrumented latency comparison.',source_run=d['run_id'],patched_source_sha256=prep.sha(source),jar_sha256=prep.sha(jar),source_sha256=prep.sha(Path(__file__)),records_ns=records)
 (args.output/'profile.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--jdk',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--trials',type=int,default=3);run(p.parse_args())

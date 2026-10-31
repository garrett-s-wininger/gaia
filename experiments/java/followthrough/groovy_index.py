"""Prepared immutable java.base class discovery, fresh Groovy maps and bindings."""
import argparse,hashlib,json,os,pathlib,random,statistics,subprocess,time,zipfile
HERE=pathlib.Path(__file__).resolve().parent
SOURCE='org/codehaus/groovy/vmplugin/v9/Java9.java'
RESOURCE='META-INF/gaia/runtime-java-base.idx'
HELPER=r'''
    private static Map<String, Set<String>> gaiaRuntimeClasses() {
        try (java.io.InputStream raw = Java9.class.getClassLoader().getResourceAsStream("META-INF/gaia/runtime-java-base.idx")) {
            if (raw == null) throw new IllegalStateException("missing runtime discovery index");
            java.io.DataInputStream in = new java.io.DataInputStream(raw);
            if (in.readInt() != 0x47414931 || !in.readUTF().equals(System.getProperty("java.runtime.version"))) throw new IllegalStateException("runtime discovery index identity");
            int count=in.readInt();if(count<0||count>100000)throw new IllegalStateException("index count");
            Map<String, Set<String>> result=new LinkedHashMap<>();
            for(int i=0;i<count;i++) {
                String name=in.readUTF();int n=in.readInt();if(n<0||n>10000)throw new IllegalStateException("index package count");
                Set<String> packages=new HashSet<>();for(int j=0;j<n;j++)if(!packages.add(in.readUTF()))throw new IllegalStateException("duplicate package");
                if(result.put(name,java.util.Collections.unmodifiableSet(packages))!=null)throw new IllegalStateException("duplicate name");
            }
            if(in.read()!=-1)throw new IllegalStateException("trailing index data");
            return java.util.Collections.unmodifiableMap(result);
        } catch(java.io.IOException error) {throw new IllegalStateException("runtime discovery index unreadable",error);}
    }
    private static class GaiaRuntimeClasses { static final Map<String, Set<String>> VALUE=gaiaRuntimeClasses(); }
'''
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def checked(cmd,env=None):
    p=subprocess.run(list(map(str,cmd)),capture_output=True,text=True,env=env)
    if p.returncode:raise RuntimeError(p.stdout+p.stderr)
    return p

def prepare(a):
    a.work.mkdir(parents=True,exist_ok=True);downloads=a.tools/'downloads';stock=downloads/'groovy-6.0.0.jar';sources=downloads/'groovy-6.0.0-sources.jar';classes=a.work/'producer';classes.mkdir(exist_ok=True)
    start=time.perf_counter_ns();checked([a.jdk/'bin/javac','--release','17','-cp',stock,'-d',classes,HERE/'RuntimeIndex.java']);index=a.work/'java-base.idx';value=json.loads(checked([a.jdk/'bin/java','-XX:-UsePerfData','-cp',str(stock)+os.pathsep+str(classes),'RuntimeIndex',index]).stdout);producer_ns=time.perf_counter_ns()-start
    with zipfile.ZipFile(sources) as z:original=z.read(SOURCE).decode()
    anchor='Map<String, Set<String>> result = ClassFinder.find(uri, packageName, true, false)'
    assert original.count(anchor)==1
    patched=original.replace(anchor,'Map<String, Set<String>> result = (("jrt".equals(uri.getScheme()) && "/modules/java.base/".equals(uri.getPath()) && "java".equals(packageName)) ? GaiaRuntimeClasses.VALUE : ClassFinder.find(uri, packageName, true, false))')
    patched=patched.replace('    private static Map<String, Set<String>> doFindClasses(',HELPER+'\n    private static Map<String, Set<String>> doFindClasses(')
    variants={};build_ns={}
    for name,text in [('rebuilt',original),('indexed',patched)]:
        start=time.perf_counter_ns();folder=a.work/name;folder.mkdir(exist_ok=True);src=folder/'source'/SOURCE;src.parent.mkdir(parents=True,exist_ok=True);src.write_text(text);out=folder/'classes';out.mkdir(exist_ok=True)
        checked([a.jdk/'bin/javac','--release','17','-cp',stock,'-d',out,src]);replacement={p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*.class')};target=folder/'groovy.jar'
        with zipfile.ZipFile(stock) as inp,zipfile.ZipFile(target,'w') as z:
            for item in inp.infolist():z.writestr(item,replacement.pop(item.filename,inp.read(item)))
            for path,content in replacement.items():z.writestr(path,content)
            if name=='indexed':z.writestr(RESOURCE,index.read_bytes())
        variants[name]=target;build_ns[name]=time.perf_counter_ns()-start
    app=a.work/'app';app.mkdir(exist_ok=True);old=HERE.parent/'startup'
    checked([a.jdk/'bin/javac','--release','17','-cp',str(stock)+os.pathsep+str(downloads/'picocli-4.7.7.jar'),'-d',app,HERE/'ImportProbe.java',old/'FrameworkPhases.java',old/'GaiaExtensions.java'])
    extension=a.work/'extension.jar'
    with zipfile.ZipFile(extension,'w') as z:
        z.write(app/'GaiaExtensions.class','GaiaExtensions.class');z.writestr('META-INF/groovy/org.codehaus.groovy.runtime.ExtensionModule','moduleName=gaia-runtime-index-probe\nmoduleVersion=1\nextensionClasses=GaiaExtensions\nstaticExtensionClasses=\n')
    pins=dict(runtime_modules_sha256=sha(a.jdk/'lib/modules'),java_sha256=sha(a.jdk/'bin/java'),stock_sha256=sha(stock),source_jar_sha256=sha(sources),index_sha256=sha(index),index_bytes=index.stat().st_size,producer_ns=producer_ns,build_ns=build_ns,producer_result=value)
    return variants,app,extension,pins

def run(a):
    variants,app,extension,pins=prepare(a);rows=[];validation=[];identity=None;dynamic=None
    def command(variant,mode,token):
        cp=os.pathsep.join(map(str,[variants[variant],a.tools/'downloads/picocli-4.7.7.jar',app]))
        return [a.jdk/'bin/java','-XX:-UsePerfData','-Xshare:on','-cp',cp]+(['ImportProbe'] if mode=='imports' else ['FrameworkPhases',mode,token,'11'])
    # Independent current-runtime equality; mutable maps are fresh on every request.
    for variant in variants:
        value=json.loads(checked(command(variant,'imports','probe')).stdout)
        signature=(value['digest'],value['entries'])
        if identity is None:identity=signature
        assert signature==identity
        for mode,expected in [('records',None),('metaclass','14'),('loader','18'),('extension','hello_11')]:
            token=variant+'-'+mode;cmd=command(variant,mode,token)
            if mode=='extension':cmd[cmd.index('-cp')+1]+=os.pathsep+str(extension)
            result=json.loads(checked(cmd,env=dict(os.environ,GAIA_REQUEST_TOKEN=token)).stdout)
            if expected is not None:assert result['result']==expected
            else:
                sig=(result['records'],result['digest'])
                if dynamic is None:dynamic=sig
                assert sig==dynamic
            validation.append(dict(variant=variant,mode=mode,passed=True))
        missing=subprocess.run(list(map(str,command(variant,'extension','missing'))),env=dict(os.environ,GAIA_REQUEST_TOKEN='missing'),capture_output=True,text=True)
        assert missing.returncode and 'MissingMethodException' in missing.stderr
    for block in range(-1,a.trials):
        operations=[(v,m) for v in variants for m in ['imports','registry','basic']];random.Random(987+block).shuffle(operations)
        for variant,mode in operations:
            token=f'{variant}-{mode}-{block+1}';begin=time.perf_counter_ns();proc=checked(command(variant,mode,token),env=dict(os.environ,GAIA_REQUEST_TOKEN=token));elapsed=time.perf_counter_ns()-begin;value=json.loads(proc.stdout)
            if mode=='imports':assert (value['digest'],value['entries'])==identity
            else:assert value['token']==token and value['result']==('ready' if mode=='registry' else '66')
            if block>=0:rows.append(dict(block=block,variant=variant,mode=mode,wall_ns=elapsed,result=value))
    assert pins['runtime_modules_sha256']==sha(a.jdk/'lib/modules')
    data=dict(schema='GAIA-GROOVY-RUNTIME-INDEX-1',scope='Externally admitted exact runtime image; default JVM CDS only, no agents; java.base discovery only. Runtime version checked by reader; full image digest verified by harness before/after, not hashed on each startup. Fresh maps/classes/dynamic overlays.',pins=pins,validation=validation,import_identity=identity,dgm_identity=dynamic,rows=rows)
    a.output.mkdir(parents=True,exist_ok=True);raw=a.output/'results.json';raw.write_text(json.dumps(data,indent=2)+'\n');summary=[]
    for mode in ['imports','registry','basic']:
        base=[r for r in rows if r['mode']==mode and r['variant']=='rebuilt']
        for variant in variants:
            values=[r for r in rows if r['mode']==mode and r['variant']==variant];summary.append(dict(mode=mode,variant=variant,median_process_ms=statistics.median(r['wall_ns']/1e6 for r in values),paired_wins=sum(x['wall_ns']<y['wall_ns'] for x,y in zip(values,base)),blocks=len(values)))
    (a.output/'summary.json').write_text(json.dumps(dict(cases=summary,raw_sha256=sha(raw),raw_bytes=raw.stat().st_size),indent=2)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--jdk',type=pathlib.Path,required=True);p.add_argument('--tools',type=pathlib.Path,required=True);p.add_argument('--work',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--trials',type=int,default=5);run(p.parse_args())

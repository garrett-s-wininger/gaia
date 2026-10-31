"""Read-only Python tool-environment composition with a real Django consumer."""
import argparse,hashlib,json,os,platform,random,shutil,statistics,subprocess,sys,sysconfig,time
from pathlib import Path
from common import HERE,digest,measured,pins,publish,read_corpus

PROBE=r'''
import hashlib,importlib.resources,json,sys
from pathlib import Path
config=json.loads(Path(sys.argv[1]).read_text());sys.path.insert(0,config['dependencies'])
import django,sqlparse,rest_framework
from django.conf import settings
settings.configure(INSTALLED_APPS=['rest_framework'],SECRET_KEY='gaia-research',USE_I18N=False,USE_TZ=False)
django.setup()
from rest_framework import serializers
class Event(serializers.Serializer):
    label=serializers.CharField()
    count=serializers.IntegerField()
event=Event(data={'label':'gaia','count':7});assert event.is_valid(),event.errors
from django.template import Engine,Context
rendered=Engine(debug=False).from_string('{{ label|upper }}:{{ count }}').render(Context(event.validated_data))
resource=importlib.resources.files('django').joinpath('contrib/admin/templates/admin/base.html').read_bytes()
assert rendered=='GAIA:7'
root=Path(config['dependencies']).resolve()
for module in (django,sqlparse,rest_framework):assert Path(module.__file__).resolve().is_relative_to(root)
print(json.dumps({'versions':[django.get_version(),sqlparse.__version__,rest_framework.VERSION],'api':dict(event.data),'template':rendered,'resource_sha256':hashlib.sha256(resource).hexdigest(),'token':sys.argv[2]}))
'''

def prepare_tree(rows,raw,root):
    root.mkdir(parents=True,exist_ok=False)
    for row in rows:
        name=Path(row['name'])
        if name.is_absolute() or '..' in name.parts:raise ValueError('invalid namespace')
        body=raw[row['offset']:row['offset']+row['size']]
        if digest(body)!=row['sha256']:raise ValueError('content changed')
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)

def rootfs(work,dependencies):
    root=work/'oci-root';root.mkdir();files={}
    def copy(path):
        source=Path(path);target=root/str(source).lstrip('/');target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source.resolve(),target);target.chmod(source.stat().st_mode&0o777);files[str(source)]=digest(target.read_bytes())
    interpreter=Path(sys.executable).resolve();copy(interpreter)
    stdlib=Path(sysconfig.get_path('stdlib'));shutil.copytree(stdlib,root/str(stdlib).lstrip('/'),ignore=shutil.ignore_patterns('__pycache__'))
    candidates=[interpreter,*stdlib.rglob('*.so')];libraries=set()
    for path in candidates:
        result=subprocess.run(['ldd',str(path)],capture_output=True,text=True)
        for line in result.stdout.splitlines():
            for token in line.split():
                if token.startswith('/') and Path(token).is_file():libraries.add(Path(token))
    for path in sorted(libraries):copy(path)
    shutil.copytree(dependencies,root/'deps');app=root/'app';app.mkdir();(app/'probe.py').write_text(PROBE);(app/'config.json').write_text(json.dumps({'dependencies':'/deps'}))
    return root,{'interpreter':str(interpreter),'sdk_files':len(files),'runtime_library_pins':files,'stdlib_source':str(stdlib),'root_bytes':sum(p.stat().st_size for p in root.rglob('*') if p.is_file())}

def run(args):
    sources=[Path(__file__),HERE/'common.py'];before=pins(sources);args.work.mkdir(parents=True,exist_ok=False)
    begin=time.perf_counter_ns();rows,raw,objects=read_corpus(args.index,args.payload);admission_ns=time.perf_counter_ns()-begin
    dependencies=args.work/'immutable-dependencies';begin=time.perf_counter_ns();prepare_tree(rows,raw,dependencies);materialization_ns=time.perf_counter_ns()-begin
    sdk={'interpreter_sha256':digest(Path(sys.executable).resolve().read_bytes()),'version':sys.version,'stdlib_location_role':'existing compatibleSDK shared by everycontrol; acquisition/download/fullSDKdiscovery not measured'}
    observations=[];oracle=None
    for block in range(args.trials):
        modes=['copy','symlink','direct'];random.Random(81+block).shuffle(modes)
        for mode in modes:
            with measured(args.lock):
                started=time.perf_counter_ns();env=args.work/f'env-{block}-{mode}';env.mkdir();(env/'probe.py').write_text(PROBE)
                if mode=='copy':shutil.copytree(dependencies,env/'deps');where=env/'deps'
                elif mode=='symlink':(env/'deps').symlink_to(dependencies,target_is_directory=True);where=env/'deps'
                else:where=dependencies
                (env/'config.json').write_text(json.dumps({'dependencies':str(where.resolve() if mode=='direct' else where)}));setup_ns=time.perf_counter_ns()-started;children=[]
                for number in range(args.starts):
                    token=f'{block}-{mode}-{number}';begin=time.perf_counter_ns();result=subprocess.run([sys.executable,'-I','-S','-B',str(env/'probe.py'),str(env/'config.json'),token],capture_output=True,text=True,check=True);elapsed=time.perf_counter_ns()-begin;value=json.loads(result.stdout);assert value.pop('token')==token
                    if oracle is None:oracle=value
                    assert value==oracle;children.append(elapsed)
                    if number==0:first_ns=time.perf_counter_ns()-started
                teardown=time.perf_counter_ns();shutil.rmtree(env);teardown_ns=time.perf_counter_ns()-teardown;whole=time.perf_counter_ns()-started
            observations.append({'block':block,'mode':mode,'setup_ns':setup_ns,'first_ready_ns':first_ns,'charged_first_ready_ns':first_ns+admission_ns+materialization_ns,'whole_session_ns':whole,'teardown_ns':teardown_ns,'children_ns':children})
    container=None
    if args.prepare_rootfs:
        started=time.perf_counter_ns();path,info=rootfs(args.work,dependencies);container={'path':str(path),'preparation_ns':time.perf_counter_ns()-started,**info}
    assert before==pins(sources)
    summary=[]
    for mode in ['copy','symlink','direct']:
        selected=[r for r in observations if r['mode']==mode]
        summary.append({'mode':mode,'median_setup_ms':statistics.median(r['setup_ns']/1e6 for r in selected),'median_first_ready_ms':statistics.median(r['first_ready_ns']/1e6 for r in selected),'median_charged_first_ready_ms':statistics.median(r['charged_first_ready_ns']/1e6 for r in selected),'median_complete_session_ms':statistics.median(r['whole_session_ns']/1e6 for r in selected),'median_teardown_ms':statistics.median(r['teardown_ns']/1e6 for r in selected)})
    result={'schema':'GAIA-SCIENCE-ENVIRONMENT-1','scope':'Read-only Python toolenv contract: actualDjango/DRF/sqlparse import+serializer+Djangotemplate+resource operation in freshisolatedPython. Copyprivatefiles, conventionalone-symlink and directsearchrootconfig controls. ExistinginterpreterSDK shared; notvirtualenvorOCIimageprovisioning/nativeloaderspeedclaim. Dependencycorpusadmission+onecommonmaterialization shownseparately andchargedtofirstready; sessionincludesnormalcleanup. Originalartifactcache presumedavailable; no downloads.','corpus':{'files':len(rows),'unique_objects':len(objects),'payload_bytes':len(raw),'index_sha256':digest(args.index.read_bytes()),'payload_sha256':digest(raw)},'sdk':sdk,'admission_ns':admission_ns,'common_materialization_ns':materialization_ns,'oracle':oracle,'rows':observations,'container_preparation':container,'sources':before}
    print(publish(args.output,result,{'cases':summary,'common_admission_ms':admission_ns/1e6,'common_materialization_ms':materialization_ns/1e6},{'passed':True,'fresh_real_framework_processes':len(observations)*args.starts,'same_api_resources_versions':True,'isolation_scope':'read-only dependencycontract; no writableprivatepackageguarantee'},sources))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--index',type=Path,required=True);p.add_argument('--payload',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--lock',type=Path);p.add_argument('--trials',type=int,default=3);p.add_argument('--starts',type=int,default=3);p.add_argument('--prepare-rootfs',action='store_true');run(p.parse_args())

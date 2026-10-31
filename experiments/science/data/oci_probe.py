"""Offline OCI rootfs readiness diagnostic; no image-pulling equivalence claim."""
import argparse,json,os,subprocess,time
from pathlib import Path
from common import HERE,digest,measured,pins,publish

def run(args):
    oracle=json.loads(args.environment_results.read_text());rootfs=args.rootfs.resolve();rows=[];sources=[Path(__file__),HERE/'environment.py',HERE/'common.py'];before=pins(sources)
    env=dict(os.environ,XDG_RUNTIME_DIR=str(args.runtime))
    base=['podman','--root',str(args.storage),'--runroot',str(args.runroot),'--tmpdir',str(args.tmpdir)]
    sdk=rootfs/'usr/bin/python3.14';sdk_sha=digest(sdk.read_bytes());app_sha=digest((rootfs/'app/probe.py').read_bytes())
    for number in range(args.trials):
        token='oci-'+str(number);command=[*base,'run','--rm','--network=none','--cgroups=disabled','--read-only','--security-opt','label=disable','--rootfs',str(rootfs),'/usr/bin/python3.14','-I','-S','-B','/app/probe.py','/app/config.json',token]
        with measured(args.lock):
            start=time.perf_counter_ns();result=subprocess.run(command,capture_output=True,text=True,env=env,timeout=90);elapsed=time.perf_counter_ns()-start
        if result.returncode:raise RuntimeError(result.stderr)
        value=json.loads(result.stdout);assert value.pop('token')==token;assert value==oracle['oracle'];rows.append({'operation':number,'ready_and_teardown_ns':elapsed,'same_consumer':True,'stderr':result.stderr})
    assert before==pins(sources) and sdk_sha==digest(sdk.read_bytes()) and app_sha==digest((rootfs/'app/probe.py').read_bytes())
    data={'schema':'GAIA-SCIENCE-OCI-READINESS-1','scope':'ThreefreshactualPodmanOCIcontainers frompreconstructedlocalrootfs, networkdisabled/read-onlyroot/cgroupsdisabled. SameunmodifiedPythonframeworkconsumer asusermodecontrol. Strongerisolationanddifferentnamespace capabilities, notanequal-capabilityspeedcomparison orlazyimage/pullbenchmark. RootfsSDK/dependencypreparation recordedseparately; noremoteimage.','rootfs_preparation_ns':oracle['container_preparation']['preparation_ns'],'rootfs_bytes':oracle['container_preparation']['root_bytes'],'environment_raw_sha256':digest(args.environment_results.read_bytes()),'interpreter_sha256':sdk_sha,'app_sha256':app_sha,'sources':before,'rows':rows}
    import statistics
    print(publish(args.output,data,{'median_ready_and_teardown_ms':statistics.median(r['ready_and_teardown_ns']/1e6 for r in rows),'operations':len(rows),'rootfs_preparation_ms':data['rootfs_preparation_ns']/1e6,'rootfs_bytes':data['rootfs_bytes']},{'passed':True,'actual_isolated_framework_processes':len(rows),'same_oracle':True,'network_disabled':True},sources))

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ['rootfs','storage','runtime','runroot','tmpdir','environment-results','output']:p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--trials',type=int,default=3);p.add_argument('--lock',type=Path);run(p.parse_args())

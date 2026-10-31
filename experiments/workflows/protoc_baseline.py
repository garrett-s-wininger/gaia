"""Existing multi-output protoc; reject descriptor handoffs that change outputs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import hashlib
import json
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import time

LANGUAGES=('cpp','python','java')
SOURCE_MODES=('independent_sequential','independent_parallel','combined')
DESCRIPTOR_MODES=('descriptor_first_parallel','descriptor_retained_parallel')


def digest(body):return hashlib.sha256(body).hexdigest()
def identity(root):
    return {p.relative_to(root).as_posix():digest(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}


def first_difference(expected,actual):
    """Bounded evidence; never construct a multi-megabyte textual diff."""
    a=expected.read_bytes();b=actual.read_bytes();shared=min(len(a),len(b));offset=shared
    for begin in range(0,shared,65536):
        left=a[begin:begin+65536];right=b[begin:begin+65536]
        if left!=right:
            offset=begin+next((i for i,(x,y) in enumerate(zip(left,right)) if x!=y),min(len(left),len(right)));break
    return dict(expected_bytes=len(a),actual_bytes=len(b),first_byte_offset=offset,
                expected_context_hex=a[max(0,offset-16):offset+32].hex(),actual_context_hex=b[max(0,offset-16):offset+32].hex())


def mismatch(oracle,actual,expected_root,actual_root):
    missing=sorted(set(oracle)-set(actual));extra=sorted(set(actual)-set(oracle));changed=sorted(k for k in oracle.keys()&actual.keys() if oracle[k]!=actual[k])
    result=dict(missing=missing,extra=extra,changed=changed,expected_hashes=oracle,actual_hashes=actual)
    if changed:result['first_difference']=dict(path=changed[0],**first_difference(expected_root/changed[0],actual_root/changed[0]))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protoc',type=Path,default=Path(shutil.which('protoc') or 'protoc'));p.add_argument('--descriptor',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--lock',type=Path);p.add_argument('--trials',type=int,default=5)
    args=p.parse_args();args.protoc=args.protoc.resolve();args.work.mkdir(parents=True,exist_ok=False);args.output.mkdir(parents=True,exist_ok=False)
    sources=args.work/'sources';sources.mkdir();target=sources/'google/protobuf/descriptor.proto';target.parent.mkdir(parents=True);target.write_bytes(args.descriptor.read_bytes())
    synthetic=['syntax="proto3";','package gaia.schema;','option java_package="gaia.schema";']
    for record in range(250):
        synthetic.append(f'message Record{record:05} {{')
        for field in range(12):synthetic.append(f'  {("string","int64","double","bool")[field%4]} field{field:02} = {field+1};')
        synthetic.extend([f'  Record{(record+1)%250:05} parent = 13;','}'])
    (sources/'fixture.proto').write_text('\n'.join(synthetic)+'\n');before=identity(sources);empty=args.work/'no-source-fallback';empty.mkdir()
    script_pin=digest(Path(__file__).read_bytes());tool_pin=digest(args.protoc.read_bytes())
    data=dict(schema_version=2,status='running',trials=args.trials,protoc_version=subprocess.check_output([str(args.protoc),'--version'],text=True).strip(),protoc_sha256=tool_pin,source_sha256=script_pin,inputs=before,prepared_descriptors={},preflight=[],observations=[],output_identities={},supported_modes={},
              scope='Unmodified existing protoc; three built-in outputs; actual installed descriptor.proto and synthetic250record fixture; warm filesystem; subprocess execution and output writes charged, output-directory preparation excluded; outputhash/Python syntax checks outside timings; first-descriptor mode charges producer, retained mode reports producer separately; empty source path prevents descriptor-mode fallback. Each child decodes its own model; no shared in-memory AST, generated C++/Java compilation, or universal descriptor-handoff equivalence claim.')
    def save():
        # Checkpoint after each complete operation and on exceptions. An interrupted
        # write itself is not a durable journal; prior process exceptions retain data.
        (args.output/'results.json').write_text(json.dumps(data,indent=2)+'\n')
    save()
    try:
        for case,source in [('descriptor','google/protobuf/descriptor.proto'),('generated','fixture.proto')]:
            def produce(path):
                subprocess.run([str(args.protoc),'-I',str(sources),'--include_source_info','--include_imports','--descriptor_set_out='+str(path),source],capture_output=True,check=True)
            model=args.work/f'{case}-prepared.bin';begin=time.perf_counter_ns();produce(model);data['prepared_descriptors'][case]=dict(producer_ns=time.perf_counter_ns()-begin,bytes=model.stat().st_size,sha256=digest(model.read_bytes()));save()
            def generate(mode,output,block,measured):
                output.mkdir()
                for language in LANGUAGES:(output/language).mkdir()
                current_model=model
                def command(languages):
                    semantic=mode in DESCRIPTOR_MODES
                    subprocess.run([str(args.protoc),'-I',str(empty if semantic else sources),*(['--descriptor_set_in='+str(current_model)] if semantic else []),*[f'--{language}_out={output/language}' for language in languages],source],capture_output=True,check=True)
                stream=args.lock.open('a') if args.lock else None
                try:
                    if stream:fcntl.flock(stream,fcntl.LOCK_EX)
                    begin=time.perf_counter_ns()
                    if mode=='descriptor_first_parallel':current_model=args.work/f'{case}-{block}-current.bin';produce(current_model)
                    if mode=='combined':command(LANGUAGES)
                    elif mode=='independent_sequential':
                        for language in LANGUAGES:command((language,))
                    else:
                        with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda language:command((language,)),LANGUAGES))
                    elapsed=time.perf_counter_ns()-begin
                finally:
                    if stream:stream.close()
                actual=identity(output)
                for path in (output/'python').rglob('*.py'):compile(path.read_bytes(),str(path),'exec')
                if mode=='descriptor_first_parallel':
                    if digest(current_model.read_bytes())!=data['prepared_descriptors'][case]['sha256']:raise ValueError('descriptor preparation changed')
                    current_model.unlink()
                return actual,elapsed
            oracle_root=args.work/f'{case}-source-oracle';oracle,_=generate('combined',oracle_root,'oracle',False);data['output_identities'][case]=oracle
            supported=[]
            # All modes are checked against source generation before timed sampling;
            # descriptor equality is a measured precondition, never an assumption.
            for mode in (*SOURCE_MODES,*DESCRIPTOR_MODES):
                output=args.work/f'{case}-preflight-{mode}';actual,elapsed=generate(mode,output,'preflight',False);passed=actual==oracle
                row=dict(case=case,mode=mode,passed=passed,wall_ns=elapsed,output_files=len(actual))
                if passed:supported.append(mode);shutil.rmtree(output)
                else:
                    row['rejection']=mismatch(oracle,actual,oracle_root,output);row['reason']='exact generated-output mismatch; mode excluded rather than normalized'
                    if mode in SOURCE_MODES:raise ValueError('source-mode output mismatch: '+case+' '+mode)
                data['preflight'].append(row);save()
            data['supported_modes'][case]=supported;save()
            for block in range(args.trials):
                order=list(supported);random.Random(block+501).shuffle(order)
                for mode in order:
                    output=args.work/f'{case}-{block}-{mode}';actual,elapsed=generate(mode,output,block,True)
                    if actual!=oracle:
                        data['measurement_rejection']=dict(case=case,mode=mode,block=block,evidence=mismatch(oracle,actual,oracle_root,output));raise ValueError('timed operation changed generated outputs')
                    data['observations'].append(dict(case=case,block=block,mode=mode,wall_ns=elapsed,output_files=len(actual),output_bytes=sum(p.stat().st_size for p in output.rglob('*') if p.is_file())))
                    save();shutil.rmtree(output)
            if digest(model.read_bytes())!=data['prepared_descriptors'][case]['sha256']:raise ValueError('prepared model mutated')
        if before!=identity(sources) or tool_pin!=digest(args.protoc.read_bytes()) or script_pin!=digest(Path(__file__).read_bytes()):raise ValueError('input/tool/source changed during run')
        data['status']='complete';save()
    except BaseException as error:
        data['status']='failed';data['error']=dict(type=type(error).__name__,message=str(error),stderr=getattr(error,'stderr',b'').decode(errors='replace')[-2000:] if isinstance(getattr(error,'stderr',None),bytes) else str(getattr(error,'stderr',''))[-2000:]);save();raise
    summaries=[]
    for case,modes in data['supported_modes'].items():
        for mode in modes:
            rows=[r for r in data['observations'] if r['case']==case and r['mode']==mode];summaries.append(dict(case=case,mode=mode,median_ms=statistics.median(r['wall_ns']/1e6 for r in rows),samples=len(rows)))
    raw=args.output/'results.json';summary=dict(cases=summaries,rejected=[dict(case=r['case'],mode=r['mode'],reason=r['reason']) for r in data['preflight'] if not r['passed']],raw_identity=dict(bytes=raw.stat().st_size,sha256=digest(raw.read_bytes())))
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summaries,indent=2))

if __name__=='__main__':main()

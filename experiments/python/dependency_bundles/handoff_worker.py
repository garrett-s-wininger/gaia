"""Fresh-process read/validate/decode diagnostic; no module execution."""
import argparse
import gc
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from native_loader import NativeBundleReader


def main(args):
    plan=json.loads(args.plan.read_text());readers=[]
    try:
        start=time.perf_counter()
        for row in plan['inputs']:
            readers.append(NativeBundleReader(row['archive'],row['index'],index_sha256=row['pin'],
                           library=plan['library'],verify='local',bytecode_handoff=args.mode))
        opened=time.perf_counter()
        gc.collect()
        cpu=time.process_time();start_decode=time.perf_counter()
        codes=[reader.load_code(name,source_hash=bytes.fromhex(source_hash) if source_hash else None)
               for reader,row in zip(readers,plan['inputs']) for name,source_hash in row['requests']]
        finished=time.perf_counter();cpu_finished=time.process_time()
        # Baseline equivalence and lifetime verification are outside measurement.
        for reader in readers:reader.close()
        reference=[]
        for row in plan['inputs']:
            reader=NativeBundleReader(row['archive'],row['index'],index_sha256=row['pin'],
                                     library=plan['library'],verify='local',bytecode_handoff='bytes')
            try:
                reference.extend(reader.load_code(name,source_hash=bytes.fromhex(h) if h else None) for name,h in row['requests'])
            finally:reader.close()
        if codes!=reference or any(a.co_filename!=b.co_filename for a,b in zip(codes,reference)):
            raise ValueError('decoded code differs')
        print(json.dumps(dict(correct=True,mode=args.mode,code_count=len(codes),
                              open_seconds=opened-start,decode_seconds=finished-start_decode,
                              decode_cpu_seconds=cpu_finished-cpu)))
    finally:
        for reader in readers:reader.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--mode',choices=['bytes','view','native'],required=True)
    main(parser.parse_args())

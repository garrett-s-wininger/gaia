#!/usr/bin/env python3
"""Acquire the exact recorded real TypeScript project source archive."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import urllib.request

HERE=Path(__file__).resolve().parent

def main(args):
    provenance=json.loads(args.provenance.read_text());url=provenance['dist']['tarball']
    if url!='https://registry.npmjs.org/exponential-backoff/-/exponential-backoff-3.1.3.tgz':raise ValueError('unexpected project URL')
    args.destination.mkdir(parents=True,exist_ok=True);archive=args.destination/'exponential-backoff-3.1.3.tgz'
    raw=archive.read_bytes() if archive.exists() else urllib.request.urlopen(url,timeout=120).read()
    algorithm,pin=provenance['dist']['integrity'].split('-',1)
    if algorithm!='sha512' or base64.b64encode(hashlib.sha512(raw).digest()).decode()!=pin:
        raise ValueError('project archive SHA-512 differs')
    if hashlib.sha256(raw).hexdigest()!=provenance['sha256'] or len(raw)!=provenance['bytes']:
        raise ValueError('project archive identity differs')
    archive.write_bytes(raw);(args.destination/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');print(args.destination)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--provenance',type=Path,default=HERE/'results/typescript-project/project-provenance.json')
    p.add_argument('--destination',type=Path,default=HERE/'_work/backoff-corpus')
    main(p.parse_args())

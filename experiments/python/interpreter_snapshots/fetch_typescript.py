#!/usr/bin/env python3
"""Fetch the exact recorded TypeScript archive; verify pinned SHA-512/SHA-256."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import urllib.request

HERE=Path(__file__).resolve().parent

def admit(body,provenance):
    alg,pin=provenance['dist']['integrity'].split('-',1)
    if alg!='sha512' or base64.b64encode(hashlib.sha512(body).digest()).decode()!=pin:
        raise ValueError('TypeScript SHA-512 differs')
    if hashlib.sha256(body).hexdigest()!=provenance['tarball_sha256'] or len(body)!=provenance['bytes']:
        raise ValueError('TypeScript archive identity differs')

def main(args):
    provenance=json.loads(args.provenance.read_text())
    url=provenance['dist']['tarball']
    if url!='https://registry.npmjs.org/typescript/-/typescript-5.9.3.tgz':raise ValueError('unexpected corpus URL')
    args.destination.mkdir(parents=True,exist_ok=True);archive=args.destination/'typescript-5.9.3.tgz'
    body=archive.read_bytes() if archive.exists() else urllib.request.urlopen(url,timeout=120).read()
    admit(body,provenance);archive.write_bytes(body)
    (args.destination/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print(args.destination)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--provenance',type=Path,default=HERE/'results/typescript/provenance.json')
    p.add_argument('--destination',type=Path,default=HERE/'_work/typescript-corpus')
    main(p.parse_args())

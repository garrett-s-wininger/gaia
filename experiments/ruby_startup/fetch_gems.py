#!/usr/bin/env python3
"""Acquire exact recorded gem archives, then install locally without resolving."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

HERE=Path(__file__).resolve().parent

def main(args):
    pins=json.loads(args.manifest.read_text());args.destination=args.destination.resolve();cache=args.destination/'archives';cache.mkdir(parents=True,exist_ok=True)
    archives=[]
    for row in pins['gems']:
        if row['url']!='https://rubygems.org/downloads/'+row['filename'] or Path(row['filename']).name!=row['filename']:raise ValueError('unexpected gem source')
        path=cache/row['filename'];body=path.read_bytes() if path.exists() else urllib.request.urlopen(row['url'],timeout=120).read()
        if len(body)!=row['bytes'] or hashlib.sha256(body).hexdigest()!=row['sha256']:raise ValueError('gem hash mismatch')
        path.write_bytes(body);archives.append(str(path))
    gems=args.destination/'gems';env=dict(os.environ,GEM_HOME=str(gems),GEM_PATH=str(gems),MAKEFLAGS='-j2')
    subprocess.run(['gem','install','--local','--ignore-dependencies','--no-document','--install-dir',str(gems)]+archives,env=env,check=True)
    print(gems)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,default=HERE/'results/initial/gem-provenance.json');p.add_argument('--destination',type=Path,default=HERE/'_work')
    main(p.parse_args())

#!/usr/bin/env python3
"""Record the exact experiment sources before starting a primary matrix."""
import argparse
import hashlib
import shutil
from pathlib import Path
from run_variants import write
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--data',type=Path,required=True);args=parser.parse_args()
output=args.data/'formal-sources';output.mkdir(parents=True,exist_ok=True)
for source in Path(__file__).resolve().parent.iterdir():
    if source.suffix in ('.py','.java','.json'):shutil.copyfile(source,output/source.name)
write(output/'pins.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file() and p.name!='pins.json'})

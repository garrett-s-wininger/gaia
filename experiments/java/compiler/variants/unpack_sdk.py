#!/usr/bin/env python3
"""Versioned explicit SYSTEM_MODULES representation, identical SDK class bytes."""
import argparse,hashlib,json,time,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--jdk',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();begin=time.perf_counter();rows=[];total=0
for jmod in sorted((a.jdk/'jmods').glob('*.jmod')):
 count=0;size=0;module=a.output/jmod.stem
 with zipfile.ZipFile(jmod) as z:
  for name in z.namelist():
   if name.startswith('classes/') and not name.endswith('/'):
    rel=Path(name).relative_to('classes');assert '..' not in rel.parts
    data=z.read(name);dest=module/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);count+=1;size+=len(data)
 rows.append(dict(module=jmod.stem,files=count,bytes=size,jmod_sha256=hashlib.sha256(jmod.read_bytes()).hexdigest()));total+=size
if not rows:raise ValueError('no SDK modules')
(a.output/'manifest.json').write_text(json.dumps(dict(jdk=str(a.jdk),seconds=time.perf_counter()-begin,bytes=total,modules=rows),indent=2)+'\n');print(total,len(rows),time.perf_counter()-begin)

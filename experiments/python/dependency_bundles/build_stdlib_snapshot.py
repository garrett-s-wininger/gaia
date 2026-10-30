"""Producer for the observed stdlib closure; validates checked bytecode once."""
import hashlib
import importlib.util
import json
import marshal
from pathlib import Path
import sys
import types
import zipfile
import zlib

import benchmark
from precomputed_index import build_index
from stdlib_snapshot import MANIFEST,runtime_identity


def relocate(code,filename):
    constants=tuple(relocate(c,filename) if isinstance(c,types.CodeType) else c for c in code.co_consts)
    result=code.replace(co_filename=filename,co_consts=constants)
    assert result.co_code==code.co_code
    return result


def build_snapshot(pairs,destination,host_root):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    host_root=Path(host_root);inputs=[]
    for source,pyc in pairs:
        source,pyc=Path(source),Path(pyc);raw=source.read_bytes();compiled=pyc.read_bytes()
        if (compiled[:4]!=importlib.util.MAGIC_NUMBER or int.from_bytes(compiled[4:8],'little')!=3 or
                compiled[8:16]!=importlib.util.source_hash(raw)):
            raise ValueError('source/checked-bytecode identity mismatch: '+str(source))
        code=marshal.loads(compiled[16:])
        if not isinstance(code,types.CodeType):raise ValueError('invalid code object')
        relative=source.relative_to(host_root).as_posix();package=relative.endswith('/__init__.py')
        name=relative[:-3].replace('/','.')
        if package:name=name[:-len('.__init__')]
        inputs.append(dict(name=name,relative=relative,package=package,raw=raw,compiled=compiled,code=code,
                           source_sha256=hashlib.sha256(raw).hexdigest(),original_pyc_sha256=hashlib.sha256(compiled).hexdigest()))
    inputs.sort(key=lambda r:r['name'])
    identity=dict(runtime=runtime_identity(),inputs=[{k:r[k] for k in ('name','relative','source_sha256','original_pyc_sha256')} for r in inputs])
    snapshot=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    directory=destination/'files';directory.mkdir()
    modules={}
    for row in inputs:
        relative=row['relative'];origin='gaia-stdlib://'+snapshot+'/'+relative
        body=row['compiled'][:16]+marshal.dumps(relocate(row['code'],origin))
        paths={'code':relative[:-3]+'.pyc','source':'__gaia_sources__/'+relative}
        record=dict(**paths,relative_source=relative,origin=origin,package=row['package'],
                    source_hash=row['compiled'][8:16].hex(),source_sha256=row['source_sha256'],original_pyc_sha256=row['original_pyc_sha256'])
        for key,payload in [('code',body),('source',row['raw'])]:
            target=directory/paths[key];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(payload)
            record[key+'_size']=len(payload);record[key+'_crc']=zlib.crc32(payload)
        modules[row['name']]=record
    manifest=dict(format='gaia-python-stdlib',version=1,snapshot=snapshot,runtime=runtime_identity(),modules=modules)
    encoded=(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n').encode()
    target=directory/MANIFEST;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(encoded)
    archive=destination/'stdlib.zip';benchmark.pack(directory,archive,zipfile.ZIP_STORED)
    index=destination/'stdlib.index';admitted=build_index(archive,index,encoding='binary')
    return dict(format='gaia-python-stdlib-input',version=1,snapshot=snapshot,modules=len(modules),
                runtime=runtime_identity(),directory=str(directory.resolve()),archive=str(archive.resolve()),
                index=str(index.resolve()),host_root=str(host_root.resolve()),manifest_sha256=hashlib.sha256(encoded).hexdigest(),**admitted)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-io',type=Path,default=benchmark.HERE/'_work/runs/path-index/diagnostics/host-io.json')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();observed=json.loads(args.host_io.read_text());root=Path(sys._stdlib_dir)
    pairs=[(root/Path(p).relative_to(root).parent.parent/(Path(p).name.split('.cpython-')[0]+'.py'),Path(p)) for p in observed['paths']['bytecode']]
    result=build_snapshot(pairs,args.output,root);benchmark.write_json(args.output/'input.json',result)
    print(args.output/'input.json')

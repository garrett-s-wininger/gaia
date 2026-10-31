#!/usr/bin/env python3
"""Fetch pinned official SDK/Crossgen artifacts into an isolated research root."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request
import zipfile

HERE=Path(__file__).resolve().parent

def main(args):
    pins=json.loads(args.manifest.read_text());args.destination.mkdir(parents=True,exist_ok=True)
    for name,filename in [('sdk','dotnet-sdk-10.0.403.tar.gz'),('crossgen','crossgen2.nupkg')]:
        row=pins[name];url=row['file']['url'] if name=='sdk' else row['url'];path=args.destination/filename
        if not url.startswith(('https://builds.dotnet.microsoft.com/dotnet/','https://api.nuget.org/v3-flatcontainer/')):raise ValueError('unexpected source')
        if not path.exists():
            with urllib.request.urlopen(url,timeout=180) as response,path.open('wb') as stream:
                while chunk:=response.read(1048576):stream.write(chunk)
        body=path.read_bytes();actual=hashlib.sha512(body).hexdigest() if name=='sdk' else base64.b64encode(hashlib.sha512(body).digest()).decode()
        expected=row['file']['hash'] if name=='sdk' else row['sha512']
        if actual!=expected or len(body)!=row['bytes']:raise ValueError('archive integrity mismatch')
        target=args.destination/('sdk' if name=='sdk' else 'crossgen2');target.mkdir(exist_ok=True)
        if name=='sdk':
            with tarfile.open(path) as archive:archive.extractall(target,filter='data')
        else:
            with zipfile.ZipFile(path) as archive:
                for member in archive.infolist():
                    relative=Path(member.filename)
                    if relative.is_absolute() or '..' in relative.parts:raise ValueError('unsafe package path')
                archive.extractall(target)
            (target/'tools/crossgen2').chmod(0o755)
        (args.destination/(name+'-provenance.json')).write_text(json.dumps(row,indent=2)+'\n')
    print(args.destination)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,default=HERE/'results/initial/toolchain-provenance.json');p.add_argument('--destination',type=Path,default=HERE/'_work')
    main(p.parse_args())

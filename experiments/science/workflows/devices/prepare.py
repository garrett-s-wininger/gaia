"""Pinned official SDK extraction/build. Never installs or changes a driver."""
import argparse,hashlib,json,pathlib,subprocess,tarfile,urllib.request,time
HERE=pathlib.Path(__file__).resolve().parent
ITEMS=[('DirectXShaderCompiler','v1.9.2609','https://github.com/microsoft/DirectXShaderCompiler/releases/download/v1.9.2609/linux_dxc_2026_09_28.x86_x64.tar.gz','96faadc7f5c282d2ffda49804beb4c3ee38127bc252b723234e3c5cdf7aa39a1'),('DirectX-Headers','v1.620.1','https://codeload.github.com/microsoft/DirectX-Headers/tar.gz/refs/tags/v1.620.1','79cd6d5b87d940044b20a3f45e5fbf4a73e4c7eedc1bafabe1b5cabb97fef5bf')]
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=pathlib.Path,required=True);a=p.parse_args();w=a.work;w.mkdir(parents=True,exist_ok=True);pins=[]
 for name,tag,url,digest in ITEMS:
  archive=w/(name+'.tar.gz')
  if not archive.exists():
   with urllib.request.urlopen(url) as response:archive.write_bytes(response.read())
  assert hashlib.sha256(archive.read_bytes()).hexdigest()==digest
  dest=w/name;dest.mkdir(exist_ok=True)
  with tarfile.open(archive) as t:t.extractall(dest,filter='data')
  pins.append(dict(project=name,tag=tag,url=url,bytes=archive.stat().st_size,sha256=digest))
 (w/'acquisition.json').write_text(json.dumps(pins,indent=2)+'\n');h=w/'DirectX-Headers/DirectX-Headers-1.620.1'
 commands=[['g++','-std=c++17','-O3','-DNDEBUG','-D_Field_size_bytes_opt_(x)=','-D_Inout_count_(x)=','-I'+str(h/'include'),'-I'+str(h/'include/wsl/stubs'),str(HERE/'dispatch.cpp'),str(h/'src/dxguids.cpp'),'-ldl','-o',str(w/'dispatch')],[str(w/'DirectXShaderCompiler/bin/dxc'),'-T','cs_6_0','-E','main',str(HERE/'frontier.hlsl'),'-Fo',str(w/'frontier.dxil')]]
 rows=[]
 for command in commands:
  start=time.perf_counter_ns();subprocess.run(command,check=True);rows.append({'argv':command,'ns':time.perf_counter_ns()-start})
 (w/'preparation.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__':main()

"""Real PNG assets through independent and shared ffmpeg pipelines."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib,json,random,shutil,struct,time
from common import checked,timed,lock,filepin

SIZES=(128,256,384)
PREFIX=['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-threads','1']

def encode(source,output,size,raw=None,dimensions=None):
    args=PREFIX.copy()
    if raw is None:args+=['-i',str(source)]
    else:args+=['-f','rawvideo','-pixel_format','rgba','-video_size',f'{dimensions[0]}x{dimensions[1]}','-i','pipe:0']
    args+=['-filter_threads','1','-vf',f'scale={size}:{size}:flags=bilinear,format=rgba','-frames:v','1','-c:v','png','-threads:v','1','-compression_level','3',str(output)]
    checked(args,input=raw)

def decode(path):return checked(PREFIX+['-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','rgba','pipe:1']).stdout

def operation(mode,source,output):
    output.mkdir()
    data=source.read_bytes();width,height=struct.unpack('>II',data[16:24]);raw=None
    if mode=='shared-raw-parallel':raw=decode(source)
    if mode=='combined-ffmpeg':
        filters='[0:v]format=rgba,split=3[a][b][c];'+ ';'.join(f'[{name}]scale={size}:{size}:flags=bilinear[o{n}]' for n,(name,size) in enumerate(zip('abc',SIZES)))
        args=PREFIX+['-i',str(source),'-filter_complex_threads','3','-filter_complex',filters]
        for n,size in enumerate(SIZES):args+=['-map',f'[o{n}]','-frames:v','1','-pix_fmt','rgba','-c:v','png','-threads:v','1','-compression_level','3',str(output/f'{size}.png')]
        checked(args)
    else:
        def one(size):encode(source,output/f'{size}.png',size,raw,(width,height))
        if mode=='independent-sequential':list(map(one,SIZES))
        else:
            with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(one,SIZES))
    return dict(input_bytes=len(data),retained_rgba_bytes=len(raw) if raw else 0,output_bytes=sum(p.stat().st_size for p in output.iterdir()))

def run(args):
    tool=Path(shutil.which('ffmpeg'));tool_pin=filepin(tool)
    work=args.work/'assets';work.mkdir();rows=[];inputs=[];oracles={};rng=random.Random(741)
    candidates=[Path('/usr/share/icons/hicolor/512x512/apps/qemu.png'),Path('/usr/share/info/gnutls-internals.png'),Path('/usr/share/doc/ogg/html/multiplex1.png')]
    for index,path in enumerate(candidates):
        if not path.exists():raise FileNotFoundError('provide the documented system PNG corpus or adjust candidates explicitly')
        copy=work/f'input{index}.png';copy.write_bytes(path.read_bytes());inputs.append(dict(name=path.name,bytes=copy.stat().st_size,sha256=filepin(copy)))
    for block in range(args.trials):
      for index,_ in enumerate(candidates):
        source=work/f'input{index}.png';modes=['independent-sequential','independent-parallel','combined-ffmpeg','shared-raw-parallel'];rng.shuffle(modes)
        for mode in modes:
            output=work/f'{index}-{block}-{mode}'
            with lock(args.lock):sample=timed(lambda:operation(mode,source,output))
            hashes={p.name:hashlib.sha256(decode(p)).hexdigest() for p in sorted(output.iterdir())}
            if index not in oracles:oracles[index]=hashes
            assert hashes==oracles[index],(index,mode)
            rows.append(dict(block=block,input=index,mode=mode,wall_ns=sample['wall_ns'],parent_cpu_ns=sample['parent_cpu_ns'],counts=sample['value'],pixels=hashes));shutil.rmtree(output)
    assert tool_pin==filepin(tool)
    assert [r['sha256'] for r in inputs]==[filepin(work/f'input{i}.png') for i in range(len(inputs))]
    return dict(inputs=inputs,rows=rows,ffmpeg_sha256=tool_pin,ffmpeg_version=checked(['ffmpeg','-version']).stdout.decode().splitlines()[0],
                scope='Three actual installed PNG icons/diagrams; three square resize+PNG outputs. Complete subprocess/pipe/output operation; decoded RGBA equivalence, not identical PNG metadata. Logical retained buffer counts exclude process/native/transient memory. Existing multi-output ffmpeg is strong control; no new decoder/encoder or photographic/video claim.')

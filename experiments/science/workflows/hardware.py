"""Capability probes are not GPU performance results."""
import subprocess
from pathlib import Path
from common import save

def run(output):
    probes=[]
    commands=[
      ['ffmpeg','-hide_banner','-hwaccels'],
      ['ffmpeg','-nostdin','-hide_banner','-loglevel','verbose','-init_hw_device','cuda=cu','-f','lavfi','-i','testsrc=size=128x128:rate=1','-frames:v','1','-f','null','-'],
      ['ffmpeg','-nostdin','-hide_banner','-loglevel','verbose','-init_hw_device','vulkan=vk','-filter_hw_device','vk','-f','lavfi','-i','testsrc=size=128x128:rate=1','-vf','format=nv12,hwupload,scale_vulkan=w=64:h=64,hwdownload,format=nv12','-frames:v','1','-f','null','-'],
    ]
    for args in commands:
      try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=30)
        probes.append(dict(command=args,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
      except subprocess.TimeoutExpired as exc:probes.append(dict(command=args,timed_out=True,stdout=str(exc.stdout),stderr=str(exc.stderr)))
    data=dict(scope='Actual init and one-frame scale capability attempts. A successful Vulkan call can use a CPU/software provider; no GPU timing or hardware inference from compiled-backend list.',device_nodes={p:Path(p).exists() for p in ['/dev/dxg','/dev/dri','/dev/kfd','/dev/accel']},probes=probes)
    save(output,data);return data
if __name__=='__main__':
    import sys
    run(sys.argv[1])

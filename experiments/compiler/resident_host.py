"""One serial native worker; no request/result retention in this transport."""
import atexit
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile


class ResidentHost:
    def __init__(self,host,env=None,completion_metadata=False):
        self.errors=tempfile.TemporaryFile();self.requests=0;self.peaks=[]
        self.completion_metadata=completion_metadata;self.arena_used=[];self.arena_reserved=0
        self.process=subprocess.Popen([str(host),'--serve'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.errors,env=env)
        atexit.register(self.close)

    def cpu_seconds(self):
        try:
            fields=Path(f'/proc/{self.process.pid}/stat').read_text().rsplit(')',1)[1].split()
            return (int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
        except FileNotFoundError:return 0

    def request(self,argv):
        encoded=[str(arg).encode() for arg in argv]
        body=struct.pack('<I',len(encoded))+b''.join(struct.pack('<I',len(arg))+arg for arg in encoded)
        try:
            self.process.stdin.write(struct.pack('<Q',len(body))+body);self.process.stdin.flush()
        except BrokenPipeError:raise RuntimeError('native worker exited') from None
        line=self.process.stdout.readline(4*1024*1024)
        if not line.endswith(b'\n'):
            self.errors.seek(0);raise RuntimeError('native worker failed: '+self.errors.read(65536).decode(errors='replace'))
        acknowledgement=self.process.stdout.readline(128)
        result=json.loads(line)
        if self.completion_metadata:
            fields=acknowledgement.split()
            if len(fields)!=3 or fields[0]!=b'GAIA-DONE':raise RuntimeError('checker cleanup acknowledgement')
            used,reserved=map(int,fields[1:])
            if not 0<=used<=reserved<=64*1048576:raise RuntimeError('checker allocation bound')
            self.arena_used.append(used);self.arena_reserved=reserved
        elif acknowledgement!=b'GAIA-DONE\n':raise RuntimeError('native worker did not complete request cleanup')
        self.requests+=1;self.peaks.append(result.get('peak_rss_bytes',0) if self.completion_metadata else result['peak_rss_bytes'])
        return result

    def statistics(self):
        result=dict(requests=self.requests,peak_rss_bytes=self.peaks,cpu_seconds=self.cpu_seconds(),serial=True)
        if self.completion_metadata:
            result.pop('peak_rss_bytes')
            result.update(arena_used_bytes=self.arena_used,arena_reserved_bytes=self.arena_reserved)
        try:
            result['final_memory_kib']={parts[0].rstrip(':'):int(parts[1]) for line in Path(f'/proc/{self.process.pid}/status').read_text().splitlines()
                                        if len(parts:=line.split())==3 and parts[0] in ('VmRSS:','VmHWM:','VmSize:')}
        except FileNotFoundError:pass
        return result

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        for stream in (self.process.stdin,self.process.stdout,self.errors):stream.close()

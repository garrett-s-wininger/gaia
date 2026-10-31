"""Verified demand admission; application-service model, not physical disk I/O."""
from collections import OrderedDict
from pathlib import Path
import hashlib
import json
import os
import socket
import socketserver
import struct
import sys
import threading
import time

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'storage'))
from service import ModelIO,Profile

REQUEST=struct.Struct('!QQ')
LENGTH=struct.Struct('!Q')
MAX_REQUEST=32*1024*1024

def digest(body):return hashlib.sha256(body).hexdigest()
def receive(sock,size):
    out=bytearray()
    while len(out)<size:
        part=sock.recv(size-len(out))
        if not part:raise EOFError('truncated service record')
        out.extend(part)
    return bytes(out)

class ChunkStore:
    """Pinned producer chunks, immutable retained bytes, strict logical-byte LRU."""
    def __init__(self,payload,chunk_size,budget,model,expected_hashes):
        self.path=Path(payload);self.size=self.path.stat().st_size
        if not 0<chunk_size<=MAX_REQUEST or budget<0:raise ValueError('admission bounds')
        self.chunk_size=chunk_size;self.budget=budget;self.model=model;self.hashes=expected_hashes
        if len(self.hashes)!=(self.size+chunk_size-1)//chunk_size:raise ValueError('chunk manifest geometry')
        self.stream=self.path.open('rb')
        self.cache=OrderedDict();self.bytes=0;self.peak=0;self.evictions=0;self.hits=0;self.misses=0;self.first_fetch=None;self.last_fetch=None;self.lock=threading.Lock();self.requests=0;self.trace=[]
    def _chunk(self,number):
        if number in self.cache:self.hits+=1;self.cache.move_to_end(number);return self.cache[number]
        self.misses+=1;offset=number*self.chunk_size;size=min(self.chunk_size,self.size-offset)
        body=self.model.pread(self.stream,self.path,offset,size)
        if digest(body)!=self.hashes[number]:raise ValueError('chunk digest mismatch')
        stamp=time.perf_counter();self.last_fetch=stamp
        if self.first_fetch is None:self.first_fetch=stamp
        if len(body)<=self.budget:
            while self.bytes+len(body)>self.budget:
                _,old=self.cache.popitem(last=False);self.bytes-=len(old);self.evictions+=1
            self.cache[number]=body;self.bytes+=len(body);self.peak=max(self.peak,self.bytes)
        return body
    def read(self,offset,size):
        if not 0<=size<=MAX_REQUEST or not 0<=offset<=self.size-size:raise ValueError('range bounds')
        with self.lock:
            self.requests+=1;self.trace.append((offset,size))
            result=[];end=offset+size
            while offset<end:
                number=offset//self.chunk_size;body=self._chunk(number);begin=offset%self.chunk_size;n=min(end-offset,len(body)-begin)
                result.append(body[begin:begin+n]);offset+=n
            return b''.join(result)
    def admit_all(self):
        if self.budget<self.size:raise ValueError('full admission budget')
        with self.lock:
            body=self.model.read(self.path,self.size)
            for number in range(len(self.hashes)):
                part=body[number*self.chunk_size:(number+1)*self.chunk_size]
                if digest(part)!=self.hashes[number]:raise ValueError('chunk digest mismatch')
                self.cache[number]=part;self.bytes+=len(part)
            self.peak=self.bytes;self.first_fetch=self.last_fetch=time.perf_counter()
    def stats(self):
        return dict(cache_bytes=self.bytes,peak_cache_bytes=self.peak,budget=self.budget,evictions=self.evictions,hits=self.hits,misses=self.misses,consumer_requests=self.requests,first_fetch=self.first_fetch,last_fetch=self.last_fetch,storage=self.model.stats())
    def close(self):self.stream.close()

class RangeStore:
    def __init__(self,payload,model):self.path=Path(payload);self.stream=self.path.open('rb');self.size=self.path.stat().st_size;self.model=model;self.first=None;self.last=None;self.requests=0;self.trace=[]
    def read(self,offset,size):
        if not 0<=size<=MAX_REQUEST or not 0<=offset<=self.size-size:raise ValueError('range bounds')
        self.trace.append((offset,size));body=self.model.pread(self.stream,self.path,offset,size);self.last=time.perf_counter();self.first=self.first or self.last;self.requests+=1;return body
    def stats(self):return dict(storage=self.model.stats(),first_fetch=self.first,last_fetch=self.last,consumer_requests=self.requests,cache_bytes=0,peak_cache_bytes=0,budget=0,evictions=0)
    def close(self):self.stream.close()

class Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads=True
    def __init__(self,address,store):
        self.store=store
        class Handler(socketserver.BaseRequestHandler):
            def handle(self):
                self.request.settimeout(30)
                try:
                    while True:
                        offset,size=REQUEST.unpack(receive(self.request,REQUEST.size))
                        try:body=store.read(offset,size)
                        except (ValueError,OSError):self.request.sendall(LENGTH.pack((1<<64)-1));return
                        self.request.sendall(LENGTH.pack(len(body))+body)
                except (EOFError,OSError):return
        super().__init__(str(address),Handler)

class Client:
    def __init__(self,address):self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);self.sock.settimeout(30);self.sock.connect(str(address))
    def read(self,offset,size):
        self.sock.sendall(REQUEST.pack(offset,size));length=LENGTH.unpack(receive(self.sock,LENGTH.size))[0]
        if length!=size:raise ValueError('service read failed/bounds')
        return receive(self.sock,length)
    def close(self):self.sock.close()

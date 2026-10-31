"""GAF2 first proof: bounded outstanding IDs and progressive batch records."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import multiprocessing
import socket
import socketserver
import struct
import threading
import time

import batch
import binary_transport as old
import transfer as t

MAGIC=b'GAF2';VERSION=2
STREAM=5
DATA=3;END=5;ERROR=9
END_BODY=struct.Struct('!8sIQ')
ERROR_BODY=struct.Struct('!8sH')
WINDOW=8;BYTE_WINDOW=4*1024*1024


def header(op,flags,ident,size):return old.HEADER.pack(MAGIC,VERSION,op,flags,ident,size)


def _serve(content,ready,delay_ms,faults):
    counts=dict(requests=0,response_payload_bytes=0,manifest_requests=0,range_requests=0,request_frame_bytes=0,response_framing_bytes=0,batch_framing_bytes=0)
    lock=threading.Lock();tags={path:'"sha256:'+t.digest(body)+'"' for path,body in content.items()}
    pool=ThreadPoolExecutor(max_workers=8)
    barrier=threading.Barrier(9);warm=[pool.submit(barrier.wait) for _ in range(8)];barrier.wait()
    for future in warm:future.result()
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            sock=self.request;sock.settimeout(10);sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            write_lock=threading.Lock();slots=threading.BoundedSemaphore(8);next_id=1;futures=[]
            def emit(op,flags,ident,prefix,payload=b''):
                fault=faults.get('reply')
                packet=header(op,flags,ident+1 if fault=='wrong-id' else ident,len(prefix)+len(payload))
                if fault=='wrong-version':packet=old.HEADER.pack(MAGIC,3,op,flags,ident,len(prefix)+len(payload))
                if op not in (old.RESET,old.METRICS):
                    with lock:counts['response_framing_bytes']+=len(packet)+len(prefix);counts['response_payload_bytes']+=len(payload)
                with write_lock:old.send_buffers(sock,[packet,prefix,payload])
            def response(op,ident,body):
                try:
                    # Independently scheduled readiness: one sleep per request,
                    # concurrent across requests, never one sleep per stream record.
                    if op not in (old.RESET,old.METRICS) and delay_ms:time.sleep(delay_ms/1000)
                    if faults.get('reorder') and op==old.BLOB and ident%2:time.sleep(0.01)
                    if op in (old.RESET,old.METRICS):
                        with lock:
                            if op==old.RESET:
                                for key in counts:counts[key]=0
                                payload=b'{}'
                            else:payload=t.encode(counts)
                        emit(op,1,ident,old.REPLY.pack(0,0,bytes(32),len(payload),0),payload);return
                    if op in (old.BATCH,STREAM):
                        keys=batch.parse_request(body)
                        if op==old.BATCH:
                            payload=batch.response(keys,content)
                            with lock:counts['batch_framing_bytes']+=batch.HEADER.size+40*len(keys)
                            # Whole-body control: record overhead remains payload.
                            emit(op,1,ident,old.REPLY.pack(0,1,bytes(32),len(payload),0),payload);return
                        total=0
                        for position,key in enumerate(keys):
                            payload=content.get('/blobs/sha256/'+key)
                            if payload is None:
                                emit(op,ERROR,ident,ERROR_BODY.pack(b'GASERR01',1));return
                            if faults.get('truncate-record')==position:
                                with write_lock:
                                    sock.sendall(header(op,DATA,ident,old.REPLY.size+len(payload))+old.REPLY.pack(0,1,bytes.fromhex(key),len(payload),0)+payload[:-1]);sock.shutdown(socket.SHUT_WR)
                                return
                            reply_key=('0'*64) if faults.get('wrong-record')==position else key
                            if faults.get('corrupt-record')==position and payload:payload=bytes([payload[0]^1])+payload[1:]
                            emit(op,DATA,ident,old.REPLY.pack(0,1,bytes.fromhex(reply_key),len(payload),0),payload);total+=len(payload)
                        if faults.get('missing-end'):sock.shutdown(socket.SHUT_WR);return
                        count=len(keys)+(1 if faults.get('wrong-end') else 0)
                        emit(op,END,ident,END_BODY.pack(b'GASEND01',count,total));return
                    if len(body)!=33 or body[0]!=1:return
                    key=body[1:];path=('/manifests/sha256/' if op==old.MANIFEST else '/blobs/sha256/')+key.hex()
                    status,headers,payload=t.resource_response(content,tags,path,{},{});tag=key if status==200 else bytes(32)
                    emit(op,1,ident,old.REPLY.pack(old.STATUS.get(status,5),1,tag,len(payload),0),payload)
                except (OSError,t.TransferError,ValueError):
                    try:sock.shutdown(socket.SHUT_RDWR)
                    except OSError:pass
                finally:slots.release()
            try:
                while True:
                    raw=old.receive(sock,old.HEADER.size,True)
                    if raw is None:break
                    magic,version,op,flags,ident,size=old.HEADER.unpack(raw)
                    if magic!=MAGIC or version!=VERSION or flags or ident!=next_id or op not in (1,2,4,STREAM,240,241) or size>old.MAX_REQUEST:break
                    expected={1:33,2:33,240:0,241:0}.get(op)
                    if expected is not None and size!=expected:break
                    body=old.receive(sock,size);next_id+=1
                    # No unbounded task queue: reader stops after eight requests.
                    slots.acquire()
                    if op not in (old.RESET,old.METRICS):
                        with lock:
                            counts['requests']+=1;counts['request_frame_bytes']+=old.HEADER.size+len(body);counts['manifest_requests']+=op==old.MANIFEST
                    futures=[future for future in futures if not future.done()];futures.append(pool.submit(response,op,ident,body))
            except (OSError,t.TransferError):pass
            finally:
                for future in futures:
                    try:future.result(timeout=12)
                    except Exception:pass
    class Server(socketserver.ThreadingMixIn,socketserver.TCPServer):
        daemon_threads=True;allow_reuse_address=True;request_queue_size=33
        def __init__(self,*args):self.slots=threading.BoundedSemaphore(33);super().__init__(*args)
        def process_request(self,request,address):
            if not self.slots.acquire(blocking=False):self.shutdown_request(request);return
            try:super().process_request(request,address)
            except BaseException:self.slots.release();raise
        def process_request_thread(self,request,address):
            try:super().process_request_thread(request,address)
            finally:self.slots.release()
    server=Server(('127.0.0.1',0),Handler);ready.send(server.server_address[1]);ready.close();server.serve_forever(poll_interval=0.05)


@contextmanager
def local_server(collection,delay_ms=0,faults=None):
    ctx=multiprocessing.get_context('spawn');reader,writer=ctx.Pipe(duplex=False)
    process=ctx.Process(target=_serve,args=(t.resources(collection),writer,delay_ms,faults or {}));process.start();writer.close()
    try:
        if not reader.poll(10):raise RuntimeError('pipeline server startup timeout')
        yield 'gaia-mux://127.0.0.1:'+str(reader.recv())
    finally:
        reader.close();process.terminate();process.join(timeout=5)
        if process.is_alive():process.kill();process.join()


class Client(old.Buffered):
    def __init__(self,url):
        super().__init__(url.replace('gaia-mux://','gaia-binary-buffered://',1));self.disposed=False;self.pending={};self.completions=[];self.peak_pending=0;self.peak_pending_bytes=0;self.reordered_completions=0
    def connect(self):
        if self.disposed:raise t.TransferError('connection disposed; create a new client')
        ident=threading.get_ident()
        if ident not in self.connections:
            sock=socket.create_connection((self.host,self.port),timeout=10);sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1);self.connections[ident]=[sock,1]
        return self.connections[ident]
    def reset_counts(self):self.requests=0;self.bytes=0;self.manifest_bytes=0;self.completions=[];self.peak_pending=0;self.peak_pending_bytes=0;self.reordered_completions=0
    def start(self,op,body,limit):
        sock,ident=self.connect()
        if len(body)>old.MAX_REQUEST or not 0<ident<1<<64 or len(self.pending)>=WINDOW:raise t.TransferError('pipeline request bound')
        sock.sendall(header(op,0,ident,len(body))+body);self.connections[threading.get_ident()][1]+=1
        self.pending[ident]=(op,limit);self.requests+=op not in (old.RESET,old.METRICS)
        self.peak_pending=max(self.peak_pending,len(self.pending));self.peak_pending_bytes=max(self.peak_pending_bytes,sum(value[1] for value in self.pending.values()))
        return ident
    def frame(self):
        sock,_=self.connect();magic,version,op,flags,ident,size=old.HEADER.unpack(self.receive(sock,old.HEADER.size))
        if magic!=MAGIC or version!=VERSION or ident not in self.pending or op!=self.pending[ident][0] or size>old.MAX_FRAME:raise t.TransferError('pipeline response correlation/header')
        return sock,op,flags,ident,size
    def complete(self,ident):
        self.reordered_completions+=ident!=min(self.pending);self.pending.pop(ident);self.completions.append(ident)
    def response(self):
        sock,op,flags,ident,size=self.frame();limit=self.pending[ident][1]
        if flags!=1 or size<old.REPLY.size or size>old.REPLY.size+limit:raise t.TransferError('pipeline response bound/type')
        status,algorithm,key,total,offset=old.REPLY.unpack(self.receive(sock,old.REPLY.size))
        if status not in old.HTTP_STATUS or algorithm!=(0 if op in (240,241) else 1) or offset or total!=size-old.REPLY.size or total>limit:raise t.TransferError('pipeline response descriptor')
        payload=self.receive(sock,total);self.bytes+=len(payload);self.manifest_bytes+=len(payload) if op==old.MANIFEST else 0;self.complete(ident)
        return ident,old.HTTP_STATUS[status],key,total,offset,payload
    def exchange(self,op,body,limit):
        ident=self.start(op,body,limit);actual,status,key,total,offset,payload=self.response()
        if actual!=ident:raise t.TransferError('unexpected response to serial request')
        return status,key,total,offset,payload
    def windowed(self,objects):
        completed=False
        try:
            pending={};next_object=0;pending_bytes=0
            while next_object<len(objects) or pending:
                while next_object<len(objects) and len(pending)<WINDOW:
                    obj=objects[next_object]
                    if pending and pending_bytes+obj['size']>BYTE_WINDOW:break
                    ident=self.start(old.BLOB,b'\x01'+bytes.fromhex(obj['sha256']),obj['size']);pending[ident]=obj;pending_bytes+=obj['size'];next_object+=1
                ident,status,key,_,_,payload=self.response()
                if ident not in pending:raise t.TransferError('unknown window completion')
                obj=pending.pop(ident);pending_bytes-=obj['size']
                if status!=200 or key.hex()!=obj['sha256']:raise t.TransferError('windowed blob status/identity')
                yield obj,payload
            completed=True
        finally:
            if not completed:self.close()
    def stream_batch(self,objects):
        completed=False
        try:
            ident=self.start(STREAM,batch.request([obj['sha256'] for obj in objects]),batch.MAX_RESPONSE);total=0
            for obj in objects:
                sock,op,flags,actual,size=self.frame()
                if actual!=ident:raise t.TransferError('stream response identity')
                if flags==ERROR:
                    if size!=ERROR_BODY.size:raise t.TransferError('stream error framing')
                    magic,code=ERROR_BODY.unpack(self.receive(sock,size));self.complete(ident)
                    if magic!=b'GASERR01' or code not in (1,2,3):raise t.TransferError('invalid stream error')
                    raise t.TransferError('stream server error')
                if flags!=DATA or size!=old.REPLY.size+obj['size']:raise t.TransferError('stream record length/type')
                status,algorithm,key,declared,offset=old.REPLY.unpack(self.receive(sock,old.REPLY.size))
                if status or algorithm!=1 or key.hex()!=obj['sha256'] or declared!=obj['size'] or offset:raise t.TransferError('stream record identity/descriptor')
                payload=self.receive(sock,obj['size']);self.bytes+=len(payload);total+=len(payload);yield obj,payload
            sock,op,flags,actual,size=self.frame()
            if actual!=ident or flags!=END or size!=END_BODY.size:raise t.TransferError('missing stream end')
            magic,count,declared=END_BODY.unpack(self.receive(sock,size))
            if magic!=b'GASEND01' or count!=len(objects) or declared!=total:raise t.TransferError('stream end totals')
            self.complete(ident)
            completed=True
        finally:
            if not completed:self.close()
    def close(self):
        self.disposed=True;self.pending.clear();super().close()

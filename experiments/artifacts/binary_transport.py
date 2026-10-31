"""Versioned bounded loopback framing experiment; no public-protocol claim."""
from contextlib import contextmanager
import multiprocessing
import re
import socket
import socketserver
import struct
import threading
import time
from urllib.parse import urlsplit

import batch
import transfer as t

MAGIC=b'GAF1'
VERSION=1
RESPONSE=1
HEADER=struct.Struct('!4sBBHQQ')  # magic, version, opcode, flags, request ID, body length
REPLY=struct.Struct('!BB32sQQ')   # status, algorithm, digest, representation size, offset
MANIFEST,BLOB,RANGE,BATCH=1,2,3,4
RESET,METRICS=240,241
OPS={MANIFEST,BLOB,RANGE,BATCH,RESET,METRICS}
MAX_CONNECTIONS=33  # 32 payload workers plus the metadata connection
MAX_REQUEST=batch.MAX_REQUEST
MAX_FRAME=REPLY.size+batch.MAX_RESPONSE
HTTP_STATUS={0:200,1:206,2:404,3:412,4:416,5:400}
STATUS={v:k for k,v in HTTP_STATUS.items()}


def receive(sock,size,eof_ok=False):
    if size<0 or size>MAX_FRAME:raise t.TransferError('binary allocation bound')
    data=bytearray(size);view=memoryview(data);offset=0
    while offset<size:
        count=sock.recv_into(view[offset:])
        if not count:
            if offset==0 and eof_ok:return None
            raise t.TransferError('binary truncated stream')
        offset+=count
    return bytes(data)


def request_header(body,opcode,request_id):
    if opcode not in OPS or not 0<request_id<1<<64 or len(body)>MAX_REQUEST:raise t.TransferError('binary request bounds')
    return HEADER.pack(MAGIC,VERSION,opcode,0,request_id,len(body))


def send_buffers(sock,buffers):
    """Send bounded vectors without concatenating the response payload."""
    pending=[memoryview(body) for body in buffers if len(body)]
    if not hasattr(sock,'sendmsg'):
        for body in pending:sock.sendall(body)
        return
    while pending:
        count=sock.sendmsg(pending)
        if count<=0:raise OSError('binary send made no progress')
        while pending and count>=len(pending[0]):count-=len(pending.pop(0))
        if pending and count:pending[0]=pending[0][count:]


def _serve(content,ready,delay_ms,faults,buffered=False):
    counts=dict(requests=0,response_payload_bytes=0,manifest_requests=0,range_requests=0,
                request_frame_bytes=0,response_framing_bytes=0,batch_framing_bytes=0)
    lock=threading.Lock();tags={path:'"sha256:'+t.digest(body)+'"' for path,body in content.items()}
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            sock=self.request;sock.settimeout(10);sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1);next_id=1
            try:
                while True:
                    raw=receive(sock,HEADER.size,True)
                    if raw is None:return
                    magic,version,op,flags,ident,size=HEADER.unpack(raw)
                    if magic!=MAGIC or version!=VERSION or op not in OPS or flags or ident!=next_id or size>MAX_REQUEST:return
                    expected={MANIFEST:33,BLOB:33,RANGE:49,RESET:0,METRICS:0}.get(op)
                    if (expected is not None and size!=expected) or (op==BATCH and size<batch.HEADER.size):return
                    body=receive(sock,size);next_id+=1
                    headers={};path='';batch_overhead=0;algorithm=0;key=bytes(32);offset=0;total=0
                    if op in (RESET,METRICS):
                        if body:return
                        if op==RESET:
                            with lock:
                                for field in counts:counts[field]=0
                            payload=b'{}'
                        else:
                            with lock:payload=t.encode(counts)
                        status=200;total=len(payload)
                    elif op==BATCH:
                        path='/batch/sha256';algorithm=1
                        try:
                            keys=batch.parse_request(body);payload=batch.response(keys,content)
                        except (t.TransferError,KeyError):return
                        batch_overhead=batch.HEADER.size+40*len(keys);status=200;total=len(payload)
                        if delay_ms:time.sleep(delay_ms/1000)
                        if faults.get(path)=='corrupt' and payload:payload=payload[:-1]+bytes([payload[-1]^1])
                        if faults.get(path)=='bad-record-id' and len(payload)>batch.HEADER.size:
                            at=batch.HEADER.size;payload=payload[:at]+bytes([payload[at]^1])+payload[at+1:]
                    else:
                        expected=49 if op==RANGE else 33
                        if len(body)!=expected or body[0]!=1:return
                        algorithm=1;key=body[1:33];path=('/manifests/sha256/' if op==MANIFEST else '/blobs/sha256/')+key.hex()
                        request_headers={}
                        if op==RANGE:
                            start,end=struct.unpack_from('!QQ',body,33)
                            if start>end:return
                            request_headers={'Range':f'bytes={start}-{end}','If-Match':'"sha256:'+key.hex()+'"'}
                        if delay_ms:time.sleep(delay_ms/1000)
                        status,headers,payload=t.resource_response(content,tags,path,request_headers,faults)
                        if 'ETag' in headers:
                            value=headers['ETag'].strip('"').removeprefix('sha256:')
                            key=bytes.fromhex(value) if t.HEX.fullmatch(value) else bytes(32)
                        total=len(content.get(path,b''))
                        if status==206:
                            match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',headers.get('Content-Range',''))
                            if not match:return
                            offset=int(match[1]);total=int(match[3])
                        if headers.get('Content-Encoding'):algorithm=2  # unsupported representation in fault tests
                    fault=faults.get(path)
                    fixed=REPLY.pack(STATUS.get(status,5),algorithm,key,total,offset)
                    packet=HEADER.pack(MAGIC,2 if fault=='wrong-version' else VERSION,
                        BLOB if fault=='wrong-opcode' and op!=BLOB else MANIFEST if fault=='wrong-opcode' else op,
                        RESPONSE,ident+1 if fault=='wrong-request-id' else ident,
                        MAX_FRAME+1 if fault=='huge-length' else len(fixed)+len(payload))
                    if op not in (RESET,METRICS):
                        with lock:
                            counts['requests']+=1;counts['response_payload_bytes']+=len(payload)-(1 if fault=='truncated' and payload else 0)
                            counts['manifest_requests']+=op==MANIFEST;counts['range_requests']+=op==RANGE
                            counts['request_frame_bytes']+=HEADER.size+len(body);counts['response_framing_bytes']+=HEADER.size+REPLY.size
                            counts['batch_framing_bytes']+=batch_overhead
                    if fault=='truncated-header':sock.sendall(packet[:12]);return
                    if fault in ('huge-length','wrong-version','wrong-opcode','wrong-request-id'):
                        sock.sendall(packet+fixed);return
                    if fault=='truncated' and payload:
                        sock.sendall(packet+fixed);sock.sendall(payload[:-1]);return
                    if buffered:send_buffers(sock,[packet+fixed,payload])
                    else:sock.sendall(packet+fixed);sock.sendall(payload)
            except (OSError,t.TransferError,ValueError,struct.error):return
    class Server(socketserver.ThreadingMixIn,socketserver.TCPServer):
        daemon_threads=True;allow_reuse_address=True;request_queue_size=MAX_CONNECTIONS
        def __init__(self,*args):self.slots=threading.BoundedSemaphore(MAX_CONNECTIONS);super().__init__(*args)
        def process_request(self,request,address):
            if not self.slots.acquire(blocking=False):self.shutdown_request(request);return
            try:super().process_request(request,address)
            except BaseException:self.slots.release();raise
        def process_request_thread(self,request,address):
            try:super().process_request_thread(request,address)
            finally:self.slots.release()
    server=Server(('127.0.0.1',0),Handler);ready.send(server.server_address[1]);ready.close();server.serve_forever(poll_interval=0.05)


@contextmanager
def local_server(collection,delay_ms=0,faults=None,buffered=False):
    ctx=multiprocessing.get_context('spawn');reader,writer=ctx.Pipe(duplex=False)
    process=ctx.Process(target=_serve,args=(t.resources(collection),writer,delay_ms,faults or {},buffered));process.start();writer.close()
    try:
        if not reader.poll(10):raise RuntimeError('binary server startup timeout')
        yield ('gaia-binary-buffered' if buffered else 'gaia-binary')+'://127.0.0.1:'+str(reader.recv())
    finally:
        reader.close();process.terminate();process.join(timeout=5)
        if process.is_alive():process.kill();process.join()


class Binary:
    def __init__(self,url):
        parsed=urlsplit(url)
        if parsed.scheme!='gaia-binary' or parsed.path not in ('','/') or parsed.username or parsed.password or not parsed.hostname:
            raise t.TransferError('binary experiment origin')
        self.host=parsed.hostname;self.port=parsed.port;self.connections={};self.lock=threading.Lock()
        self.requests=0;self.bytes=0;self.manifest_bytes=0
    def receive(self,sock,size,eof_ok=False):return receive(sock,size,eof_ok)
    def exchange(self,op,body,limit):
        ident=threading.get_ident()
        if ident not in self.connections:
            sock=socket.create_connection((self.host,self.port),timeout=10);sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            self.connections[ident]=[sock,1]
        entry=self.connections[ident];sock,request_id=entry
        try:
            sock.sendall(request_header(body,op,request_id)+body);entry[1]+=1
            magic,version,reply_op,flags,reply_id,size=HEADER.unpack(self.receive(sock,HEADER.size))
            if (magic!=MAGIC or version!=VERSION or reply_op!=op or flags!=RESPONSE or reply_id!=request_id or
                size<REPLY.size or size>MAX_FRAME or size>REPLY.size+limit):raise t.TransferError('binary response header/version/identity/bound')
            status,algorithm,key,total,offset=REPLY.unpack(self.receive(sock,REPLY.size))
            expected_algorithm=0 if op in (RESET,METRICS) else 1
            if status not in HTTP_STATUS or algorithm!=expected_algorithm:raise t.TransferError('binary response status/algorithm')
            payload_size=size-REPLY.size
            if offset>total or payload_size>total-offset:raise t.TransferError('binary response geometry')
            if op!=RANGE and offset:raise t.TransferError('binary unexpected offset')
            if status==0 and payload_size!=total:raise t.TransferError('binary complete-response size')
            if total>(batch.MAX_RESPONSE if op==BATCH else t.MAX_MANIFEST if op in (RESET,METRICS,MANIFEST) else t.MAX_PACK):
                raise t.TransferError('binary representation bound')
            payload=self.receive(sock,payload_size)
            with self.lock:
                self.requests+=1;self.bytes+=len(payload)
                if op==MANIFEST:self.manifest_bytes+=len(payload)
            return HTTP_STATUS[status],key,total,offset,payload
        except (OSError,t.TransferError,ValueError,struct.error) as error:
            sock.close();raise t.TransferError('binary transfer failed') from error
    def get(self,path,limit,headers=None):
        headers=headers or {}
        if path in ('/control/reset','/control/metrics'):
            op=RESET if path.endswith('reset') else METRICS;request=b''
        else:
            match=re.fullmatch(r'/(manifests|blobs)/sha256/([0-9a-f]{64})',path)
            if not match:raise t.TransferError('binary resource identity')
            op=MANIFEST if match[1]=='manifests' else RANGE if 'Range' in headers else BLOB
            request=b'\x01'+bytes.fromhex(match[2])
            if op==RANGE:
                interval=re.fullmatch(r'bytes=(\d+)-(\d+)',headers['Range'])
                if not interval or headers.get('If-Match')!='"sha256:'+match[2]+'"':raise t.TransferError('binary range request')
                request+=struct.pack('!QQ',*map(int,interval.groups()))
        status,key,total,offset,payload=self.exchange(op,request,limit)
        response_headers={}
        if op not in (RESET,METRICS):response_headers['etag']='"sha256:'+key.hex()+'"'
        if status==206:response_headers['content-range']=f'bytes {offset}-{offset+len(payload)-1}/{total}'
        return status,response_headers,payload
    def batch(self,objects):
        body=batch.request([obj['sha256'] for obj in objects]);limit=batch.HEADER.size+40*len(objects)+sum(obj['size'] for obj in objects)
        status,key,_,_,payload=self.exchange(BATCH,body,limit)
        if status!=200 or key!=bytes(32):raise t.TransferError('binary batch status/identity')
        return payload
    def close(self):
        for sock,_ in self.connections.values():sock.close()


class Buffered(Binary):
    """Owned result bytes via a bounded buffered reader, with no full-body copy."""
    def __init__(self,url):
        super().__init__(url.replace('gaia-binary-buffered://','gaia-binary://',1));self.readers={}
    def receive(self,sock,size,eof_ok=False):
        if size<0 or size>MAX_FRAME:raise t.TransferError('binary allocation bound')
        if sock not in self.readers:self.readers[sock]=sock.makefile('rb',buffering=65536)
        body=self.readers[sock].read(size)
        if len(body)!=size:
            if not body and eof_ok:return None
            raise t.TransferError('buffered binary truncated stream')
        return body
    def close(self):
        for reader in self.readers.values():reader.close()
        super().close()

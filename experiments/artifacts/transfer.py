"""Bounded, metadata-first HTTP experiment; this is not a public Gaia protocol."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import multiprocessing
import os
from pathlib import Path
import re
import socket
import tempfile
import threading
import time
from urllib.parse import urlsplit

MAX_MANIFEST=4*1024*1024
MAX_PACK=64*1024*1024
MAX_OBJECTS=16384
MODES=('objects-serial','objects-parallel','pack-exact','pack-coalesced','pack-full','selected-batch')
PIPELINE_MODES=('objects-windowed','stream-batch')
HEX=re.compile(r'[0-9a-f]{64}\Z')


class TransferError(ValueError):pass


def digest(body):return hashlib.sha256(body).hexdigest()


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()


def atomic_write(path,body):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.tmp.',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(body)
        os.replace(name,path)
    finally:Path(name).unlink(missing_ok=True)


def build_collection(payloads):
    unique={digest(body):body for body in payloads}
    if not unique or len(unique)>MAX_OBJECTS:raise TransferError('object count')
    objects=[];offset=0;parts=[]
    for key,body in sorted(unique.items()):
        objects.append(dict(sha256=key,size=len(body),offset=offset));offset+=len(body);parts.append(body)
    pack=b''.join(parts)
    if len(pack)>MAX_PACK:raise TransferError('pack limit')
    manifest=encode(dict(version=1,digest_algorithm='sha256',pack=dict(sha256=digest(pack),size=len(pack)),objects=objects))
    if len(manifest)>MAX_MANIFEST:raise TransferError('manifest limit')
    return dict(manifest=manifest,manifest_id=digest(manifest),pack=pack,pack_id=digest(pack),objects=unique)


def _pairs(items):
    result={}
    for key,value in items:
        if key in result:raise TransferError('duplicate JSON member')
        result[key]=value
    return result


def parse_manifest(body):
    if len(body)>MAX_MANIFEST:raise TransferError('manifest limit')
    try:value=json.loads(body,object_pairs_hook=_pairs)
    except (ValueError,UnicodeError) as error:raise TransferError('manifest JSON') from error
    if not isinstance(value,dict) or set(value)!={'version','digest_algorithm','pack','objects'} or type(value['version']) is not int or value['version']!=1 or value['digest_algorithm']!='sha256':
        raise TransferError('manifest schema/version')
    pack=value['pack'];objects=value['objects']
    if not isinstance(pack,dict) or set(pack)!={'sha256','size'} or not isinstance(pack['sha256'],str) or not HEX.fullmatch(pack['sha256']):raise TransferError('pack descriptor')
    if type(pack['size']) is not int or not 0<=pack['size']<=MAX_PACK:raise TransferError('pack size')
    if not isinstance(objects,list) or not 0<len(objects)<=MAX_OBJECTS:raise TransferError('object count')
    seen=set();offset=0
    for obj in objects:
        if not isinstance(obj,dict) or set(obj)!={'sha256','size','offset'}:raise TransferError('object schema')
        key=obj['sha256']
        if not isinstance(key,str) or not HEX.fullmatch(key) or key in seen:raise TransferError('object identity')
        if type(obj['size']) is not int or not 0<=obj['size']<=MAX_PACK or type(obj['offset']) is not int or obj['offset']!=offset:raise TransferError('object geometry')
        seen.add(key);offset+=obj['size']
        if offset>pack['size']:raise TransferError('pack bounds')
    if offset!=pack['size']:raise TransferError('pack coverage')
    return value


def resources(collection):
    return {f'/blobs/sha256/{key}':body for key,body in collection['objects'].items()}|{
        f'/blobs/sha256/{collection["pack_id"]}':collection['pack'],
        f'/manifests/sha256/{collection["manifest_id"]}':collection['manifest']}


def resource_response(content,tags,path,request_headers,faults):
    body=content.get(path);status=200;headers={};fault=faults.get(path)
    if body is None:return 404,headers,b''
    tag=tags[path];headers=dict(ETag=tag,**{'Accept-Ranges':'bytes','Content-Type':'application/octet-stream'})
    if request_headers.get('If-Match') not in (None,tag):body=b'';status=412
    elif request_headers.get('Range') and fault!='ignore-range':
        match=re.fullmatch(r'bytes=(\d+)-(\d+)',request_headers['Range'])
        if not match or int(match[1])>int(match[2]) or int(match[2])>=len(body):
            headers['Content-Range']=f'bytes */{len(body)}';body=b'';status=416
        else:
            start,end=map(int,match.groups());headers['Content-Range']=f'bytes {start}-{end}/{len(body)}'
            body=body[start:end+1];status=206
    if fault=='corrupt' and body:body=bytes([body[0]^1])+body[1:]
    if fault=='wrong-etag':headers['ETag']='"'+('0'*64)+'"'
    if fault=='wrong-range' and status==206:headers['Content-Range']='bytes 0-0/1'
    if fault=='encoded':headers['Content-Encoding']='gzip'
    return status,headers,body


def _serve(content,ready,delay_ms,faults):
    import batch
    counts=dict(requests=0,response_payload_bytes=0,manifest_requests=0,range_requests=0,
                request_frame_bytes=0,response_framing_bytes=0,batch_framing_bytes=0)
    lock=threading.Lock();tags={path:'"sha256:'+digest(body)+'"' for path,body in content.items()}
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'
        def setup(self):
            super().setup();self.connection.settimeout(10);self.connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
        def log_message(self,*args):pass
        def send_body(self,status,headers,body,counted,request_size=0,batch_overhead=0):
            fault=faults.get(self.path)
            self.send_response(status)
            for key,value in headers.items():self.send_header(key,value)
            self.send_header('Content-Length',str(len(body)))
            if fault=='truncated':self.send_header('Connection','close')
            framing=sum(map(len,self._headers_buffer))+2
            if counted:
                request_framing=len(self.raw_requestline)+2+sum(len(k)+2+len(v)+2 for k,v in self.headers.items())
                with lock:
                    counts['requests']+=1;counts['response_payload_bytes']+=len(body)-(1 if fault=='truncated' and body else 0)
                    counts['manifest_requests']+=self.path.startswith('/manifests/')
                    counts['range_requests']+=bool(self.headers.get('Range'))
                    counts['request_frame_bytes']+=request_framing+request_size;counts['response_framing_bytes']+=framing
                    counts['batch_framing_bytes']+=batch_overhead
            self.end_headers()
            if fault=='truncated' and body:self.wfile.write(body[:-1]);self.close_connection=True
            else:self.wfile.write(body)
        def do_GET(self):
            if self.path=='/control/reset':
                with lock:
                    for key in counts:counts[key]=0
                self.send_body(200,{},b'{}',False);return
            if self.path=='/control/metrics':
                with lock:body=encode(counts)
                self.send_body(200,{},body,False);return
            if delay_ms:time.sleep(delay_ms/1000)
            status,headers,body=resource_response(content,tags,self.path,self.headers,faults)
            self.send_body(status,headers,body,True)
        def do_POST(self):
            if self.path!='/batch/sha256':self.send_body(404,{},b'',False);return
            if delay_ms:time.sleep(delay_ms/1000)
            length=self.headers.get('Content-Length','')
            if not length.isdecimal() or not 0<int(length)<=batch.MAX_REQUEST:
                self.send_body(400,{},b'',False);self.close_connection=True;return
            try:
                request=self.rfile.read(int(length));keys=batch.parse_request(request);body=batch.response(keys,content)
            except (TransferError,KeyError):self.send_body(400,{},b'',True,int(length));return
            if faults.get(self.path)=='corrupt' and body:body=body[:-1]+bytes([body[-1]^1])
            self.send_body(200,{'Content-Type':'application/octet-stream'},body,True,len(request),batch.HEADER.size+40*len(keys))
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.daemon_threads=True
    ready.send(server.server_address[1]);ready.close();server.serve_forever(poll_interval=0.05)


@contextmanager
def local_server(collection,delay_ms=0,faults=None):
    ctx=multiprocessing.get_context('spawn');reader,writer=ctx.Pipe(duplex=False)
    process=ctx.Process(target=_serve,args=(resources(collection),writer,delay_ms,faults or {}));process.start();writer.close()
    try:
        if not reader.poll(10):raise RuntimeError('server startup timeout')
        yield 'http://127.0.0.1:'+str(reader.recv())
    finally:
        reader.close();process.terminate();process.join(timeout=5)
        if process.is_alive():process.kill();process.join()


class HTTP:
    def __init__(self,url):
        parsed=urlsplit(url)
        if parsed.scheme!='http' or parsed.path not in ('','/') or parsed.username or parsed.password or not parsed.hostname:
            raise TransferError('loopback experiment requires plain HTTP origin')
        self.host=parsed.hostname;self.port=parsed.port;self.connections={};self.lock=threading.Lock()
        self.requests=0;self.bytes=0;self.manifest_bytes=0
    def request(self,method,path,limit,headers=None,request_body=None):
        ident=threading.get_ident()
        if ident not in self.connections:
            connection=http.client.HTTPConnection(self.host,self.port,timeout=10);connection.connect()
            connection.sock.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1);self.connections[ident]=connection
        connection=self.connections[ident]
        try:
            connection.request(method,path,body=request_body,headers={'Accept-Encoding':'identity',**(headers or {})});response=connection.getresponse()
            length=response.getheader('Content-Length')
            if length is None or not length.isdecimal() or int(length)>limit:raise TransferError('response size/framing')
            if response.getheader('Content-Encoding') not in (None,'identity'):raise TransferError('encoded range representation')
            body=response.read(limit+1)
            if len(body)!=int(length):raise TransferError('truncated response')
            with self.lock:
                self.requests+=1;self.bytes+=len(body)
                if path.startswith('/manifests/'):self.manifest_bytes+=len(body)
            return response.status,dict((k.lower(),v) for k,v in response.getheaders()),body
        except (OSError,http.client.HTTPException) as error:
            connection.close();raise TransferError('HTTP transfer failed') from error
    def get(self,path,limit,headers=None):return self.request('GET',path,limit,headers)
    def batch(self,objects):
        import batch
        request=batch.request([obj['sha256'] for obj in objects])
        limit=batch.HEADER.size+40*len(objects)+sum(obj['size'] for obj in objects)
        status,_,body=self.request('POST','/batch/sha256',limit,{'Content-Type':'application/octet-stream'},request)
        if status!=200:raise TransferError('HTTP batch status')
        return body
    def close(self):
        for connection in self.connections.values():connection.close()


def control(url,action):
    http=transport(url)
    try:
        status,_,body=http.get('/control/'+action,MAX_MANIFEST)
        if status!=200:raise TransferError('control failed')
        return json.loads(body)
    finally:http.close()


def _cached(path,size,key):
    try:
        with path.open('rb') as stream:
            if os.fstat(stream.fileno()).st_size!=size:return None,0
            body=stream.read(size+1)
        return (body if len(body)==size and digest(body)==key else None),len(body)
    except FileNotFoundError:return None,0


def coalesce(objects,gap,max_span):
    if gap<0 or max_span<=0:raise TransferError('range budget')
    result=[]
    for obj in sorted(objects,key=lambda o:o['offset']):
        if obj['size']==0:continue
        start=obj['offset'];end=start+obj['size']-1
        if result and start-result[-1][1]-1<=gap and end-result[-1][0]+1<=max_span:
            result[-1][1]=end;result[-1][2].append(obj)
        else:result.append([start,end,[obj]])
    return result


def fetch(url,manifest_id,manifest_size,wanted,cache,mode,workers=8,gap=65536,max_span=4*1024*1024,storage='files',client=None,verified_callback=None):
    """Time outside this call too if measuring process/library startup."""
    if mode not in MODES+PIPELINE_MODES or not 1<=workers<=32 or not HEX.fullmatch(manifest_id) or not 0<manifest_size<=MAX_MANIFEST:
        raise TransferError('request bounds/mode')
    from cache_store import make
    begin=time.perf_counter();cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    (cache/'ready.json').unlink(missing_ok=True)
    http=None;store=None;first_new_verified=None;metadata_fetched=False;batch_framing=0;published=0;published_keys=set();hash_bytes=0;cached=0;fallback=False
    try:
        store=make(cache,storage);http=client if client is not None else transport(url)
        metadata=cache/('sha256-'+manifest_id+'.manifest');body,hashed=_cached(metadata,manifest_size,manifest_id);hash_bytes+=hashed
        if body is None:
            status,_,body=http.get('/manifests/sha256/'+manifest_id,manifest_size)
            if status!=200 or len(body)!=manifest_size or digest(body)!=manifest_id:raise TransferError('manifest integrity/status')
            hash_bytes+=len(body)
            manifest=parse_manifest(body);atomic_write(metadata,body);metadata_fetched=True
        else:manifest=parse_manifest(body)
        metadata_end=time.perf_counter()
        objects={obj['sha256']:obj for obj in manifest['objects']}
        wanted=list(wanted)
        if len(wanted)>MAX_OBJECTS or len(wanted)!=len(set(wanted)) or any(key not in objects for key in wanted):raise TransferError('unknown/duplicate requested object')
        available=set()
        for key,known in store.iter_available([objects[key] for key in wanted]):
            hash_bytes+=len(known)
            if digest(known)==key:available.add(key)
            else:store.invalidate(key)
        known=None;cached=len(available);missing=[objects[key] for key in wanted if key not in available]
        for obj in missing:store.invalidate(obj['sha256'])
        store.prepare(missing)
        cache_end=time.perf_counter();missing_bytes=sum(obj['size'] for obj in missing)
        def publish(obj,payload):
            nonlocal published,hash_bytes,first_new_verified
            if len(payload)!=obj['size'] or digest(payload)!=obj['sha256']:raise TransferError('object integrity')
            if first_new_verified is None:first_new_verified=time.perf_counter()-begin
            if verified_callback is not None:verified_callback(obj,memoryview(payload))
            with http.lock:
                hash_bytes+=len(payload)
                if obj['sha256'] in published_keys:return
                published_keys.add(obj['sha256'])
            store.put_verified(obj,payload)
            with http.lock:published+=1
        def single(obj):
            status,headers,payload=http.get('/blobs/sha256/'+obj['sha256'],obj['size'])
            if status!=200:raise TransferError('object status')
            publish(obj,payload)
        if mode in ('objects-windowed','stream-batch') and missing:
            method=http.windowed if mode=='objects-windowed' else http.stream_batch
            for obj,body in method(missing):publish(obj,body)
        elif mode.startswith('objects-'):
            if mode=='objects-parallel' and missing:
                with ThreadPoolExecutor(max_workers=workers) as pool:list(pool.map(single,missing))
            else:
                for obj in missing:single(obj)
        elif mode=='selected-batch' and missing:
            import batch
            payload=http.batch(missing);items=batch.parse_response(payload,missing)
            batch_framing=len(payload)-sum(obj['size'] for obj in missing)
            for obj,body in items:publish(obj,body)
        elif missing:
            pack=manifest['pack'];tag='"sha256:'+pack['sha256']+'"';path='/blobs/sha256/'+pack['sha256']
            def entire(payload):
                nonlocal hash_bytes
                if len(payload)!=pack['size'] or digest(payload)!=pack['sha256']:raise TransferError('pack integrity')
                hash_bytes+=len(payload)
                for obj in missing:publish(obj,payload[obj['offset']:obj['offset']+obj['size']])
            if mode=='pack-full':
                status,headers,payload=http.get(path,pack['size'],{'If-Match':tag})
                if status!=200 or headers.get('etag')!=tag:raise TransferError('pack status/validator')
                entire(payload)
            else:
                for obj in missing:
                    if obj['size']==0:publish(obj,b'')
                ranges=coalesce(missing,0 if mode=='pack-exact' else gap,1 if mode=='pack-exact' else max_span)
                for start,end,members in ranges:
                    status,headers,payload=http.get(path,pack['size'],{'Range':f'bytes={start}-{end}','If-Match':tag})
                    if headers.get('etag')!=tag:raise TransferError('range validator')
                    if status==200:
                        entire(payload);fallback=True;break
                    if status!=206 or headers.get('content-range')!=f'bytes {start}-{end}/{pack["size"]}' or len(payload)!=end-start+1:
                        raise TransferError('range status/geometry')
                    for obj in members:publish(obj,payload[obj['offset']-start:obj['offset']-start+obj['size']])
        store.finish();payload_end=time.perf_counter()
        receipt=encode(dict(version=1,manifest='sha256:'+manifest_id,objects=['sha256:'+key for key in sorted(wanted)]))
        atomic_write(cache/'ready.json',receipt)
        receipt_end=time.perf_counter()
    except BaseException:
        if http is not None:http.close()
        if store is not None:store.abort()
        raise
    finally:
        if http is not None and client is None:http.close()
        if store is not None:store.close()
    end=time.perf_counter()
    return dict(seconds=end-begin,metadata_seconds=metadata_end-begin,cache_validation_seconds=cache_end-metadata_end,
                payload_verify_publish_seconds=payload_end-cache_end,receipt_seconds=receipt_end-payload_end,
                requests=http.requests,response_payload_bytes=http.bytes,manifest_bytes=http.manifest_bytes,
                transfer_bytes=http.bytes-http.manifest_bytes-batch_framing,missing_bytes=missing_bytes,batch_framing_bytes=batch_framing,
                overfetch_bytes=http.bytes-http.manifest_bytes-batch_framing-missing_bytes,hash_bytes=hash_bytes,
                cache_hits=cached,published_objects=published,connections=len(http.connections),full_pack_fallback=fallback,storage=storage,
                store=store.stats.copy(),atomic_publications=store.stats['atomic_publications']+int(metadata_fetched)+1,
                first_new_verified_seconds=first_new_verified,publication_bytes=store.stats['data_write_bytes']+store.stats['metadata_write_bytes']+(manifest_size if metadata_fetched else 0)+len(receipt))


def transport(url):
    if url.startswith('gaia-mux://'):
        from pipeline_transport import Client
        return Client(url)
    if url.startswith('gaia-binary-buffered://'):
        from binary_transport import Buffered
        return Buffered(url)
    if url.startswith('gaia-binary://'):
        from binary_transport import Binary
        return Binary(url)
    return HTTP(url)

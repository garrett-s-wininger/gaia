"""Actual loopback HTTP/binary delivery with explicit application-service models."""
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import argparse,hashlib,http.client,http.server,json,random,socket,socketserver,statistics,struct,threading,time
from pathlib import Path
from common import HERE,digest,measured,pins,publish,read_corpus

U32=struct.Struct('!I');U64=struct.Struct('!Q');MAX=32*1024*1024
def recv(stream,n):
    out=bytearray()
    while len(out)<n:
        part=stream.recv(n-len(out))
        if not part:raise EOFError('truncated frame')
        out.extend(part)
    return bytes(out)
def request_bytes(ids):return U32.pack(len(ids))+b''.join(bytes.fromhex(key) for key in ids)
def parse_request(body):
    if len(body)<4:raise ValueError('request header')
    count=U32.unpack_from(body)[0]
    if not 1<=count<=64 or len(body)!=4+count*32:raise ValueError('request geometry')
    return [body[4+i*32:36+i*32].hex() for i in range(count)]
def encode_response(ids,objects):return U32.pack(len(ids))+b''.join(U64.pack(len(objects[key]))+objects[key] for key in ids)
def parse_response(body,ids):
    if len(body)<4 or U32.unpack_from(body)[0]!=len(ids):raise ValueError('response count')
    at=4;out=[]
    for key in ids:
        if at+8>len(body):raise ValueError('response length')
        size=U64.unpack_from(body,at)[0];at+=8
        if size>MAX or at+size>len(body):raise ValueError('response bounds')
        value=body[at:at+size];at+=size
        if digest(value)!=key:raise ValueError('content pin mismatch')
        out.append((key,value))
    if at!=len(body):raise ValueError('trailing bytes')
    return out

class Service:
    def __init__(self,objects):self.objects=objects;self.lock=threading.Lock();self.reset('nominal')
    def reset(self,profile):
        self.profile=profile;self.next_free=time.perf_counter();self.requests=0;self.request_bytes=0;self.response_bytes=0;self.rows=[]
    def handle(self,body):
        ids=parse_request(body)
        if any(key not in self.objects for key in ids):raise ValueError('unknown object')
        response=encode_response(ids,self.objects);now=time.perf_counter()
        with self.lock:
            number=self.requests;self.requests+=1;self.request_bytes+=len(body);self.response_bytes+=len(response)
            if self.profile=='nominal':latency=0;bandwidth=float('inf')
            elif self.profile=='latency':latency=.005;bandwidth=64*1024*1024
            elif self.profile=='bandwidth':latency=.001;bandwidth=8*1024*1024
            else:latency=.005 if number<8 else .001;bandwidth=(64 if number<8 else 8)*1024*1024
            begin=max(now+latency,self.next_free);end=begin+len(response)/bandwidth;self.next_free=end
            self.rows.append({'number':number,'bytes':len(response),'modeled_queue_seconds':max(0,begin-now-latency),'latency_seconds':latency,'bandwidth':bandwidth if bandwidth!=float('inf') else None})
        time.sleep(max(0,end-time.perf_counter()));return response

class HTTP(http.server.ThreadingHTTPServer):daemon_threads=True
class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def setup(self):
        super().setup();self.connection.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
    def log_message(self,*args):pass
    def do_POST(self):
        try:
            count=int(self.headers.get('Content-Length','-1'))
            if not 0<count<=4096:raise ValueError('request bound')
            body=self.rfile.read(count)
            if len(body)!=count:raise ValueError('request truncated')
            result=self.server.service.handle(body)
            self.send_response(200);self.send_header('Content-Length',str(len(result)));self.end_headers();self.wfile.write(result)
        except (ValueError,OSError):self.send_error(400)

class Binary(socketserver.ThreadingTCPServer):allow_reuse_address=True;daemon_threads=True
class BinaryHandler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(30)
        self.request.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
        try:
            while True:
                n=U32.unpack(recv(self.request,4))[0]
                if not 0<n<=4096:raise ValueError('request bound')
                body=recv(self.request,n);result=self.server.service.handle(body);self.request.sendall(U64.pack(len(result))+result)
        except (EOFError,OSError,ValueError):return

class Client:
    def __init__(self,protocol,address):
        self.protocol=protocol
        self.connection=http.client.HTTPConnection(*address,timeout=30) if protocol=='http' else socket.create_connection(address,timeout=30)
    def query(self,ids):
        body=request_bytes(ids)
        if self.protocol=='http':
            self.connection.request('POST','/batch',body,{'Content-Type':'application/octet-stream'});response=self.connection.getresponse()
            if response.status!=200:raise ValueError('HTTP status')
            data=response.read()
        else:
            self.connection.sendall(U32.pack(len(body))+body);n=U64.unpack(recv(self.connection,8))[0]
            if n>MAX:raise ValueError('response bound')
            data=recv(self.connection,n)
        return parse_response(data,ids)
    def close(self):self.connection.close()

def acquire(protocol,address,ids,objects,window,batch,adaptive=False,budget=4*1024*1024):
    start=time.perf_counter();pending=[ids[i:i+batch] for i in range(0,len(ids),batch)];index=0;inflight={};reserved=peak=0;local=threading.local();clients=[];lock=threading.Lock();received={};first=None;windows=[];ema=None;completed=0
    def fetch(group):
        if not hasattr(local,'client'):
            local.client=Client(protocol,address)
            with lock:clients.append(local.client)
        began=time.perf_counter();values=local.client.query(group);return values,time.perf_counter()-began
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            while index<len(pending) or inflight:
                while index<len(pending) and len(inflight)<window:
                    group=pending[index];size=sum(len(objects[key]) for key in group)
                    if size>budget:raise ValueError('batch exceeds budget')
                    if reserved+size>budget:break
                    future=pool.submit(fetch,group);inflight[future]=size;reserved+=size;peak=max(peak,reserved);index+=1
                if not inflight:raise ValueError('admission stalled')
                done,_=wait(inflight,return_when=FIRST_COMPLETED)
                for future in done:
                    size=inflight.pop(future);values,elapsed=future.result();reserved-=size;completed+=1
                    if first is None:first=time.perf_counter()-start
                    for key,body in values:received[key]=body
                    ema=elapsed if ema is None else .75*ema+.25*elapsed
                    if adaptive and completed%4==0:
                        window=max(1,window-1) if ema>.030 else min(8,window+1)
                        windows.append({'completed':completed,'window':window,'ema_seconds':ema})
        for client in clients:client.close()
        elapsed=time.perf_counter()-start
    finally:
        for client in clients:client.close()
    if set(received)!=set(ids) or any(received[key]!=objects[key] for key in ids):raise ValueError('consumer mismatch')
    return {'whole_seconds':elapsed,'first_useful_seconds':first,'peak_inflight_payload_bytes':peak,'logical_budget':budget,'objects':len(received),'payload_bytes':sum(map(len,received.values())),'controller':windows,'output_sha256':digest(b''.join(bytes.fromhex(k)+received[k] for k in sorted(received)))}

def run(args):
    sources=[Path(__file__),HERE/'common.py'];before=pins(sources);_,_,allobjects=read_corpus(args.index,args.payload)
    # Real immutable blobs, selected deterministically; largest first exposes HoL.
    selected=sorted(allobjects,key=lambda key:hashlib.sha256(key.encode()).digest())[:48];selected.sort(key=lambda key:len(allobjects[key]),reverse=True);objects={key:allobjects[key] for key in selected};service=Service(objects)
    servers=[HTTP(('127.0.0.1',0),Handler),Binary(('127.0.0.1',0),BinaryHandler)]
    for server in servers:server.service=service;thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
    addresses={'http':servers[0].server_address,'binary':servers[1].server_address};rows=[]
    policies=[('single',1,1,False),('parallel',4,1,False),('batch',4,4,False),('wide',8,4,False),('feedback',1,4,True)]
    try:
        for block in range(args.trials):
            cases=[(profile,protocol,policy) for profile in ('nominal','latency','bandwidth','phase-change') for protocol in ('http','binary') for policy in policies];random.Random(712+block).shuffle(cases)
            for profile,protocol,(name,window,batch,adaptive) in cases:
                with measured(args.lock):
                    service.reset(profile);result=acquire(protocol,addresses[protocol],selected,objects,window,batch,adaptive)
                rows.append({'block':block,'profile':profile,'protocol':protocol,'policy':name,'window':window,'batch':batch,**result,'service':{'requests':service.requests,'request_body_bytes':service.request_bytes,'response_body_bytes':service.response_bytes,'requests_trace':service.rows}})
                if len(rows)%10==0:print('delivery',len(rows),flush=True)
    finally:
        for server in servers:server.shutdown();server.server_close()
    assert before==pins(sources)
    summary=[]
    for profile in ('nominal','latency','bandwidth','phase-change'):
        for protocol in ('http','binary'):
            for name,*_ in policies:
                selected_rows=[r for r in rows if r['profile']==profile and r['protocol']==protocol and r['policy']==name]
                summary.append({'profile':profile,'protocol':protocol,'policy':name,'median_complete_ms':statistics.median(r['whole_seconds']*1000 for r in selected_rows),'median_first_ms':statistics.median(r['first_useful_seconds']*1000 for r in selected_rows),'requests':selected_rows[0]['service']['requests'],'max_inflight_bytes':max(r['peak_inflight_payload_bytes'] for r in selected_rows)})
    data={'schema':'GAIA-SCIENCE-DELIVERY-1','scope':'Actual TCP loopback HTTP1.1 persistent POST-batch and persistent binary with identical bounded payload framing. Latency/bandwidth/phase profiles delay application service; not WAN/packet bandwidth emulation. Server data/preparation lifetime separate. Client setup/normal close, verification and generic blob consumption charged. Logical in-flight payload bound is not total retained/process memory; received outputs retained for oracle.','objects':{k:len(v) for k,v in objects.items()},'sources':before,'rows':rows}
    print(publish(args.output,data,{'cases':summary},{'passed':True,'complete_operations':len(rows),'verified_blobs':len(rows)*len(objects),'same_consumer_output':len({r['output_sha256'] for r in rows})==1,'budget_overshoots':sum(r['peak_inflight_payload_bytes']>r['logical_budget'] for r in rows)},sources))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--index',type=Path,required=True);p.add_argument('--payload',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--lock',type=Path);p.add_argument('--trials',type=int,default=3);run(p.parse_args())

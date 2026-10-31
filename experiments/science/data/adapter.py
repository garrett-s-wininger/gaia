"""A bounded roundtrip contract preserving optional unknown/presence metadata."""
import argparse,base64,json,statistics,struct,time
from pathlib import Path
from common import HERE,digest,measured,pins,publish,read_corpus

MAGIC=b'GAREC001';HEAD=struct.Struct('<8sH');FIELD=struct.Struct('<HI');MAX=1024*1024
def encode(fields):
    if len(fields)>128:raise ValueError('field count')
    body=HEAD.pack(MAGIC,len(fields))+b''.join(FIELD.pack(tag,len(value))+value for tag,value in fields)
    decode(body)
    return body
def decode(body):
    if not HEAD.size<=len(body)<=MAX:raise ValueError('record bound')
    magic,n=HEAD.unpack_from(body)
    if magic!=MAGIC or n>128:raise ValueError('schema')
    at=HEAD.size;seen=set();fields=[]
    for _ in range(n):
        if at+FIELD.size>len(body):raise ValueError('field header')
        tag,size=FIELD.unpack_from(body,at);at+=FIELD.size
        if tag in seen or at+size>len(body):raise ValueError('field geometry')
        seen.add(tag);value=body[at:at+size];at+=size
        if tag==1:value.decode('utf8')
        elif tag in (2,3):
            if size!=8:raise ValueError('integer size')
        elif tag==4:
            if size!=32:raise ValueError('digest size')
        elif tag==5:
            if not value or value[0] not in (0,1):raise ValueError('presence metadata')
            value[1:].decode('utf8')
        elif tag<128 or tag>=32768:raise ValueError('unknown required field')
        fields.append((tag,value))
    if at!=len(body) or not {1,2,3,4}<=seen:raise ValueError('missing/trailing fields')
    return tuple(fields)
def project(fields):
    values=dict(fields)
    return {'name':values[1].decode(),'size':int.from_bytes(values[2],'little'),'offset':int.from_bytes(values[3],'little'),'sha256':values[4].hex()}
def lossless_json(body):
    fields=decode(body);value=[{'tag':tag,'opaque_base64':base64.b64encode(data).decode()} for tag,data in fields]
    encoded=json.dumps(value,separators=(',',':')).encode();parsed=json.loads(encoded)
    result=encode(tuple((row['tag'],base64.b64decode(row['opaque_base64'],validate=True)) for row in parsed))
    return result,len(encoded)
def lossy_json(body):
    values=json.loads(json.dumps(project(decode(body))))
    return encode(((1,values['name'].encode()),(2,values['size'].to_bytes(8,'little')),(3,values['offset'].to_bytes(8,'little')),(4,bytes.fromhex(values['sha256']))))
def fixture(row,number):
    fields=[(1,row['name'].encode()),(2,row['size'].to_bytes(8,'little')),(3,row['offset'].to_bytes(8,'little')),(4,bytes.fromhex(row['sha256']))]
    if number%2:fields.append((5,b'\1'+row['name'].encode()))
    if number%3:fields.append((128,(number.to_bytes(4,'little')+b'\0future\xff')))
    return encode(tuple(fields))

def run(args):
    sources=[Path(__file__),HERE/'common.py'];before=pins(sources);rows,raw,_=read_corpus(args.index,args.payload);bodies=[fixture(row,n) for n,row in enumerate(rows[:512])];observations=[];rejections=[]
    for block in range(args.trials):
        with measured(args.lock):
            start=time.perf_counter_ns();json_bytes=0;outputs=[]
            for body in bodies:
                restored,size=lossless_json(body);json_bytes+=size
                if restored!=body:raise ValueError('lossless roundtrip changed bytes')
                outputs.append(digest(restored))
            elapsed=time.perf_counter_ns()-start
        observations.append({'block':block,'records':len(bodies),'roundtrip_ns':elapsed,'binary_bytes':sum(map(len,bodies)),'json_bytes':json_bytes,'output_sha256':digest(''.join(outputs).encode())})
    for n,body in enumerate(bodies):
        restored=lossy_json(body)
        if project(decode(restored))!=project(decode(body)):raise ValueError('projection changed known values')
        if restored!=body:rejections.append({'record':n,'source_sha256':digest(body),'lossy_sha256':digest(restored)})
    checks=[]
    for value in [b'',b'BADMAGIC'+bodies[0][8:],bodies[0][:-1],bodies[0]+b'trailing']:
        try:decode(value);raise AssertionError('malformed record accepted')
        except ValueError:checks.append('rejected malformed geometry/version')
    base=decode(bodies[0])
    for tag in (6,32768):
        raw=HEAD.pack(MAGIC,len(base)+1)+b''.join(FIELD.pack(t,len(v))+v for t,v in (*base,(tag,b'unknown')))
        try:decode(raw);raise AssertionError('required extension accepted')
        except ValueError:checks.append('unknown required extension rejected')
    assert before==pins(sources)
    data={'schema':'GAIA-SCIENCE-ADAPTER-1','scope':'Experimental TLV contract over actualpackage-filemetadata pluslabelledsyntheticexplicit/unknownextensions; byte-exactroundtripchecks, not auniversalprotocol/Protobufrepair orspeedcomparisonagainst lossyinvalidcontrol. Optionalunknownfields preserved opaquely; requiredunknowns rejected.','index_sha256':digest(args.index.read_bytes()),'sources':before,'rows':observations,'lossy_rejections':rejections,'checks':checks}
    print(publish(args.output,data,{'records':len(bodies),'median_roundtrip_ms':statistics.median(r['roundtrip_ns']/1e6 for r in observations),'binary_bytes':observations[0]['binary_bytes'],'json_bytes':observations[0]['json_bytes'],'lossy_rejected_records':len(rejections),'same_known_projection':True},{'passed':True,'exact_roundtrips':len(bodies)*args.trials,'malformed_or_required_extension_rejections':len(checks),'lossy_candidate_excluded_from_performance_claims':True},sources))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--index',type=Path,required=True);p.add_argument('--payload',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--lock',type=Path);p.add_argument('--trials',type=int,default=5);run(p.parse_args())

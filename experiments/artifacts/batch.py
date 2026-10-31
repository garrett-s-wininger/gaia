"""Shared selected-object batch body over HTTP or experimental TCP framing."""
import struct
import transfer as t

HEADER=struct.Struct('!8sBBHI')
REQUEST_MAGIC=b'GABREQ01'
RESPONSE_MAGIC=b'GABRES01'
ALGORITHM=1  # Explicit SHA-256; unsupported tags fail.
MAX_REQUEST=HEADER.size+32*t.MAX_OBJECTS
MAX_RESPONSE=HEADER.size+40*t.MAX_OBJECTS+t.MAX_PACK


def _header(body,magic):
    if len(body)<HEADER.size:raise t.TransferError('batch truncated header')
    tag,algorithm,flags,reserved,count=HEADER.unpack_from(body)
    if tag!=magic or algorithm!=ALGORITHM or flags or reserved or count>t.MAX_OBJECTS:
        raise t.TransferError('batch version/algorithm/flags/count')
    return count


def request(keys):
    if not 0<len(keys)<=t.MAX_OBJECTS or len(keys)!=len(set(keys)) or any(not t.HEX.fullmatch(key) for key in keys):
        raise t.TransferError('batch requested identities')
    return HEADER.pack(REQUEST_MAGIC,ALGORITHM,0,0,len(keys))+b''.join(bytes.fromhex(key) for key in keys)


def parse_request(body):
    if len(body)>MAX_REQUEST:raise t.TransferError('batch request bound')
    count=_header(body,REQUEST_MAGIC)
    if not count or len(body)!=HEADER.size+32*count:raise t.TransferError('batch request framing')
    keys=[body[i:i+32].hex() for i in range(HEADER.size,len(body),32)]
    if len(set(keys))!=len(keys):raise t.TransferError('batch duplicate requested identity')
    return keys


def response(keys,content):
    parts=[HEADER.pack(RESPONSE_MAGIC,ALGORITHM,0,0,len(keys))];total=HEADER.size;payload=0
    for key in keys:
        body=content.get('/blobs/sha256/'+key)
        if body is None:raise KeyError(key)
        total+=40+len(body);payload+=len(body)
        if total>MAX_RESPONSE or payload>t.MAX_PACK:raise t.TransferError('batch response bound')
        parts.extend([bytes.fromhex(key),struct.pack('!Q',len(body)),body])
    return b''.join(parts)


def parse_response(body,objects):
    if len(body)>MAX_RESPONSE:raise t.TransferError('batch response bound')
    count=_header(body,RESPONSE_MAGIC)
    if count!=len(objects):raise t.TransferError('batch response identity count')
    offset=HEADER.size;result=[];payload=0;view=memoryview(body)
    for obj in objects:
        if len(body)-offset<40:raise t.TransferError('batch truncated record')
        key=body[offset:offset+32].hex();size=struct.unpack_from('!Q',body,offset+32)[0];offset+=40
        if key!=obj['sha256'] or size!=obj['size'] or size>len(body)-offset:raise t.TransferError('batch record identity/size')
        result.append((obj,view[offset:offset+size]));offset+=size;payload+=size
    if offset!=len(body) or payload>t.MAX_PACK:raise t.TransferError('batch response trailing bytes/bounds')
    return result

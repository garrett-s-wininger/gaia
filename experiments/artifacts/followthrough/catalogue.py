"""Read-only portable artifact catalogue with matching owned-object controls."""
import ctypes,hashlib,json,struct
HEADER=struct.Struct('<8sIIII');ROW=struct.Struct('<QQII32s')
MAX_BYTES=16*1024*1024

def encode(rows):
    strings=bytearray();table=bytearray()
    for r in rows:
        name=r['name'].encode();table.extend(ROW.pack(r['offset'],r['size'],len(strings),len(name),bytes.fromhex(r['sha256'])));strings.extend(name)
    return HEADER.pack(b'GACAT001',1,len(rows),len(strings),ROW.size)+table+strings

def validate(body):
    if not 24<=len(body)<=MAX_BYTES:raise ValueError('catalogue size')
    magic,version,count,size,stride=HEADER.unpack_from(body)
    if magic!=b'GACAT001' or version!=1 or count>100000 or stride!=ROW.size or 24+count*stride+size!=len(body):raise ValueError('catalogue geometry')
    pool=24+count*stride
    for i in range(count):
        offset,length,start,n,_=ROW.unpack_from(body,24+i*stride)
        if not n or start+n>size or length>64*1024*1024 or offset>64*1024*1024-length:raise ValueError('name/content bounds')
        body[pool+start:pool+start+n].decode('utf8')
    return count,pool

def query_objects(rows):
    out=[0]*6
    for row in rows:
        name=row['name'];size=row['size'];offset=row['offset'];pin=row['sha256']
        if type(size) is not int or type(offset) is not int or not 0<=size<=64*1024*1024 or not 0<=offset<=64*1024*1024-size or not isinstance(name,str) or not name.encode('utf8') or len(pin)!=64 or len(bytes.fromhex(pin))!=32:raise ValueError('row schema')
        out[0]+=1;out[1]+=size
        if name.endswith('.pyc'):out[2]+=1;out[3]+=size
        if name.startswith('django/'):out[4]+=1;out[5]+=size
    return out

def objects(body):
    count,pool=validate(body);result=[]
    for i in range(count):
        off,size,start,n,digest=ROW.unpack_from(body,24+i*ROW.size)
        result.append(dict(offset=off,size=size,name=body[pool+start:pool+start+n].decode(),sha256=digest.hex()))
    return result

def query_direct(body):
    count,pool=validate(body);out=[0]*6
    for i in range(count):
        off,size,start,n,digest=ROW.unpack_from(body,24+i*ROW.size);name=body[pool+start:pool+start+n]
        out[0]+=1;out[1]+=size
        if name.endswith(b'.pyc'):out[2]+=1;out[3]+=size
        if name.startswith(b'django/'):out[4]+=1;out[5]+=size
    return out

class Native:
    def __init__(self,path):
        self.lib=ctypes.CDLL(str(path));self.call=self.lib.gaia_catalogue_query;self.call.argtypes=[ctypes.c_void_p,ctypes.c_uint64,ctypes.POINTER(ctypes.c_uint64)];self.call.restype=ctypes.c_int32
    def query(self,body):
        result=(ctypes.c_uint64*6)();code=self.call(ctypes.c_char_p(body),len(body),result)
        if code:raise ValueError('native catalogue error '+str(code))
        return list(result)

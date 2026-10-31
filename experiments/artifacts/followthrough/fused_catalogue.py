"""Same binary validation and query in one Python row pass."""
import catalogue

def query_direct(body):
    if not 24<=len(body)<=catalogue.MAX_BYTES:raise ValueError('catalogue size')
    magic,version,count,size,stride=catalogue.HEADER.unpack_from(body)
    if magic!=b'GACAT001' or version!=1 or count>100000 or stride!=catalogue.ROW.size or 24+count*stride+size!=len(body):raise ValueError('catalogue geometry')
    pool=24+count*stride;out=[0]*6
    for i in range(count):
        off,length,start,n,pin=catalogue.ROW.unpack_from(body,24+i*stride)
        if not n or start+n>size or length>64*1024*1024 or off>64*1024*1024-length:raise ValueError('name/content bounds')
        name=body[pool+start:pool+start+n];name.decode('utf8')
        out[0]+=1;out[1]+=length
        if name.endswith(b'.pyc'):out[2]+=1;out[3]+=length
        if name.startswith(b'django/'):out[4]+=1;out[5]+=length
    return out

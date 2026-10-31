"""One bounded Odin FFI call for physical SHA-256 verification/stat emission."""
import ctypes
import hashlib
from pathlib import Path
import struct
import time
import condition_index as reference

class Verifier:
    def __init__(self,path,mode='emit'):
        if mode not in ('verify','emit'):raise ValueError('native verifier mode')
        self.path=Path(path).resolve();self.mode=mode;self.library=ctypes.CDLL(str(self.path))
        self.function=self.library.gaia_condition_verify
        self.function.argtypes=[ctypes.c_void_p,ctypes.c_uint64,ctypes.c_void_p,ctypes.c_uint64,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint64)]
        self.function.restype=ctypes.c_int

    def call(self,template,mode=None,capacity=None):
        """No state survives a call. Input and output are Python-owned buffers."""
        mode=int(self.mode=='emit') if mode is None else mode
        if not isinstance(template,bytearray):template=bytearray(template)
        count=struct.unpack_from('<Q',template,8)[0] if len(template)>=16 else 0
        capacity=(len(template) if mode else count*32) if capacity is None else capacity
        if not 0<=capacity<=8*1048576:raise ValueError('output capacity bound')
        output=bytearray(max(1,capacity));metrics=(ctypes.c_uint64*7)()
        source=(ctypes.c_ubyte*len(template)).from_buffer(template)
        target=(ctypes.c_ubyte*len(output)).from_buffer(output)
        begin=time.perf_counter_ns();code=self.function(source,len(template),target,capacity,mode,metrics);end=time.perf_counter_ns()
        if code:raise reference.UnsupportedIndex('native condition verification failed: '+str(code))
        return output[:metrics[6]],dict(physical_reads=metrics[0],physical_bytes=metrics[1],native_read_ns=metrics[2],native_hash_ns=metrics[3],native_emit_ns=metrics[4],native_total_ns=metrics[5],ffi_ns=end-begin)

    def verify(self,template):
        # The wire template has the ordinary prefixes/digests and expected sizes;
        # metadata placeholders are patched only after every required check.
        begin=time.perf_counter_ns();template+=bytes(32)
        output,stats=self.call(template)
        if self.mode=='verify':
            at=16;count=struct.unpack_from('<Q',template,8)[0]
            for row in range(count):
                kind=template[at];length=struct.unpack_from('<Q',template,at+9)[0];patch=at+17+length
                if kind==1:template[patch:patch+32]=output[row*32:(row+1)*32]
                at=patch+64
            template[-32:]=hashlib.sha256(template[:-32]).digest();output=template
        stats['native_adapter_ns']=time.perf_counter_ns()-begin
        stats['native_mode']=self.mode
        return output,stats

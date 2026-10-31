"""Optional real C++ CIN4 parser/lease tests; GAIA_SHARED_PROBE points to .so."""
import ctypes as c
import fcntl
import os
from pathlib import Path
import struct
import sys
import unittest

PROBE=os.environ.get('GAIA_SHARED_PROBE')
@unittest.skipUnless(PROBE and sys.platform=='linux' and hasattr(os,'memfd_create'),'set GAIA_SHARED_PROBE to the Linux shared-input probe library')
class SharedNativeInputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib=c.CDLL(PROBE)
        cls.lib.gaia_blake3_backend.argtypes=[c.c_int]
        cls.lib.gaia_shared_cache_reset.argtypes=[c.c_char_p];cls.lib.gaia_shared_cache_reset.restype=c.c_int
        cls.lib.gaia_shared_cache_prime.argtypes=[c.c_void_p,c.c_size_t,c.c_char_p];cls.lib.gaia_shared_cache_prime.restype=c.c_int
        cls.lib.gaia_shared_probe_open.argtypes=[c.c_void_p,c.c_size_t,c.c_char_p];cls.lib.gaia_shared_probe_open.restype=c.c_void_p
        cls.lib.gaia_shared_probe_close.argtypes=[c.c_void_p]
        cls.lib.gaia_shared_probe_stat.argtypes=[c.c_void_p,c.c_int];cls.lib.gaia_shared_probe_stat.restype=c.c_uint64
        cls.lib.gaia_shared_probe_name.argtypes=[c.c_void_p,c.c_size_t];cls.lib.gaia_shared_probe_name.restype=c.c_char_p
        cls.lib.gaia_shared_probe_bytes.argtypes=[c.c_void_p,c.c_size_t,c.POINTER(c.c_size_t)];cls.lib.gaia_shared_probe_bytes.restype=c.c_void_p
        cls.lib.gaia_shared_probe_digest.argtypes=[c.c_void_p,c.c_size_t];cls.lib.gaia_shared_probe_digest.restype=c.c_void_p
        cls.lib.gaia_shared_probe_hash.argtypes=[c.c_void_p,c.c_size_t,c.c_void_p]
    def setUp(self):
        self.fds=[];self.handles=[];self.lib.gaia_blake3_backend(1);self.assertEqual(self.lib.gaia_shared_cache_reset(b''),0)
    def tearDown(self):
        for handle in self.handles:self.lib.gaia_shared_probe_close(handle)
        self.lib.gaia_shared_cache_reset(b'');self.lib.gaia_blake3_backend(1)
        for fd in self.fds:
            try:os.close(fd)
            except OSError:pass
    def digest(self,body):
        out=(c.c_uint8*32)();self.lib.gaia_shared_probe_hash(body,len(body),out);return bytes(out)
    def segment(self,files,seal=True,raw=None):
        if raw is None:
            raw=bytearray(b'GAIACIN3'+struct.pack('<Q',len(files)))
            for name,body in sorted(files.items()):
                name=name.encode();raw+=struct.pack('<IQ',len(name),len(body))+name+b'\0'+body+b'\0'
            raw=bytes(raw)
        fd=os.memfd_create('gaia-test-input',os.MFD_ALLOW_SEALING);self.fds.append(fd);os.write(fd,raw)
        if seal:fcntl.fcntl(fd,fcntl.F_ADD_SEALS,15)
        return dict(path=f'/proc/self/fd/{fd}',size=len(raw),pin=self.digest(raw),fd=fd)
    def manifest(self,segments,count,removed=()):
        raw=bytearray(b'GAIACIN4'+struct.pack('<QQ',count,len(segments)))
        for segment in segments:
            path=segment['path'].encode();raw+=struct.pack('<I',len(path))+path+struct.pack('<Q',segment['size'])+segment['pin']
        raw+=struct.pack('<Q',len(removed))
        for name in removed:
            name=name.encode();raw+=struct.pack('<I',len(name))+name
        return bytes(raw)
    def open(self,raw,pin=None):
        pin=pin or b'blake3:'+self.digest(raw).hex().encode();handle=self.lib.gaia_shared_probe_open(raw,len(raw),pin)
        if handle:self.handles.append(handle)
        return handle
    def stat(self,handle,n):return self.lib.gaia_shared_probe_stat(handle,n)
    def contents(self,handle):
        result={}
        for i in range(self.stat(handle,8)):
            size=c.c_size_t();pointer=self.lib.gaia_shared_probe_bytes(handle,i,c.byref(size));body=c.string_at(pointer,size.value)
            self.assertEqual(c.string_at(self.lib.gaia_shared_probe_digest(handle,i),32),self.digest(body))
            result[self.lib.gaia_shared_probe_name(handle,i).decode()]=body
        return result
    def test_valid_overlay_delete_and_retained_digest_counts(self):
        self.assertEqual(self.digest(b'').hex(),'af1349b9f5f9a1a6a0404dea36dcc9499bcb25c9adc112b7cc9a93cae41f3262')
        base=self.segment({'/input/a':b'old','/input/b':b'keep'});raw=self.manifest([base],2)
        self.assertEqual(self.lib.gaia_shared_cache_prime(raw,len(raw),b'blake3:'+self.digest(raw).hex().encode()),0)
        overlay=self.segment({'/input/a':b'new','/input/c':b'added'});handle=self.open(self.manifest([base,overlay],2,['/input/c']))
        self.assertTrue(handle);self.assertEqual(self.contents(handle),{'/input/a':b'new','/input/b':b'keep'})
        self.assertEqual([self.stat(handle,i) for i in (0,1,2,5)],[1,1,overlay['size'],1])
    def test_wrong_pins_unsealed_truncated_and_algorithm_rejected(self):
        base=self.segment({'/input/a':b'hello'});raw=self.manifest([base],1)
        self.assertFalse(self.open(raw,b'blake3:'+b'0'*64))
        wrong=dict(base,pin=bytes(32));self.assertFalse(self.open(self.manifest([wrong],1)))
        unsealed=self.segment({'/input/a':b'hello'},seal=False);self.assertFalse(self.open(self.manifest([unsealed],1)))
        truncated=self.segment({},raw=b'GAIACIN3'+struct.pack('<Q',1)+b'broken');self.assertFalse(self.open(self.manifest([truncated],1)))
        self.lib.gaia_blake3_backend(0);self.assertFalse(self.open(raw));self.lib.gaia_blake3_backend(1)
        self.assertTrue(self.open(raw))
    def test_cache_owns_fd_and_live_lease_survives_reset_and_eviction(self):
        base=self.segment({'/input/a':b'leased'});first=self.open(self.manifest([base],1));self.assertTrue(first)
        os.close(base['fd']);base['path']='/nonexistent/locator'
        again=self.open(self.manifest([base],1));self.assertTrue(again);self.assertEqual(self.stat(again,0),1)
        self.assertEqual(self.lib.gaia_shared_cache_reset(b''),0)
        self.assertEqual(self.contents(first),{'/input/a':b'leased'})
        for i in range(10):
            segment=self.segment({'/input/a':str(i).encode()});handle=self.open(self.manifest([segment],1));self.assertTrue(handle)
            self.assertLessEqual(self.stat(handle,9),64*1048576);self.assertLessEqual(self.stat(handle,10),8)
        self.assertEqual(self.contents(first),{'/input/a':b'leased'})
    def test_utf8_canonical_paths_cached_size_and_kernel_seals(self):
        base=self.segment({'/input/a':b'sealed'})
        with self.assertRaises(OSError):os.write(base['fd'],b'changed')
        self.assertTrue(self.open(self.manifest([base],1)))
        self.assertFalse(self.open(self.manifest([dict(base,size=base['size']+1)],1)))
        name=b'/input/\xff';body=b'bad-name'
        raw=b'GAIACIN3'+struct.pack('<QIQ',1,len(name),len(body))+name+b'\0'+body+b'\0'
        bad=self.segment({},raw=raw);self.assertFalse(self.open(self.manifest([bad],1)))
        for name in ('/input/../a','/input/./a','/input//a','/input/a/'):
            bad=self.segment({name:b'bad'});self.assertFalse(self.open(self.manifest([bad],1)))
        # The same physical-byte provider cannot interpret CIN4 under SHA-256.
        self.lib.gaia_blake3_backend(0);self.assertFalse(self.open(self.manifest([base],1)))
        self.lib.gaia_blake3_backend(1);again=self.open(self.manifest([base],1));self.assertTrue(again);self.assertEqual(self.stat(again,0),1)

    def test_reset_keep_is_atomic_on_malformed_input(self):
        base=self.segment({'/input/a':b'base'});handle=self.open(self.manifest([base],1));self.assertTrue(handle)
        for text in (b'bad',b'0'*65,b'0'*64+b'\n'+b'0'*64,b'\n',b'x'*1000):
            self.assertNotEqual(self.lib.gaia_shared_cache_reset(text),0);self.assertEqual(self.stat(handle,10),1)
        self.assertEqual(self.lib.gaia_shared_cache_reset(base['pin'].hex().encode()+b'\n'),0)
        self.assertEqual(self.stat(handle,10),1)
    def test_manifest_framing_counts_paths_bounds_and_tree_collisions(self):
        base=self.segment({'/input/a':b'a'});raw=self.manifest([base],1)
        for broken in (raw[:-1],raw+b'x',self.manifest([base],2),self.manifest([base,base],1),self.manifest([base],0,['/../a']),self.manifest([base],0,['/input/a','/input/a'])):
            self.assertFalse(self.open(broken))
        huge=dict(base,size=65*1048576);self.assertFalse(self.open(self.manifest([huge],1)))
        child=self.segment({'/input/a/b':b'bad-hierarchy'});self.assertFalse(self.open(self.manifest([base,child],2)))
        self.assertTrue(self.open(self.manifest([base,child],1,['/input/a'])))

if __name__=='__main__':unittest.main()

"""Native batching preserves reference conditions and rejects malformed requests."""
import os
from pathlib import Path
import struct
import tempfile
import unittest
import hashlib

import retained_conditions as retained
from native_conditions import Verifier
import test_retained_conditions as previous
import condition_index as reference

LIBRARY=os.environ.get('GAIA_CONDITION_VERIFIER')

@unittest.skipUnless(LIBRARY,'set GAIA_CONDITION_VERIFIER')
class NativeEmitDifferentialTests(previous.RetainedDifferentialTests):
    def setUp(self):
        super().setUp();self.producer=retained.Producer(Verifier(LIBRARY,'emit'))

@unittest.skipUnless(LIBRARY,'set GAIA_CONDITION_VERIFIER')
class NativeVerifyDifferentialTests(previous.RetainedDifferentialTests):
    def setUp(self):
        super().setUp();self.producer=retained.Producer(Verifier(LIBRARY,'verify'))

@unittest.skipUnless(LIBRARY,'set GAIA_CONDITION_VERIFIER')
class NativeEmitInvalidationTests(previous.RetainedNativeTests):
    def setUp(self):
        super().setUp();self.producer=retained.Producer(Verifier(LIBRARY,'emit'))

@unittest.skipUnless(LIBRARY,'set GAIA_CONDITION_VERIFIER')
class NativeVerifyInvalidationTests(previous.RetainedNativeTests):
    def setUp(self):
        super().setUp();self.producer=retained.Producer(Verifier(LIBRARY,'verify'))

@unittest.skipUnless(LIBRARY,'set GAIA_CONDITION_VERIFIER')
class NativeBoundsTests(unittest.TestCase):
    def test_wire_bounds_and_current_backing(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'input';path.write_bytes(b'contents');name=str(path).encode()
            prefix=b'GAIACQ01'+struct.pack('<Q',1)+b'\x01'+struct.pack('<QQ',1,len(name))+name
            request=bytearray(prefix+struct.pack('<QQQQ',8,0,0,0)+hashlib.sha256(b'contents').digest()+bytes(32))
            for mode in ('verify','emit'):
                verifier=Verifier(LIBRARY,mode);out,stats=verifier.call(request)
                self.assertEqual(stats['physical_reads'],1);self.assertEqual(stats['physical_bytes'],8)
                for bad in (b'',request[:20],request[:-1],b'BADWIRE!'+request[8:],request+bytes(1)):
                    with self.assertRaises(reference.UnsupportedIndex):verifier.call(bad)
                for capacity in (0,1):
                    with self.assertRaises(reference.UnsupportedIndex):verifier.call(request,capacity=capacity)
                with self.assertRaises(reference.UnsupportedIndex):verifier.call(request,mode=5)
                bad=request.copy();bad[8:16]=struct.pack('<Q',65537)
                with self.assertRaises(reference.UnsupportedIndex):verifier.call(bad)
                bad=request.copy();bad[len(prefix)+32]^=1
                with self.assertRaises(reference.UnsupportedIndex):verifier.call(bad)
                path.write_bytes(b'changed!')
                with self.assertRaises(reference.UnsupportedIndex):verifier.call(request)
                path.unlink()
                with self.assertRaises(reference.UnsupportedIndex):verifier.call(request)
                path.symlink_to(Path(folder)/'target');path.resolve().write_bytes(b'contents')
                verifier.call(request)
                path.unlink();path.mkdir()
                with self.assertRaises(reference.UnsupportedIndex):verifier.call(request)
                path.rmdir();path.write_bytes(b'contents')


@unittest.skipUnless(LIBRARY,'set GAIA_CONDITION_VERIFIER')
class NativeStreamingTests(unittest.TestCase):
    def test_empty_chunked_and_metadata_equivalence(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'é-file'
            for body in (b'',bytes(range(256))*1000):
                path.write_bytes(body);os.chmod(path,0o751);os.utime(path,ns=(-1000000001,-1000000001))
                name=str(path).encode();prefix=b'GAIACQ01'+struct.pack('<Q',1)+b'\x01'+struct.pack('<QQ',7,len(name))+name
                template=bytearray(prefix+struct.pack('<QQQQ',len(body),0,0,0)+hashlib.sha256(body).digest())
                info=path.stat();sec,ns=divmod(info.st_mtime_ns,10**9)
                expected=bytearray(prefix+struct.pack('<QQQQ',len(body),sec%(1<<64),ns,info.st_mode)+hashlib.sha256(body).digest());expected+=hashlib.sha256(expected).digest()
                for mode in ('verify','emit'):
                    out,stats=Verifier(LIBRARY,mode).verify(template.copy());self.assertEqual(out,expected)
                    self.assertEqual(stats['physical_bytes'],len(body))

if __name__=='__main__':unittest.main()

import fcntl
import hashlib
import mmap
import os
from pathlib import Path
import tempfile
import time
import unittest

from service import ModelIO,Profile,Sealed,SEALS


class ServiceTests(unittest.TestCase):
    def test_nominal_bytes_and_scope_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);model=ModelIO(root,Profile('nominal'));model.write(root/'blob',b'0123456789')
            self.assertEqual(model.read(root/'blob',10),b'0123456789')
            with (root/'blob').open('rb') as source:self.assertEqual(model.pread(source,root/'blob',2,3),b'234')
            self.assertEqual((model.read_calls,model.read_bytes,model.write_calls,model.write_bytes),(2,13,1,10));self.assertEqual(model.requested_seconds,0)
            with self.assertRaises(ValueError):model.read(root.parent/'unscoped',10)
    def test_calibrated_read_and_write_delay_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);model=ModelIO(root,Profile('calibration',read_latency_ms=2,write_latency_ms=3,read_mib_s=100,write_mib_s=100));body=b'x'*(1024*1024);begin=time.perf_counter();model.write(root/'blob',body);self.assertEqual(model.read(root/'blob',len(body)),body);elapsed=time.perf_counter()-begin
            self.assertAlmostEqual(model.requested_seconds,.025,places=6);self.assertGreaterEqual(model.slept_seconds,.024);self.assertGreaterEqual(elapsed,model.slept_seconds)
    def test_sealed_snapshot_readonly_and_detached_from_source(self):
        original=bytearray(b'immutable');snapshot=Sealed(original)
        try:
            original[:]=b'XXXXXXXXX';self.assertEqual(os.pread(snapshot.fd,9,0),b'immutable');self.assertEqual(fcntl.fcntl(snapshot.fd,fcntl.F_GET_SEALS)&SEALS,SEALS)
            with self.assertRaises(OSError):os.write(snapshot.fd,b'x')
            mapping=mmap.mmap(snapshot.fd,0,access=mmap.ACCESS_READ)
            with self.assertRaises(TypeError):mapping[0]=0
            mapping.close()
        finally:snapshot.close()

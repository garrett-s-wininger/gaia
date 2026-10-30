import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

import test_native_catalog as fixtures
from mapped_catalog import build_mapped_catalog
from native_loader import NativeBundleReader


class MappedCatalogTests(fixtures.NativeCatalogTests):
    def derived(self,archive,index,built):
        return build_mapped_catalog(archive,index,built['index_sha256'],Path(index).with_suffix('.lookup'),self.library)
    def mapped(self,archive,index,built,catalog,**kw):
        return NativeBundleReader(archive,index,index_sha256=built['index_sha256'],library=self.library,
                                  verify=kw.pop('verify','local'),catalog_mode='mapped',catalog_path=catalog['path'],
                                  catalog_sha256=catalog['sha256'],**kw)
    def reader(self,archive,index,built,**kw):return self.mapped(archive,index,built,self.derived(archive,index,built),**kw)
    def test_budget_limit_failure_cleanup_and_constant_arena_after_lookups(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,built,_=self.fixture(Path(temp));catalog=self.derived(archive,index,built)
            reader=self.mapped(archive,index,built,catalog);used=reader.live_counts[3];reader.close()
            before=len(list(Path('/proc/self/fd').iterdir()))
            for budget in (0,1,used-1):
                with self.assertRaises(MemoryError):self.mapped(archive,index,built,catalog,catalog_budget=budget)
                self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)
            reader=self.mapped(archive,index,built,catalog,catalog_budget=used)
            try:
                for _ in range(100):reader.precomputed_modules['gaia_live_pkg.child'];reader.read('gaia_live_pkg/data.txt')
                self.assertEqual(reader._ffi.live_stats(reader._handle)[3],used)
            finally:reader.close()
            self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)
    def test_pin_and_rehashed_structural_corruption_are_rejected_without_leaks(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,built,_=self.fixture(Path(temp));catalog=self.derived(archive,index,built)
            path=Path(catalog['path']);original=path.read_bytes()
            before=len(list(Path('/proc/self/fd').iterdir()))
            with self.assertRaises(ValueError):self.mapped(archive,index,built,dict(catalog,sha256='0'*64))
            n,d,_,slots,dirslots=struct.unpack_from('<5Q',original,48)
            payload=256+16*d;files=payload+8*n;modules=files+8*slots
            next_modules=payload+8*(n+2*slots+dirslots+4*d+n)
            for kind in ('magic','version','flags','binding','n','capacity','size','offset','reserved','name-offset','hash-row','head','dir-offset','truncated'):
                body=bytearray(original)
                if kind=='magic':body[:8]=b'BADMAGIC'
                elif kind=='version':struct.pack_into('<I',body,8,99)
                elif kind=='flags':struct.pack_into('<I',body,12,1)
                elif kind=='binding':body[16:48]=b'x'*32
                elif kind=='n':struct.pack_into('<Q',body,48,n+1)
                elif kind=='capacity':struct.pack_into('<Q',body,72,slots+1)
                elif kind=='size':struct.pack_into('<Q',body,88,len(body)+1)
                elif kind=='offset':struct.pack_into('<Q',body,104,payload+8)
                elif kind=='reserved':body[128]=1
                elif kind=='name-offset':struct.pack_into('<Q',body,payload,len(original)+999999)
                elif kind=='hash-row':struct.pack_into('<Q',body,files,n+1)
                elif kind=='head':struct.pack_into('<Q',body,next_modules,n+1)
                elif kind=='dir-offset':struct.pack_into('<Q',body,256,len(original)+999999)
                elif kind=='truncated':body=body[:-8]
                path.write_bytes(body);pin=hashlib.sha256(body).hexdigest()
                with self.subTest(kind=kind),self.assertRaises(ValueError):self.mapped(archive,index,built,dict(catalog,sha256=pin))
                self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)
    def test_bounded_iteration_rejects_well_pinned_child_cycle(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,built,_=self.fixture(Path(temp));catalog=self.derived(archive,index,built);path=Path(catalog['path'])
            body=bytearray(path.read_bytes());n,d,_,slots,dirslots=struct.unpack_from('<5Q',body,48)
            payload=256+16*d;module_heads=payload+8*(n+2*slots+dirslots+d)
            module_next=payload+8*(n+2*slots+dirslots+4*d+n)
            reader=self.mapped(archive,index,built,catalog)
            directory=reader.directories['gaia_live_pkg/'];reader.close()
            head=struct.unpack_from('<Q',body,module_heads+8*directory)[0]
            struct.pack_into('<Q',body,module_next+8*(head-1),head)
            path.write_bytes(body);catalog['sha256']=hashlib.sha256(body).hexdigest()
            reader=self.mapped(archive,index,built,catalog)
            try:
                with self.assertRaisesRegex(ValueError,'child chain'):list(reader.precomputed_children['gaia_live_pkg'])
            finally:reader.close()


if __name__=='__main__':unittest.main()

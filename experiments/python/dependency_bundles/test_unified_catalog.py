import hashlib
from pathlib import Path
import struct
import tempfile
import unittest

import test_native_catalog as fixtures
from mapped_catalog import build_mapped_catalog
from unified_catalog import build_unified_catalog,word_width
from native_loader import NativeBundleReader


class UnifiedCatalogTests(fixtures.NativeCatalogTests):
    compact=False
    def derived(self,archive,index,built):
        source=build_mapped_catalog(archive,index,built['index_sha256'],Path(index).with_suffix('.lookup'),self.library)
        return build_unified_catalog(archive,index,built['index_sha256'],source,Path(index).with_suffix('.unified'),self.library,compact=self.compact)
    def mapped(self,archive,index,built,catalog,**kw):
        return NativeBundleReader(archive,index,index_sha256=built['index_sha256'],library=self.library,
                                  verify=kw.pop('verify','local'),catalog_mode='compact' if self.compact else 'unified',
                                  catalog_path=catalog['path'],catalog_sha256=catalog['sha256'],**kw)
    def reader(self,archive,index,built,**kw):return self.mapped(archive,index,built,self.derived(archive,index,built),**kw)
    def test_budget_limit_failure_cleanup_and_constant_arena_after_lookups(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,built,_=self.fixture(Path(temp));c=self.derived(archive,index,built)
            r=self.mapped(archive,index,built,c);used=r.live_counts[3];r.close()
            before=len(list(Path('/proc/self/fd').iterdir()))
            for budget in (0,1,used-1):
                with self.assertRaises(MemoryError):self.mapped(archive,index,built,c,catalog_budget=budget)
                self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)
            r=self.mapped(archive,index,built,c,catalog_budget=used)
            try:
                for _ in range(100):r.precomputed_modules['gaia_live_pkg.child'];r.read('gaia_live_pkg/data.txt')
                self.assertEqual(r._ffi.live_stats(r._handle)[3],used)
            finally:r.close()
    def test_authentication_structural_bounds_and_cycle_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,built,_=self.fixture(Path(temp));c=self.derived(archive,index,built);path=Path(c['path']);original=path.read_bytes()
            width=c['word_bytes'];kind='<I' if width==4 else '<Q'
            n,d,_,fc,mc,dc=struct.unpack_from('<6Q',original,72)
            record,table=struct.unpack_from('<2Q',original,120)
            before=len(list(Path('/proc/self/fd').iterdir()))
            with self.assertRaises(ValueError):self.mapped(archive,index,built,dict(c,sha256='0'*64))
            changes={'magic':0,'version':8,'flags':12,'lineage':16,'size':48,'index-offset':56,'index-length':64,
                     'count':72,'file-capacity':96,'module-capacity':104,'dir-offset':120,'table-offset':128,'reserved':200}
            for label,offset in [*changes.items(),('name-offset',table),('file-row',table+width*n),('dir-record',record),('truncated',None)]:
                body=bytearray(original)
                if label=='truncated':body=body[:-1]
                elif label=='name-offset':struct.pack_into(kind,body,offset,len(body)+999)
                elif label=='file-row':struct.pack_into(kind,body,offset,n+1)
                elif label=='dir-record':struct.pack_into(kind,body,offset,len(body)+999)
                else:body[offset]^=0xff
                path.write_bytes(body);changed=dict(c,sha256=hashlib.sha256(body).hexdigest())
                with self.subTest(label=label),self.assertRaises(ValueError):self.mapped(archive,index,built,changed)
                self.assertEqual(len(list(Path('/proc/self/fd').iterdir())),before)
            path.write_bytes(original);r=self.mapped(archive,index,built,c);directory=r.directories['gaia_live_pkg/'];r.close()
            body=bytearray(original);heads=table+width*(n+fc+mc+dc+d);nexts=table+width*(n+fc+mc+dc+4*d+n)
            head=struct.unpack_from(kind,body,heads+width*directory)[0];struct.pack_into(kind,body,nexts+width*(head-1),head)
            path.write_bytes(body);r=self.mapped(archive,index,built,dict(c,sha256=hashlib.sha256(body).hexdigest()))
            try:
                with self.assertRaisesRegex(ValueError,'child chain'):list(r.precomputed_children['gaia_live_pkg'])
            finally:r.close()
    def test_embedded_index_is_standalone_and_full_hash_policy_works(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,built,files=self.fixture(Path(temp));c=self.derived(archive,index,built)
            original=index.read_bytes();body=Path(c['path']).read_bytes();offset,length=struct.unpack_from('<2Q',body,56)
            self.assertEqual(body[offset:offset+length],original)
            retained=index.with_suffix('.retained');index.rename(retained)
            for policy in ('local','hash'):
                r=self.mapped(archive,index,built,c,verify=policy)
                try:
                    for name,payload in files.items():self.assertEqual(r.read(name),payload)
                finally:r.close()
            with self.assertRaises(ValueError):self.mapped(archive,index,dict(built,index_sha256='0'*64),c)
            self.assertEqual(word_width(True,2**32,1,128),8)
            self.assertEqual(word_width(True,1,1,2**32),8)
            self.assertEqual(word_width(True,2**32-1,1,128),4)


class CompactCatalogTests(UnifiedCatalogTests):
    compact=True


if __name__=='__main__':unittest.main()

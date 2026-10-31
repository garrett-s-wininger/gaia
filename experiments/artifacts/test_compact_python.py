import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import compact_python as c
import locked_python as lp
import transfer as t
import cache_store


class CompactPythonTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'source';(source/'pkg/sub').mkdir(parents=True)
        for name,body in {'pkg/__init__.py':b'VALUE = 1\n','pkg/sub/__init__.py':b'','pkg/sub/leaf.py':b'X = 2\n','pkg/data.txt':b'resource\n'}.items():(source/name).write_bytes(body)
        lock,payloads=lp.make_lock(source,dict(versions={},resources={}));pin=t.digest(lock)
        store=cache_store.Packed(root/'cache');objects=[dict(sha256=t.digest(body),size=len(body)) for body in payloads];store.prepare(objects)
        for obj,body in zip(objects,payloads):store.put_verified(obj,body)
        store.finish();store.close();desc=c.build(root/'cache',lock,pin,root/'consumer.gpi','pack')
        return source,lock,pin,desc
    def test_lookup_resources_packages_children_and_lifetime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,lock,pin,desc=self.fixture(root);reader=c.Reader(root/'cache',root/'consumer.gpi',desc['pin'],pin)
            self.assertEqual(reader.read('pkg/data.txt'),b'resource\n');self.assertEqual(reader.precomputed_modules['pkg.sub.leaf'],('pkg/sub/leaf.py',False))
            self.assertEqual(reader.precomputed_packages['pkg/sub'],'pkg.sub');self.assertEqual(reader.precomputed_children['pkg/sub'],(('leaf',False),))
            self.assertIn('pkg/sub/',reader.directories);self.assertNotIn('missing',reader.entries)
            self.assertEqual(reader.native_timings['integrity_policy'],'sha256+crc32-every-read');reader.close()
            with self.assertRaises(t.TransferError):reader.read('pkg/data.txt')
    def test_index_pin_binding_truncation_and_unsupported_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,lock,pin,desc=self.fixture(root);path=root/'consumer.gpi';original=path.read_bytes()
            with self.assertRaises(t.TransferError):c.Reader(root/'cache',path,'0'*64,pin)
            with self.assertRaises(t.TransferError):c.Reader(root/'cache',path,desc['pin'],'0'*64)
            for bad in (original[:12],original[:8]+(2).to_bytes(4,'big')+original[12:]):
                path.write_bytes(bad)
                with self.assertRaises(t.TransferError):c.Reader(root/'cache',path,t.digest(bad),pin)
    def test_changed_container_fails_and_same_session_detects_corrupt_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,lock,pin,desc=self.fixture(root);reader=c.Reader(root/'cache',root/'consumer.gpi',desc['pin'],pin)
            target=next((root/'cache/packs').glob('*.gap'));body=bytearray(target.read_bytes());body[-1]^=1;target.write_bytes(body)
            with self.assertRaises(t.TransferError):
                for name in reader.entries:reader.read(name)
            reader.close()
            with self.assertRaises(t.TransferError):c.Reader(root/'cache',root/'consumer.gpi',desc['pin'],pin)
    def test_pack_and_zip_same_bytes_and_integrity_policy(self):
        import sys,zipfile
        sys.path.insert(0,str(Path(__file__).parent.parent/'python/dependency_bundles'))
        from precomputed_index import build_index
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source,lock,pin,desc=self.fixture(root);zip_path=root/'cache/dependencies.zip'
            with zipfile.ZipFile(zip_path,'w',compression=zipfile.ZIP_STORED) as z:
                for row in json.loads(lock)['files']:z.write(source/row['name'],row['name'])
            zip_index=root/'dependencies.index';old=build_index(zip_path,zip_index,encoding='binary');z=c.build(root/'cache',lock,pin,root/'zip.gpi','zip',zip_path,zip_index,old['index_sha256'])
            pack=c.Reader(root/'cache',root/'consumer.gpi',desc['pin'],pin);zip=c.Reader(root/'cache',root/'zip.gpi',z['pin'],pin)
            for name in pack.entries:self.assertEqual(pack.read(name),zip.read(name))
            self.assertEqual(pack.native_timings['integrity_policy'],zip.native_timings['integrity_policy']);pack.close();zip.close()
    def test_both_digest_and_crc_are_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,lock,pin,desc=self.fixture(root);path=root/'consumer.gpi';original=path.read_bytes();meta_size=c.HEADER.unpack_from(original)[2];offset=c.HEADER.size+meta_size
            for field in (6,7):
                body=bytearray(original);row=list(c.FILE.unpack_from(body,offset));row[field]=bytes(32) if field==6 else row[field]^1;c.FILE.pack_into(body,offset,*row);path.write_bytes(body)
                reader=c.Reader(root/'cache',path,t.digest(body),pin)
                with self.assertRaises(t.TransferError):reader.read('pkg/__init__.py')
                reader.close()

import json
from pathlib import Path
import tempfile
import unittest

import locked_python as lp
import pipeline_transport as p
import transfer as t


class LockedPythonTests(unittest.TestCase):
    def fixture(self,root):
        src=root/'source';(src/'pkg').mkdir(parents=True);(src/'pkg/__init__.py').write_bytes(b'VALUE = 7\n');(src/'pkg/data.txt').write_bytes(b'resource\n')
        lock,payloads=lp.make_lock(src,dict(versions={'pkg':'1'},resources={}))
        return lock,t.digest(lock),t.build_collection(payloads)
    def test_direct_hash_set_reuse_reader_and_corruption_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lock,pin,collection=self.fixture(root);cache=root/'cache'
            with p.local_server(collection) as url:
                result=lp.acquire(url,lock,pin,cache);metrics=t.control(url,'metrics')
                self.assertEqual((result['requests'],metrics['manifest_requests']),(1,0))
                reader=lp.PackedReader(cache,lock,pin)
                self.assertEqual(reader.read('pkg/__init__.py'),b'VALUE = 7\n');self.assertEqual(reader.read('pkg/data.txt'),b'resource\n');reader.close()
                self.assertEqual(lp.acquire('gaia-mux://127.0.0.1:1',lock,pin,cache)['requests'],0)
                pack=next((cache/'packs').glob('*.gap'));body=bytearray(pack.read_bytes());body[-1]^=1;pack.write_bytes(body)
                reader=lp.PackedReader(cache,lock,pin)
                with self.assertRaises(t.TransferError):
                    for row in json.loads(lock)['files']:reader.read(row['name'])
                reader.close();self.assertGreater(lp.acquire(url,lock,pin,cache)['transfer_bytes'],0)
    def test_failed_stream_has_no_ready_and_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);lock,pin,collection=self.fixture(root);cache=root/'cache'
            with p.local_server(collection,faults={'corrupt-record':0}) as url:
                with self.assertRaises(t.TransferError):lp.acquire(url,lock,pin,cache)
            self.assertFalse((cache/'ready.json').exists())
            with p.local_server(collection) as url:self.assertEqual(lp.acquire(url,lock,pin,cache)['requests'],1)
    def test_lock_bounds_names_algorithm_and_conflicting_sizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock,pin,_=self.fixture(Path(tmp));value=json.loads(lock)
            with self.assertRaises(t.TransferError):lp.parse_lock(lock,'0'*64)
            for field,bad in [('algorithm','blake3'),('version',2)]:
                modified=dict(value);modified[field]=bad;body=t.encode(modified)
                with self.assertRaises(t.TransferError):lp.parse_lock(body,t.digest(body))
            for name in ('../escape','/absolute','pkg//bad','pkg/../bad','C:bad'):
                modified=json.loads(lock);modified['files'][0]['name']=name;body=t.encode(modified)
                with self.assertRaises(t.TransferError):lp.parse_lock(body,t.digest(body))
    def test_exact_discovery_is_a_separate_pinned_catalog(self):
        descriptor=dict(algorithm='sha256',digest='a'*64,size=42)
        body=t.encode(dict(version=1,entries=[dict(name='example',version='1.0',lock=descriptor)]));pin=t.digest(body)
        self.assertEqual(lp.discover_exact(body,pin,'example','1.0'),descriptor)
        with self.assertRaises(LookupError):lp.discover_exact(body,pin,'example','2.0')
        with self.assertRaises(t.TransferError):lp.discover_exact(body,'0'*64,'example','1.0')
        duplicated=json.loads(body);duplicated['entries']*=2;body=t.encode(duplicated)
        with self.assertRaises(t.TransferError):lp.discover_exact(body,t.digest(body),'example','1.0')

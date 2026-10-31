import json
from pathlib import Path
import shutil
import tempfile
import unittest

import preindexed_bundle as bundle
from preindexed_bundle_benchmark import produce
import locked_python as python
import pipeline_transport as transport
import transfer as t


class PreindexedBundleTests(unittest.TestCase):
    def fixture(self,root,kind):
        source=root/'inputs';(source/'pkg').mkdir(parents=True)
        (source/'pkg/__init__.py').write_bytes(b'VALUE=1\n');(source/'pkg/data.txt').write_bytes(b'resource\n')
        body,payloads=python.make_lock(source,dict(versions={'pkg':'opaque'},resources={}))
        return produce(root/'producer',body,payloads,kind)
    def test_portability_partial_cache_offline_and_matching_reads(self):
        for kind in ('flat','zip'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);p=self.fixture(root,kind);self.assertNotIn(str(root).encode(),p['index'])
                collection=t.build_collection([p['payload'],p['index']]);cache=root/'receiver';objects=cache/'objects/sha256';objects.mkdir(parents=True);(objects/p['payload_descriptor']['digest']).write_bytes(p['payload'])
                with transport.local_server(collection) as url:
                    view,result=bundle.acquire(url,p['lock'],p['lock_pin'],cache)
                    self.assertEqual((result['objects'],result['cache_hits'],result['requests'],result['transfer_bytes']),(2,1,1,len(p['index'])))
                desc=bundle.admit(cache,p['index_descriptor'],p['payload_descriptor'],root/'binding.json');reader=bundle.Reader(cache,objects/p['index_descriptor']['digest'],p['index_descriptor']['digest'],(root/'binding.json').read_bytes(),desc['binding_pin'])
                self.assertEqual(reader.read('pkg/data.txt'),b'resource\n');self.assertEqual(reader.native_timings['integrity_policy'],'sha256+crc32-every-read');reader.close()
                self.assertEqual(bundle.acquire('gaia-mux://127.0.0.1:1',p['lock'],p['lock_pin'],cache)[1]['requests'],0)
                moved=root/'moved';shutil.copytree(cache,moved);new=bundle.admit(moved,p['index_descriptor'],p['payload_descriptor'],root/'moved-binding.json');reader=bundle.Reader(moved,moved/'objects/sha256'/p['index_descriptor']['digest'],p['index_descriptor']['digest'],(root/'moved-binding.json').read_bytes(),new['binding_pin']);self.assertEqual(reader.read('pkg/__init__.py'),b'VALUE=1\n');reader.close()
    def test_corruption_is_detected_and_repair_rebinds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=self.fixture(root,'flat');cache=root/'receiver';collection=t.build_collection([p['payload'],p['index']])
            with transport.local_server(collection) as url:
                bundle.acquire(url,p['lock'],p['lock_pin'],cache);desc=bundle.admit(cache,p['index_descriptor'],p['payload_descriptor'],root/'binding.json');index=cache/'objects/sha256'/p['index_descriptor']['digest'];reader=bundle.Reader(cache,index,p['index_descriptor']['digest'],(root/'binding.json').read_bytes(),desc['binding_pin'])
                path=cache/'objects/sha256'/p['payload_descriptor']['digest'];body=bytearray(path.read_bytes());body[-1]^=1;path.write_bytes(body)
                with self.assertRaises(t.TransferError):
                    for name in reader.entries:reader.read(name)
                reader.close()
                with self.assertRaises(t.TransferError):bundle.Reader(cache,index,p['index_descriptor']['digest'],(root/'binding.json').read_bytes(),desc['binding_pin'])
                self.assertEqual(bundle.acquire(url,p['lock'],p['lock_pin'],cache)[1]['transfer_bytes'],len(p['payload']))
                desc=bundle.admit(cache,p['index_descriptor'],p['payload_descriptor'],root/'binding.json');reader=bundle.Reader(cache,index,p['index_descriptor']['digest'],(root/'binding.json').read_bytes(),desc['binding_pin']);self.assertEqual(reader.read('pkg/data.txt'),b'resource\n');reader.close()
    def test_malformed_portable_header_and_cross_binding_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=self.fixture(Path(tmp),'flat')
            with self.assertRaises(t.TransferError):bundle.metadata(p['index'][:12])
            bad=bytearray(p['index']);bad[8:12]=(2).to_bytes(4,'big')
            with self.assertRaises(t.TransferError):bundle.metadata(bytes(bad))
            receiver=Path(tmp)/'receiver';objects=receiver/'objects/sha256';objects.mkdir(parents=True);(objects/p['index_descriptor']['digest']).write_bytes(p['index']);wrong=dict(p['payload_descriptor']);wrong['digest']='0'*64
            with self.assertRaises(t.TransferError):bundle.admit(receiver,p['index_descriptor'],wrong,Path(tmp)/'binding.json')

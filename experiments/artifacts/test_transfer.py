import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import transfer as t


class ModelTests(unittest.TestCase):
    def test_collection_deduplicates_and_zero_size(self):
        c=t.build_collection([b'',b'abc',b'abc']);m=t.parse_manifest(c['manifest'])
        self.assertEqual(len(m['objects']),2);self.assertEqual(m['pack']['size'],3)
        self.assertEqual(t.digest(c['manifest']),c['manifest_id'])

    def test_manifest_rejects_ambiguous_schema_and_geometry(self):
        c=t.build_collection([b'a',b'b']);good=json.loads(c['manifest'])
        variants=[]
        for change in [lambda x:x.update(version=2),lambda x:x.update(digest_algorithm='blake3'),lambda x:x['objects'][0].update(offset=-1),
                       lambda x:x['objects'][0].update(size=True),lambda x:x['pack'].update(size=t.MAX_PACK+1),
                       lambda x:x['objects'][1].update(sha256=x['objects'][0]['sha256'])]:
            value=json.loads(c['manifest']);change(value);variants.append(t.encode(value))
        variants += [b'{"version":1,"version":1}',b'\xff']
        for body in variants:
            with self.assertRaises(t.TransferError):t.parse_manifest(body)

    def test_coalescing_respects_gap_and_span(self):
        objects=[dict(sha256='a',offset=0,size=4),dict(sha256='b',offset=8,size=4),dict(sha256='c',offset=16,size=0)]
        self.assertEqual(len(t.coalesce(objects,4,12)),1)
        self.assertEqual(len(t.coalesce(objects,3,12)),2)
        self.assertEqual(len(t.coalesce(objects,4,11)),2)
        # A single object may exceed a batching span; it is never split here.
        self.assertEqual(t.coalesce(objects,0,1)[0][:2],[0,3])

    def test_atomic_write_failure_preserves_previous_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'blob';p.write_bytes(b'old')
            with mock.patch.object(t.os,'replace',side_effect=OSError('failed')):
                with self.assertRaises(OSError):t.atomic_write(p,b'new')
            self.assertEqual(p.read_bytes(),b'old');self.assertFalse(list(Path(tmp).glob('*.tmp.*')))


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='gaia artifacts $ ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.collection=t.build_collection([b'',b'a'*31,b'b'*47,b'c'*59,b'd'*83])
        self.keys=list(self.collection['objects']);self.size=len(self.collection['manifest'])

    def run_fetch(self,url,mode,cache,wanted=None):
        return t.fetch(url,self.collection['manifest_id'],self.size,self.keys if wanted is None else wanted,cache,mode,gap=1000,max_span=4096)

    def assert_ready(self,cache,wanted=None):
        keys=self.keys if wanted is None else wanted
        receipt=json.loads((cache/'ready.json').read_bytes());self.assertEqual(receipt['objects'],['sha256:'+key for key in sorted(keys)])
        for key in keys:self.assertEqual((cache/'objects'/'sha256'/key).read_bytes(),self.collection['objects'][key])

    def test_all_modes_match_payloads_and_independent_server_counters(self):
        with t.local_server(self.collection) as url:
            for mode in t.MODES:
                cache=self.root/mode;t.control(url,'reset');result=self.run_fetch(url,mode,cache)
                self.assert_ready(cache);server=t.control(url,'metrics')
                self.assertEqual(result['requests'],server['requests']);self.assertEqual(result['response_payload_bytes'],server['response_payload_bytes'])
                self.assertEqual(result['published_objects'],len(self.keys))
                self.assertEqual(result['cache_hits'],0)
                self.assertGreater(result['metadata_seconds'],0)

    def test_pinned_metadata_and_all_objects_work_offline(self):
        cache=self.root/'cache'
        with t.local_server(self.collection) as url:self.run_fetch(url,'pack-full',cache)
        # Connection creation would fail if a fully verified cache made requests.
        with mock.patch.object(t.http.client.HTTPConnection,'connect',side_effect=AssertionError('network attempted')):
            result=self.run_fetch('http://127.0.0.1:1','pack-coalesced',cache)
        self.assertEqual(result['requests'],0);self.assertEqual(result['transfer_bytes'],0);self.assert_ready(cache)

    def test_corrupt_cache_is_refetched_and_failure_clears_ready_marker(self):
        cache=self.root/'cache';key=next(key for key in self.keys if self.collection['objects'][key])
        with t.local_server(self.collection) as url:
            self.run_fetch(url,'objects-serial',cache)
            (cache/'objects'/'sha256'/key).write_bytes(b'!'*len(self.collection['objects'][key]))
            result=self.run_fetch(url,'objects-serial',cache);self.assertEqual(result['published_objects'],1);self.assert_ready(cache)
        (cache/'objects'/'sha256'/key).write_bytes(b'corrupt')
        with t.local_server(self.collection,faults={'/blobs/sha256/'+key:'corrupt'}) as url:
            with self.assertRaises(t.TransferError):self.run_fetch(url,'objects-serial',cache)
        self.assertFalse((cache/'ready.json').exists())

    def test_ignored_range_uses_bounded_full_pack_fallback(self):
        key=next(key for key in self.keys if self.collection['objects'][key]);cache=self.root/'cache'
        with t.local_server(self.collection,faults={'/blobs/sha256/'+self.collection['pack_id']:'ignore-range'}) as url:
            result=self.run_fetch(url,'pack-coalesced',cache,[key]);self.assert_ready(cache,[key])
            self.assertTrue(result['full_pack_fallback']);self.assertEqual(result['transfer_bytes'],len(self.collection['pack']))
            self.assertEqual(result['overfetch_bytes'],len(self.collection['pack'])-len(self.collection['objects'][key]))

    def test_bad_manifest_digest_is_rejected_before_payload(self):
        path='/manifests/sha256/'+self.collection['manifest_id'];cache=self.root/'cache'
        with t.local_server(self.collection,faults={path:'corrupt'}) as url:
            with self.assertRaises(t.TransferError):self.run_fetch(url,'pack-full',cache)
            self.assertEqual(t.control(url,'metrics')['requests'],1)
        self.assertFalse((cache/'ready.json').exists())

    def test_corrupt_truncated_wrong_validator_range_and_encoding_fail(self):
        path='/blobs/sha256/'+self.collection['pack_id']
        with t.local_server(self.collection) as url:
            # Verify the manifest once, then each fault targets payload behavior.
            metadata=self.root/'metadata';self.run_fetch(url,'objects-serial',metadata,[])
        for fault in ['corrupt','truncated','wrong-etag','wrong-range','encoded']:
            with self.subTest(fault=fault):
                cache=self.root/fault
                with t.local_server(self.collection,faults={path:fault}) as url:
                    with self.assertRaises(t.TransferError):self.run_fetch(url,'pack-coalesced',cache)
                self.assertFalse((cache/'ready.json').exists())
                self.assertFalse(list(cache.rglob('*.tmp.*')))

    def test_verified_objects_survive_partial_failure_and_resume_next_call(self):
        keys=[key for key in self.keys if self.collection['objects'][key]];cache=self.root/'cache'
        with t.local_server(self.collection,faults={'/blobs/sha256/'+keys[1]:'truncated'}) as url:
            with self.assertRaises(t.TransferError):self.run_fetch(url,'objects-serial',cache,keys)
        self.assertEqual((cache/'objects'/'sha256'/keys[0]).read_bytes(),self.collection['objects'][keys[0]])
        self.assertFalse((cache/'ready.json').exists())
        with t.local_server(self.collection) as url:
            result=self.run_fetch(url,'objects-serial',cache,keys)
        self.assertEqual(result['cache_hits'],1);self.assert_ready(cache,keys)


if __name__=='__main__':unittest.main()

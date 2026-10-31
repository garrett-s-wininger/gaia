import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import binary_transport as binary
import cache_store as c
import transfer as t


def server(collection,transport,faults=None):
    return t.local_server(collection,faults=faults) if transport=='http' else binary.local_server(collection,faults=faults,buffered=True)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='gaia packed cache $ ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.collection=t.build_collection([b'',b'a'*31,b'b'*47,b'c'*59])
        self.keys=sorted(self.collection['objects']);self.manifest=t.parse_manifest(self.collection['manifest'])
    def fetch(self,url,cache,storage='packed',mode='selected-batch',wanted=None):
        return t.fetch(url,self.collection['manifest_id'],len(self.collection['manifest']),self.keys if wanted is None else wanted,cache,mode,storage=storage)
    def access(self,cache,storage='packed',wanted=None):
        return c.access(cache,self.collection['manifest_id'],len(self.collection['manifest']),self.keys if wanted is None else wanted,storage)
    def assert_views(self,views,wanted=None):
        keys=self.keys if wanted is None else wanted;self.assertEqual(set(views),set(keys))
        for key in keys:
            self.assertTrue(views[key].readonly);self.assertEqual(bytes(views[key]),self.collection['objects'][key])
    def test_both_layouts_and_transports_preserve_logical_access(self):
        for transport in ['http','binary-buffered']:
            with server(self.collection,transport) as url:
                for layout in ['files','packed']:
                    for mode in t.MODES:
                        with self.subTest(transport=transport,layout=layout,mode=mode):
                            cache=self.root/(transport+layout+mode);sample=self.fetch(url,cache,layout,mode)
                            views,access=self.access(cache,layout);self.assert_views(views)
                            self.assertEqual(sample['published_objects'],len(self.keys))
                            self.assertEqual(sample['atomic_publications'],len(self.keys)+2 if layout=='files' else 5)
                            self.assertEqual(access['logical_hash_bytes'],len(self.collection['pack']))
    def test_owned_views_remain_valid_after_repair_and_materialization_is_explicit(self):
        cache=self.root/'cache'
        with server(self.collection,'http') as url:self.fetch(url,cache)
        views,_=self.access(cache);self.assert_views(views)
        paths,stats=c.materialize(cache,views,'packed',self.root/'ordinary');self.assertEqual(stats['publications'],len(self.keys))
        for key,path in paths.items():self.assertEqual(path.read_bytes(),self.collection['objects'][key])
        for path in (cache/'packs').glob('*.gap'):path.write_bytes(b'broken')
        self.assert_views(views)  # Owned backing buffers, independent of cache-file mutation.
        with self.assertRaises(t.TransferError):self.access(cache)
    def test_fully_cached_pinned_access_is_offline_for_both_layouts(self):
        for layout in ['files','packed']:
            cache=self.root/layout
            with server(self.collection,'binary-buffered') as url:self.fetch(url,cache,layout)
            with mock.patch.object(t.socket,'create_connection',side_effect=AssertionError('network attempted')):
                sample=self.fetch('gaia-binary-buffered://127.0.0.1:1',cache,layout)
                views,_=self.access(cache,layout);self.assert_views(views)
                self.assertEqual(sample['requests'],0);self.assertEqual(sample['atomic_publications'],1)
    def test_corrupted_blob_is_detected_and_only_that_blob_refetched(self):
        cache=self.root/'cache'
        with server(self.collection,'http') as url:
            self.fetch(url,cache);store=c.Packed(cache)
            key=next(key for key in self.keys if self.collection['objects'][key]);entry=store.entries[key];path=store.data_dir/(entry['pack']+'.gap');offset=entry['offset'];store.close()
            with path.open('r+b') as stream:stream.seek(offset);value=stream.read(1);stream.seek(offset);stream.write(bytes([value[0]^1]))
            with self.assertRaises(t.TransferError):self.access(cache)
            sample=self.fetch(url,cache);self.assertEqual(sample['published_objects'],1)
            views,_=self.access(cache);self.assert_views(views)
    def test_corrupt_index_recovers_online_and_unknown_version_is_preserved(self):
        cache=self.root/'cache'
        with server(self.collection,'http') as url:
            self.fetch(url,cache);head=json.loads((cache/'head.json').read_bytes());index=cache/'indexes'/(head['index']['digest']+'.gai')
            index.write_bytes(b'corrupt');sample=self.fetch(url,cache);self.assertTrue(sample['store']['corrupt_index'])
            self.assert_views(self.access(cache)[0])
        head=json.loads((cache/'head.json').read_bytes());head['version']=2;(cache/'head.json').write_bytes(t.encode(head))
        files={str(p.relative_to(cache)):p.read_bytes() for p in (cache/'packs').glob('*.gap')}
        with self.assertRaises(c.UnsupportedStore):c.Packed(cache)
        self.assertEqual(files,{str(p.relative_to(cache)):p.read_bytes() for p in (cache/'packs').glob('*.gap')})
        head['version']=1;head['index']['algorithm']='blake3';(cache/'head.json').write_bytes(t.encode(head))
        with self.assertRaises(c.UnsupportedStore):c.Packed(cache)
        self.assertEqual(files,{str(p.relative_to(cache)):p.read_bytes() for p in (cache/'packs').glob('*.gap')})
    def test_verified_prefix_survives_failed_blob_and_next_request_recovers(self):
        cache=self.root/'cache';keys=[key for key in self.keys if self.collection['objects'][key]]
        with server(self.collection,'http',{'/blobs/sha256/'+keys[1]:'corrupt'}) as url:
            with self.assertRaises(t.TransferError):self.fetch(url,cache,mode='objects-serial',wanted=keys)
        self.assertFalse((cache/'ready.json').exists());self.assert_views(self.access(cache,wanted=[keys[0]])[0],[keys[0]])
        with server(self.collection,'http') as url:
            sample=self.fetch(url,cache,wanted=keys);self.assertEqual(sample['cache_hits'],1)
        self.assert_views(self.access(cache,wanted=keys)[0],keys)
    def test_index_publication_failure_keeps_prior_head_and_recovers_orphans(self):
        cache=self.root/'cache';objects={obj['sha256']:obj for obj in self.manifest['objects']};first,second=self.keys[:2]
        with server(self.collection,'http') as url:self.fetch(url,cache,wanted=[first])
        original=(cache/'head.json').read_bytes();store=c.Packed(cache);store.prepare([objects[second]]);store.put_verified(objects[second],self.collection['objects'][second])
        original_publish=store._publish_bytes
        def fail_head(name,path,body):
            if name=='head.tmp':raise OSError('simulated failed head publication')
            return original_publish(name,path,body)
        with mock.patch.object(store,'_publish_bytes',side_effect=fail_head):
            with self.assertRaises(OSError):store.finish()
        store.close();self.assertEqual((cache/'head.json').read_bytes(),original)
        self.assert_views(self.access(cache,wanted=[first])[0],[first])
        reopened=c.Packed(cache);self.assertEqual(len(list(reopened.data_dir.glob('*.gap'))),len(reopened.packs));self.assertFalse(list(reopened.staging.iterdir()));reopened.close()
    def test_compaction_and_quotas_are_bounded(self):
        collection=t.build_collection([bytes([i])*17 for i in range(10)]);objects=t.parse_manifest(collection['manifest'])['objects'];cache=self.root/'compact'
        compacted=0
        for obj in objects:
            store=c.Packed(cache);store.prepare([obj]);store.put_verified(obj,collection['objects'][obj['sha256']]);store.finish()
            compacted+=store.stats['compactions'];self.assertLessEqual(len(store.packs),c.MAX_PACKS);store.close()
        self.assertEqual(compacted,1)
        store=c.Packed(cache);known=dict(store.iter_available(objects));self.assertEqual(set(known),set(collection['objects']))
        with mock.patch.object(c,'MAX_DATA',sum(obj['size'] for obj in objects)):
            with self.assertRaises(c.QuotaError):store.prepare([dict(sha256='f'*64,size=1)])
        store.close()
    def test_cache_lease_rejects_concurrent_transactions(self):
        cache=self.root/'lease';store=c.Packed(cache)
        try:
            with self.assertRaises(t.TransferError):c.Packed(cache)
            with self.assertRaises(t.TransferError):c.Files(cache)
        finally:store.close()
    def test_stale_staging_and_uncommitted_files_are_recovered(self):
        cache=self.root/'cache'
        with server(self.collection,'http') as url:self.fetch(url,cache)
        (cache/'staging'/'data.tmp').write_bytes(b'incomplete');(cache/'packs'/('f'*64+'.gap')).write_bytes(b'orphan')
        views,_=self.access(cache);self.assert_views(views);self.assertFalse(list((cache/'staging').iterdir()))
        self.assertFalse((cache/'packs'/('f'*64+'.gap')).exists())


if __name__=='__main__':unittest.main()

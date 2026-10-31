from pathlib import Path
import tempfile
import unittest
from unittest import mock

import cache_store
import pipeline_transport as p
import transfer as t


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='gaia pipeline $ ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.collection=t.build_collection([bytes([i])*4096 for i in range(12)])
        self.keys=sorted(self.collection['objects'])
    def fetch(self,url,cache,mode,layout='packed',client=None,callback=None):
        return t.fetch(url,self.collection['manifest_id'],len(self.collection['manifest']),self.keys,cache,mode,storage=layout,client=client,verified_callback=callback)
    def check(self,cache,layout):
        views,_=cache_store.access(cache,self.collection['manifest_id'],len(self.collection['manifest']),self.keys,layout)
        for key,view in views.items():self.assertEqual(bytes(view),self.collection['objects'][key])
    def test_four_paths_both_layouts_and_reused_connection(self):
        with p.local_server(self.collection) as url:
            for layout in ('files','packed'):
                for mode in ('objects-serial','objects-windowed','selected-batch','stream-batch'):
                    cache=self.root/(layout+mode);client=p.Client(url);client.connect();client.reset_counts()
                    try:
                        sample=self.fetch(url,cache,mode,layout,client)
                        self.assertEqual(sample['requests'],13 if mode.startswith('objects-') else 2)
                        self.assertEqual(sample['connections'],1);self.assertIsNotNone(sample['first_new_verified_seconds']);self.check(cache,layout)
                        client.reset_counts();again=self.fetch(url,cache,mode,layout,client)
                        self.assertEqual(again['requests'],0);self.assertIsNone(again['first_new_verified_seconds'])
                    finally:client.close()
    def test_window_demultiplexes_out_of_order_and_bounds_ids(self):
        with p.local_server(self.collection,faults={'reorder':True}) as url:
            client=p.Client(url)
            try:
                sample=self.fetch(url,self.root/'window','objects-windowed',client=client)
                self.assertLessEqual(client.peak_pending,p.WINDOW);self.assertLessEqual(client.peak_pending_bytes,p.BYTE_WINDOW)
                self.assertNotEqual(client.completions,sorted(client.completions));self.check(self.root/'window','packed')
            finally:client.close()
    def test_partial_stream_preserves_verified_prefix_without_end_receipt(self):
        for layout in ('files','packed'):
            cache=self.root/layout
            with p.local_server(self.collection,faults={'truncate-record':2}) as url:
                with self.assertRaises(t.TransferError):self.fetch(url,cache,'stream-batch',layout)
            self.assertFalse((cache/'ready.json').exists())
            views,_=cache_store.access(cache,self.collection['manifest_id'],len(self.collection['manifest']),self.keys[:2],layout)
            self.assertEqual(set(views),set(self.keys[:2]))
            with p.local_server(self.collection) as url:
                sample=self.fetch(url,cache,'stream-batch',layout);self.assertEqual(sample['cache_hits'],2)
            self.check(cache,layout)
    def test_stream_requires_end_and_checks_records_correlation_and_version(self):
        faults=[{'missing-end':True},{'wrong-end':True},{'wrong-record':1},{'corrupt-record':1},{'reply':'wrong-id'},{'reply':'wrong-version'}]
        for i,fault in enumerate(faults):
            cache=self.root/str(i)
            with p.local_server(self.collection,faults=fault) as url:
                with self.assertRaises(t.TransferError):self.fetch(url,cache,'stream-batch')
            self.assertFalse((cache/'ready.json').exists())
    def test_verified_callback_precedes_set_publication_and_owned_data_survives(self):
        cache=self.root/'callback';received=[]
        def callback(obj,view):
            self.assertFalse((cache/'ready.json').exists());self.assertTrue(view.readonly);received.append((obj['sha256'],view))
        with p.local_server(self.collection) as url:self.fetch(url,cache,'stream-batch',callback=callback)
        self.assertEqual(len(received),len(self.keys))
        for key,view in received:self.assertEqual(bytes(view),self.collection['objects'][key])
    def test_pending_errors_and_abandoned_iterator_dispose_connection(self):
        cache=self.root/'pending';cache.mkdir();(cache/('sha256-'+self.collection['manifest_id']+'.manifest')).write_bytes(self.collection['manifest'])
        with p.local_server(self.collection,faults={'reply':'wrong-id'}) as url:
            client=p.Client(url)
            with self.assertRaises(t.TransferError):self.fetch(url,cache,'objects-windowed',client=client)
            self.assertTrue(client.disposed);self.assertFalse(client.pending);self.assertFalse((cache/'ready.json').exists())
            with self.assertRaises(t.TransferError):client.connect()
        with p.local_server(self.collection) as url:
            client=p.Client(url);objects=t.parse_manifest(self.collection['manifest'])['objects'];iterator=client.windowed(objects)
            next(iterator);iterator.close();self.assertTrue(client.disposed);self.assertFalse(client.pending)
            fresh=p.Client(url)
            try:self.fetch(url,cache,'objects-windowed',client=fresh)
            finally:fresh.close()
        self.check(cache,'packed')
    def test_pinned_valid_cache_never_connects(self):
        cache=self.root/'offline'
        with p.local_server(self.collection) as url:self.fetch(url,cache,'stream-batch')
        with mock.patch.object(p.socket,'create_connection',side_effect=AssertionError('offline network')):
            sample=self.fetch('gaia-mux://127.0.0.1:1',cache,'stream-batch')
        self.assertEqual(sample['requests'],0);self.check(cache,'packed')


if __name__=='__main__':unittest.main()

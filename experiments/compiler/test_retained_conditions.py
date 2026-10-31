"""Retained plans must emit identical guards and always verify current backing."""
import hashlib
from pathlib import Path
import random
import unittest
from unittest import mock
from types import SimpleNamespace

import condition_index as reference
import incremental_conditions as previous
import retained_conditions as retained
import test_incremental_conditions as old
import test_condition_index as wire


class RetainedDifferentialTests(old.DifferentialTests):
    def setUp(self):
        super().setUp();self.producer=retained.Producer()

    def incremental(self,result=None,cwd=None):
        return self.producer.build(self.store,result or self.result,self.files,self.masks,cwd or self.cwd,self.cache)

    def test_corruption_and_valid_checksum_bad_framing_recompute(self):
        self.incremental();raw=self.cache.read_bytes();self.cache.write_bytes(b'corrupt')
        actual,stats=self.incremental();self.assertEqual(actual,self.expected())
        self.assertEqual(stats['fragment_cache_source'],'memory');self.assertTrue(stats['condition_plan_reused'])
        for bad in (b'',raw[:-1],raw[:-1]+bytes([raw[-1]^1])):
            self.producer.restore(None);self.cache.write_bytes(bad)
            actual,stats=self.incremental();self.assertEqual(actual,self.expected())
            self.assertFalse(stats['fragment_cache_valid']);self.assertEqual(stats['fragment_misses'],3)

    def test_plan_hash_reuse_and_immutable_snapshots(self):
        self.incremental();snapshot=self.producer.snapshot()
        actual,stats=self.incremental();self.assertEqual(actual,self.expected())
        self.assertTrue(stats['namespace_reused']);self.assertTrue(stats['condition_plan_reused'])
        self.assertEqual(stats['logical_hashes_computed'],0)
        self.assertEqual(stats['physical_reads'],stats['positive_files'])
        with self.assertRaises(TypeError):snapshot.fragments[('bad',)]=None
        self.producer.restore(snapshot)
        self.assertEqual(self.incremental()[0],self.expected())

    def test_namespace_masks_and_action_reorder_reclassify(self):
        self.incremental();rng=random.Random(914)
        for _ in range(25):
            self.masks={name:rng.randrange(8) for name in self.files}
            actual,stats=self.incremental();self.assertEqual(actual,self.expected())
            self.assertFalse(stats['namespace_reused'])
        order=[2,0,1];result={k:[v[i] for i in order] for k,v in self.result.items()}
        actual,_=self.incremental(result)
        self.assertEqual(actual,self.expected([self.journals[i] for i in order]))

    def test_current_bytes_and_mutable_buffers_are_not_identity_cached(self):
        self.incremental();name=str(self.root/'src/a.c');self.files[name]=bytearray(b'CCCC');Path(name).write_bytes(self.files[name])
        actual,stats=self.incremental();self.assertEqual(actual,self.expected());self.assertTrue(stats['condition_plan_reused'])
        self.files[name][:]=b'DDDD';Path(name).write_bytes(self.files[name])
        actual,stats=self.incremental();self.assertEqual(actual,self.expected());self.assertGreater(stats['logical_hashes_computed'],0)
        self.assertNotIn(name,self.producer.snapshot().contents)

    def test_bad_backing_does_not_advance_state_and_shrunk_queries_drop_refs(self):
        self.incremental();snapshot=self.producer.snapshot();name=str(self.root/'src/a.c')
        self.files[name]=b'CCCC'
        with self.assertRaises(reference.UnsupportedIndex):self.incremental()
        self.assertIs(self.producer.snapshot(),snapshot)
        Path(name).write_bytes(b'CCCC')
        raw=wire.journal([(2,1,'nothing.h')]);self.journals[0]=raw
        self.result['journal_sha256'][0]=hashlib.sha256(raw).hexdigest()
        self.write_record(self.result['cache_keys'][0],raw,b'object 0')
        actual,_=self.incremental();self.assertEqual(actual,self.expected())
        self.assertNotIn(str(self.root/'inc/é.h'),self.producer.snapshot().contents)
        self.assertEqual(len(self.producer.snapshot().fragments),3)

    def test_oversized_optional_metadata_disables_retention_without_dropping_index(self):
        with mock.patch.object(previous,'encode_cache',side_effect=reference.UnsupportedIndex('byte bound')):
            actual,stats=self.incremental()
        self.assertEqual(actual,self.expected());self.assertFalse(stats['retained']);self.assertIsNone(self.producer.snapshot())

    def test_sized_disk_reader_rejects_oversize_and_growth_after_stat(self):
        self.incremental();size=self.cache.stat().st_size
        for declared in (size-1,previous.MAX_CACHE+1):
            with mock.patch.object(previous.os,'fstat',return_value=SimpleNamespace(st_size=declared)):
                entries,valid=previous.read_cache(self.cache)
            self.assertFalse(valid);self.assertEqual(entries,{})


class RetainedNativeTests(old.IncrementalNativeTests):
    def setUp(self):
        super().setUp();self.producer=retained.Producer()

    def publish(self,value=1,body=None,files=None):
        with mock.patch.object(previous,'build_incremental',side_effect=self.producer.build):
            return super().publish(value,body,files)


if __name__=='__main__':unittest.main()

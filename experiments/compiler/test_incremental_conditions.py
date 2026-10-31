"""Differential condition equivalence, cache invalidation and native boundaries."""
import hashlib
import os
from pathlib import Path
import random
import struct
import tempfile
import unittest
from unittest import mock

import condition_index as reference
import incremental_conditions as optimized
import test_condition_index as original_tests


class DifferentialTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='gaia fragment $ ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=self.root/'store';self.store.mkdir();self.cache=self.root/'fragments'
        self.cwd=str(self.root)
        self.files={str(self.root/name):body for name,body in {
            'src/a.c':b'AAAA','src/b.c':b'BBBB','inc/é.h':b'header A','inc/hidden.h':b'header B','unused.h':b'unused'}.items()}
        for name,body in self.files.items():Path(name).parent.mkdir(parents=True,exist_ok=True);Path(name).write_bytes(body)
        self.masks={name:7 for name in self.files}
        make=original_tests.journal
        self.journals=[
            make([(8,0,''),(1,0,'src/a.c'),(6,0,'inc'),(2,1,'inc/missing.h'),
                  (9,0,'inc'),(3,0,'é.h'),(9,1,'does-not-exist'),(2,1,'optional.h')]),
            make([(3,0,'src/b.c'),(6,0,'.'),(4,0,'inc/hidden.h'),(5,0,'src/a.c'),(7,0,'inc'),(2,1,'ghost/empty.h')]),
            make([(2,1,'nope.h'),(9,0,'nested'),(8,0,''),(2,1,'../inc/missing.h')])]
        self.result={'cache_keys':[],'journal_sha256':[],'object_sha256':[]}
        for i,raw in enumerate(self.journals):
            action=hashlib.sha256(f'action {i}'.encode()).hexdigest();obj=f'object {i}'.encode()
            self.write_record(action,raw,obj)
            self.result['cache_keys'].append(action);self.result['journal_sha256'].append(hashlib.sha256(raw).hexdigest())
            self.result['object_sha256'].append(hashlib.sha256(obj).hexdigest())

    def write_record(self,action,journal,obj):
        rest=struct.pack('<QQ',len(journal),len(obj))+journal+obj;key=bytes.fromhex(action)
        raw=b'GAIADC01'+key+hashlib.sha256(key+rest).digest()+rest
        self.store.joinpath(action+'.gdo').write_bytes(raw)

    def expected(self,journals=None,cwd=None):
        return reference.build_index(journals or self.journals,self.files,self.masks,cwd or self.cwd)[0]

    def incremental(self,result=None,cwd=None):
        return optimized.build_incremental(self.store,result or self.result,self.files,self.masks,cwd or self.cwd,self.cache)

    def test_batched_byte_equivalence_for_masks_and_query_types(self):
        rng=random.Random(2817)
        for _ in range(40):
            self.masks={name:rng.randrange(8) for name in self.files}
            actual,_=optimized.build_batched(self.journals,self.files,self.masks,self.cwd)
            self.assertEqual(actual,self.expected())

    def test_cold_warm_and_reordered_actions(self):
        actual,cold=self.incremental();self.assertEqual(actual,self.expected());self.assertEqual(cold['fragment_misses'],3)
        actual,warm=self.incremental();self.assertEqual(actual,self.expected());self.assertEqual(warm['fragment_hits'],3)
        self.assertEqual(warm['queries_parsed'],0)
        order=[2,0,1];result={key:[values[i] for i in order] for key,values in self.result.items()}
        actual,stats=self.incremental(result);self.assertEqual(actual,self.expected([self.journals[i] for i in order]))
        self.assertEqual(stats['fragment_hits'],3)

    def test_one_changed_selected_journal_decodes_only_one_fragment(self):
        self.incremental();raw=original_tests.journal([(3,0,'src/a.c'),(2,1,'fresh-missing.h')])
        self.journals[0]=raw;self.result['journal_sha256'][0]=hashlib.sha256(raw).hexdigest()
        self.write_record(self.result['cache_keys'][0],raw,b'object 0')
        actual,stats=self.incremental();self.assertEqual(actual,self.expected())
        self.assertEqual((stats['fragment_hits'],stats['fragment_misses']),(2,1))
        self.assertEqual(stats['queries_parsed'],2)

    def test_current_namespace_and_backing_bytes_are_not_cached(self):
        self.incremental();new=str(self.root/'inc/new.h');Path(new).write_bytes(b'new')
        self.files[new]=b'new';self.masks[new]=2
        path=str(self.root/'src/a.c');self.files[path]=b'CCCC';Path(path).write_bytes(b'CCCC')
        self.masks[str(self.root/'inc/hidden.h')]=0
        actual,stats=self.incremental();self.assertEqual(actual,self.expected());self.assertEqual(stats['fragment_hits'],3)
        Path(path).write_bytes(b'wrong bytes')
        with self.assertRaises(reference.UnsupportedIndex):self.incremental()

    def test_action_and_cwd_identity_and_bounded_current_state(self):
        self.incremental();action=hashlib.sha256(b'new flags').hexdigest();self.result['cache_keys'][0]=action
        self.write_record(action,self.journals[0],b'object 0')
        _,stats=self.incremental();self.assertEqual((stats['fragment_hits'],stats['fragment_misses']),(2,1))
        entries,valid=optimized.read_cache(self.cache);self.assertTrue(valid);self.assertEqual(len(entries),3)
        self.assertNotIn(hashlib.sha256(b'action 0').hexdigest(),[key[0] for key in entries])
        cwd=str(self.root/'different');actual,stats=self.incremental(cwd=cwd)
        self.assertEqual(actual,self.expected(cwd=cwd));self.assertEqual(stats['fragment_misses'],3)

    def test_corruption_and_valid_checksum_bad_framing_recompute(self):
        self.incremental();original=self.cache.read_bytes()
        bad_count=bytearray(original[:-32]);bad_count[8:16]=struct.pack('<Q',100001)
        candidates=[b'',original[:-1],original[:-1]+bytes([original[-1]^1]),bytes(bad_count)+hashlib.sha256(bad_count).digest()]
        for bad in candidates:
            self.cache.write_bytes(bad);actual,stats=self.incremental()
            self.assertEqual(actual,self.expected());self.assertFalse(stats['fragment_cache_valid'])
            self.assertEqual(stats['fragment_misses'],3)

    def test_cache_publication_failure_does_not_discard_valid_index(self):
        with mock.patch.object(optimized,'write_cache',side_effect=OSError('cache not writable')):
            actual,stats=self.incremental()
        self.assertEqual(actual,self.expected());self.assertFalse(stats['fragment_cache_published'])

    def test_cached_structure_does_not_require_reopening_selected_objects(self):
        self.incremental()
        with mock.patch.object(reference,'selected_journals',side_effect=AssertionError('unexpected reread')):
            actual,stats=self.incremental()
        self.assertEqual(actual,self.expected());self.assertEqual(stats['fragment_hits'],3)


class BatchedNativeTests(original_tests.SelectiveTests):
    incremental=False
    def publish(self,value=1,body=None,files=None):
        cmd=self.native.request(value,body=body,files=files)
        self.files={str(self.native.source):self.native.source.read_bytes(),**(files or {})}
        self.masks={p:1 for p in self.files};self.ns();self.receipt.unlink(missing_ok=True)
        before=self.call();result=self.native.consume(cmd,value)
        if self.incremental:
            encoded,self.stats=optimized.build_incremental(self.native.cache,result,self.files,self.masks,str(self.root),self.root/'fragments')
        else:
            journals=reference.selected_journals(self.native.cache,result)
            encoded,self.stats=optimized.build_batched(journals,self.files,self.masks,str(self.root))
        self.assertEqual(encoded,reference.build_index(reference.selected_journals(self.native.cache,result),self.files,self.masks,str(self.root))[0])
        self.conditions.write_bytes(encoded)
        self.assertTrue(self.call('selective-record',before['stamp'])['recorded'])
        self.assertTrue(self.call()['hit']);return result


class IncrementalNativeTests(BatchedNativeTests):incremental=True


if __name__=='__main__':unittest.main()

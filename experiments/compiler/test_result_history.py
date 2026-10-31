"""Whole-result reuse must preserve the native condition and output proofs."""
import json
import os
from pathlib import Path
import unittest
from unittest import mock

import result_history as history
import test_condition_index as selective


@unittest.skipUnless(selective.native_tests.DECISION and selective.native_tests.HISTORY and selective.native_tests.LLVM,
                     'Set GAIA_DECISION_HOST, GAIA_HISTORY_HOST and GAIA_LLVM')
class LinkedResultTests(unittest.TestCase):
    rebound=False
    def setUp(self):
        self.f=selective.SelectiveTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.root=self.f.root;self.last=self.f.native.output/'last-result.json'
        self.last.write_text('{}')
        self.artifacts={p.name:p for p in [self.f.native.output/'libanswer.so',self.f.conditions,self.last]}
        self.f.outputs.write_text('GAIA-WATCH-1\n'+'\n'.join(map(str,self.artifacts.values()))+'\n')
        self.cache=history.LinkedResults(self.root/'linked',selective.native_tests.DECISION)

    def publish(self,value=1,body=None,files=None):
        result=self.f.publish(value,body,files);self.last.write_text(json.dumps(result))
        stamp=self.f.call()['stamp']
        if self.rebound:self.assertTrue(self.f.call('selective-record',stamp)['recorded'])
        stored=self.cache.store(self.f.request,self.artifacts,self.f.tools,self.f.namespace,self.f.conditions,stamp,
                                source_receipt=self.f.receipt if self.rebound else None)
        self.assertTrue(stored['stored'],stored);return result

    def restore(self,request=None):
        return self.cache.restore(request or self.f.request,self.artifacts,self.f.tools,self.f.namespace,self.f.conditions,
                                  self.f.receipt,self.f.outputs,self.last.name)

    def source(self,value):self.f.native.source.write_text(f'int answer(void){{return {value};}}\n')

    def test_revert_restores_previous_library_and_current_receipt(self):
        first=self.publish(1);original=self.artifacts['libanswer.so'].read_bytes()
        original_mode=self.artifacts['libanswer.so'].stat().st_mode&0o777
        self.publish(2);self.source(1)
        result,stats=self.restore();self.assertTrue(stats['hit']);self.assertEqual(stats['candidates'],2)
        self.assertEqual(result['object_sha256'],first['object_sha256'])
        self.assertEqual(self.artifacts['libanswer.so'].read_bytes(),original)
        self.assertEqual(self.artifacts['libanswer.so'].stat().st_mode&0o777,original_mode)
        self.assertTrue(self.f.call()['hit'])

    def test_unconditional_copy_hash_rejects_preserved_metadata_corruption(self):
        self.publish();entry=self.cache.root/self.cache.catalog()[0]['id'];library=entry/'libanswer.so'
        stamp=library.stat();body=bytearray(library.read_bytes());body[-1]^=1;library.write_bytes(body)
        os.utime(library,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        result,stats=self.restore();self.assertIsNone(result);self.assertFalse(stats['hit'])

    def test_request_tools_and_negative_visibility_are_part_of_proof(self):
        body='#if __has_include("optional.h")\n#include "optional.h"\n#else\n#define ANSWER 1\n#endif\nint answer(void){return ANSWER;}\n'
        self.publish(body=body)
        self.assertIsNone(self.restore('d'*64)[0])
        optional=self.root/'optional.h';optional.write_bytes(b'#define ANSWER 2\n')
        self.f.ns({**self.f.masks,str(optional):1});self.assertIsNone(self.restore()[0])
        self.f.ns({**self.f.masks,str(optional):0});self.assertTrue(self.restore()[1]['hit'])
        marker=self.root/'new-tool';marker.write_bytes(b'changed admitted tools')
        with self.f.tools.open('a') as stream:stream.write(str(marker)+'\n')
        self.assertIsNone(self.restore()[0])

    def test_input_mutation_during_restore_cannot_publish_receipt(self):
        self.publish(1);self.publish(2);self.source(1)
        original=history.atomic_write
        def mutate(path,body):
            original(path,body)
            if Path(path)==self.artifacts['libanswer.so']:self.source(3)
        with mock.patch.object(history,'atomic_write',side_effect=mutate):
            with self.assertRaises(history.InputsChanged):self.restore()
        self.assertFalse(self.f.receipt.exists())

    def test_eviction_quota_catalog_corruption_and_optional_write_failure(self):
        for value in (1,2,3,4):self.publish(value)
        entries=self.cache.catalog();self.assertEqual(len(entries),3)
        self.assertLessEqual(sum(e['bytes'] for e in entries),self.cache.max_bytes)
        self.source(1);self.assertIsNone(self.restore()[0])
        self.source(3);self.assertTrue(self.restore()[1]['hit'])
        catalog=self.cache.root/'catalog';catalog.write_bytes(b'corrupt')
        self.assertIsNone(self.restore()[0])
        catalog.write_bytes(b'[]');self.assertIsNone(self.restore()[0])
        small=history.LinkedResults(self.root/'too-small',selective.native_tests.DECISION,max_bytes=100)
        stamp=self.f.call()['stamp']
        self.assertFalse(small.store(self.f.request,self.artifacts,self.f.tools,self.f.namespace,self.f.conditions,stamp)['stored'])
        with mock.patch.object(history,'atomic_write',side_effect=OSError('publication unavailable')):
            self.assertFalse(self.cache.store(self.f.request,self.artifacts,self.f.tools,self.f.namespace,self.f.conditions,stamp)['stored'])
        self.assertTrue(self.artifacts['libanswer.so'].is_file())


class ReboundResultTests(LinkedResultTests):
    rebound=True

    def test_completed_proof_and_copied_artifact_must_agree(self):
        self.publish()
        path=self.artifacts['libanswer.so'];data=bytearray(path.read_bytes());data[-1]^=1;path.write_bytes(data)
        result=self.cache.store(self.f.request,self.artifacts,self.f.tools,self.f.namespace,self.f.conditions,'0'*64,source_receipt=self.f.receipt)
        self.assertFalse(result['stored'])
        self.assertIn('completed artifact changed',result['error'])


if __name__=='__main__':unittest.main()

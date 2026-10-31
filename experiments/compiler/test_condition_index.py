"""Compiler-derived conditions plus finite virtual-namespace boundary tests."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import unittest

import condition_index as index
import test_build_decisions as native_tests


def journal(records):
    raw=bytearray(b'GAIAJR01'+struct.pack('<I',len(records)))
    for op,outcome,path in records:
        name=path.encode();raw+=struct.pack('<BBI',op,outcome,len(name))+name+bytes(32)
    return raw


class FormatTests(unittest.TestCase):
    def test_namespace_validation_and_empty_job_root(self):
        nodes=index.namespace_nodes({'/root/a':1,'/root/hidden':0})
        self.assertEqual(nodes['/'][1],(1<<64)-1)
        for paths in ({'/a/../b':1},{'/a':1,'/a/child':2},{'/a':0,'/a/child':1}):
            with self.assertRaises(index.UnsupportedIndex):index.encode_namespace(paths)

    def test_journal_framing_limits(self):
        raw=journal([(2,1,'missing')]);self.assertEqual(index.decode_journal(raw),[(2,1,'missing')])
        for bad in (raw[:-1],raw+b'x',b'GAIAJR01'+struct.pack('<I',65537)):
            with self.assertRaises(index.UnsupportedIndex):index.decode_journal(bad)


@unittest.skipUnless(native_tests.DECISION and native_tests.HISTORY and native_tests.LLVM,
                     'Set GAIA_DECISION_HOST, GAIA_HISTORY_HOST and GAIA_LLVM')
class SelectiveTests(unittest.TestCase):
    def setUp(self):
        self.native=native_tests.HistoricalCandidateTests('runTest');self.native.setUp();self.addCleanup(self.native.doCleanups)
        self.root=self.native.root;self.receipt=self.root/'receipt';self.conditions=self.root/'conditions'
        self.namespace=self.root/'namespace';self.tools=self.root/'tools';self.outputs=self.root/'outputs'
        self.tools.write_text('GAIA-WATCH-1\n'+str(Path(native_tests.HISTORY).resolve())+'\n'+str(Path(native_tests.DECISION).resolve())+'\n')
        self.outputs.write_text('GAIA-WATCH-1\n'+str(self.native.output/'libanswer.so')+'\n'+str(self.conditions)+'\n')
        self.request='c'*64;self.files={};self.masks={}

    def call(self,mode='selective-check',stamp=None,request=None):
        args=[native_tests.DECISION,mode,str(self.receipt),request or self.request,str(self.tools),str(self.outputs),str(self.namespace),str(self.conditions)]
        if stamp is not None:args.append(stamp)
        p=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);return json.loads(p.stdout)

    def ns(self,masks=None):self.namespace.write_bytes(index.encode_namespace(masks or self.masks))

    def publish(self,value=1,body=None,files=None):
        cmd=self.native.request(value,body=body,files=files)
        self.files={str(self.native.source):self.native.source.read_bytes(),**(files or {})}
        self.masks={p:1 for p in self.files};self.ns();self.receipt.unlink(missing_ok=True)
        before=self.call();result=self.native.consume(cmd,value)
        journals=index.selected_journals(self.native.cache,result)
        encoded,self.stats=index.build_index(journals,self.files,self.masks,str(self.root));self.conditions.write_bytes(encoded)
        self.assertTrue(self.call('selective-record',before['stamp'])['recorded'])
        self.assertTrue(self.call()['hit']);return result

    def test_unread_content_and_membership_do_not_launch_pipeline(self):
        unused=self.root/'unused.h';unused.write_bytes(b'/* A */')
        self.publish(files={str(unused):unused.read_bytes()})
        unused.write_bytes(b'/* different unused bytes */');self.assertTrue(self.call()['hit'])
        new=self.root/'new.h';new.write_bytes(b'/* newly admitted unrelated input */')
        self.ns({**self.masks,str(new):1});self.assertTrue(self.call()['hit'])
        # Check the real LLVM journal also accepts this membership change.
        cmd=self.native.request(1,files={str(unused):unused.read_bytes(),str(new):new.read_bytes()})
        self.assertEqual(self.native.consume(cmd,1)['compiler_executions'],0)

    def test_positive_read_mutation_removal_and_equal_content_touch(self):
        self.publish();self.native.source.write_bytes(self.files[str(self.native.source)])
        hit=self.call();self.assertTrue(hit['hit']);self.assertGreater(hit['content_hashes'],0)
        self.native.source.write_text('int answer(void){return 2;}\n');self.assertFalse(self.call()['hit'])
        self.native.source.unlink();self.assertFalse(self.call()['hit'])

    def test_negative_header_appearance_uses_virtual_visibility(self):
        body='#if __has_include("optional.h")\n#include "optional.h"\n#else\n#define ANSWER 1\n#endif\nint answer(void){return ANSWER;}\n'
        self.publish(body=body)
        optional=self.root/'optional.h';optional.write_bytes(b'#define ANSWER 2\n')
        self.assertTrue(self.call()['hit'])  # Physical presence is not VFS admission.
        self.ns({**self.masks,str(optional):0});self.assertTrue(self.call()['hit'])
        self.ns({**self.masks,str(optional):1});self.assertFalse(self.call()['hit'])
        self.publish(2,body,files={str(optional):optional.read_bytes()})
        self.ns({p:m for p,m in self.masks.items() if p!=str(optional)})
        self.assertFalse(self.call()['hit'])

    def test_earlier_include_shadowing_invalidates(self):
        early=self.root/'early';late=self.root/'late';early.mkdir();late.mkdir()
        self.native.command[1:1]=['-I'+str(early),'-I'+str(late)]
        choice=late/'choice.h';choice.write_bytes(b'#define ANSWER 1\n')
        body='#include <choice.h>\nint answer(void){return ANSWER;}\n'
        self.publish(body=body,files={str(choice):choice.read_bytes()})
        shadow=early/'choice.h';shadow.write_bytes(b'#define ANSWER 2\n')
        self.ns({**self.masks,str(shadow):1});self.assertFalse(self.call()['hit'])
        self.publish(2,body,files={str(choice):choice.read_bytes(),str(shadow):shadow.read_bytes()})

    def test_directory_membership_model_and_view_masks(self):
        # The compiler fixture does not enumerate directories. Exercise the
        # explicit provider's listing semantics with synthetic query journals.
        d=self.root/'dir';d.mkdir();a=d/'a.h';a.write_bytes(b'A')
        self.publish(files={str(a):b'A'})
        encoded,_=index.build_index([journal([(6,0,str(d))])],self.files,self.masks,str(self.root))
        self.receipt.unlink();before=self.call();self.conditions.write_bytes(encoded)
        self.assertTrue(self.call('selective-record',before['stamp'])['recorded'])
        b=d/'b.h';b.write_bytes(b'B');self.ns({**self.masks,str(b):1});self.assertFalse(self.call()['hit'])
        self.ns({**self.masks,str(b):2});self.assertTrue(self.call()['hit'])  # Hidden from job zero.
        self.ns({str(self.native.source):1});self.assertFalse(self.call()['hit'])

    def test_missing_parent_and_relative_cwd_conditions(self):
        self.publish()
        records=[(8,0,''),(9,0,'subdir'),(2,1,'optional.h')]
        encoded,_=index.build_index([journal(records)],self.files,self.masks,str(self.root))
        self.receipt.unlink();before=self.call();self.conditions.write_bytes(encoded)
        self.assertTrue(self.call('selective-record',before['stamp'])['recorded'])
        child=self.root/'subdir/other.h';child.parent.mkdir();child.write_bytes(b'new')
        self.ns({**self.masks,str(child):1});self.assertFalse(self.call()['hit'])

    def test_corrupt_index_request_outputs_and_changed_tool_miss(self):
        self.publish();self.assertFalse(self.call(request='d'*64)['hit'])
        raw=self.conditions.read_bytes();self.conditions.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
        self.assertFalse(self.call()['hit']);self.conditions.write_bytes(raw)
        self.native.output.joinpath('libanswer.so').write_bytes(b'corrupt');self.assertFalse(self.call()['hit'])
        tool=self.root/'tool-identity';tool.write_bytes(b'tool version one')
        self.tools.write_text(self.tools.read_text()+str(tool)+'\n');self.publish()
        tool.write_bytes(b'tool version two');self.assertFalse(self.call()['hit'])

    def test_mutation_during_build_prevents_record(self):
        self.publish();self.receipt.unlink();before=self.call()
        self.native.source.write_text('int answer(void){return 2;}\n')
        self.assertFalse(self.call('selective-record',before['stamp'])['recorded'])


if __name__=='__main__':unittest.main()

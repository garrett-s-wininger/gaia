"""Native receipt and bounded-history correctness; opt in with explicit hosts."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import project_benchmark as wire

DECISION=os.environ.get('GAIA_DECISION_HOST')
HISTORY=os.environ.get('GAIA_HISTORY_HOST')
LLVM=os.environ.get('GAIA_LLVM')


@unittest.skipUnless(DECISION,'Set GAIA_DECISION_HOST to the lightweight native host')
class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='gaia receipt $ ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.write_bytes(b'input')
        self.output=self.root/'output';self.output.write_bytes(b'compiled output')
        self.watch=self.root/'watch';self.watch.write_text('GAIA-WATCH-1\n'+str(self.source)+'\n')
        self.outputs=self.root/'outputs';self.outputs.write_text('GAIA-WATCH-1\n'+str(self.output)+'\n')
        self.receipt=self.root/'receipt'

    def call(self,mode='check',stamp=None,request='a'*64):
        cmd=[DECISION,mode,str(self.receipt),request,str(self.watch),str(self.outputs)]+([stamp] if stamp else [])
        p=subprocess.run(cmd,capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr);return json.loads(p.stdout)

    def record(self):
        before=self.call();self.assertTrue(self.call('record',before['stamp'])['recorded'])
        self.assertTrue(self.call()['hit'])

    def test_success_restart_and_request_changes(self):
        self.assertFalse(self.call()['hit']);self.record()
        self.assertTrue(self.call()['hit'])  # Fresh process each call, no resident state.
        self.assertFalse(self.call(request='b'*64)['hit'])
        self.source.write_bytes(b'changed input');self.assertFalse(self.call()['hit'])

    def test_missing_and_corrupt_outputs(self):
        self.record();self.output.write_bytes(b'damaged output')
        self.assertFalse(self.call()['hit'])
        self.output.unlink();self.assertFalse(self.call()['hit'])

    def test_unchanged_bytes_with_new_output_metadata_are_validated(self):
        self.record();self.output.write_bytes(b'compiled output')
        self.assertTrue(self.call()['hit'])

    def test_changed_inputs_during_build_cannot_publish(self):
        before=self.call();self.source.write_bytes(b'edited during compilation')
        self.assertFalse(self.call('record',before['stamp'])['recorded'])
        self.assertFalse(self.receipt.exists())

    def test_missing_inputs_cannot_hit_or_publish(self):
        self.record();self.source.unlink();before=self.call()
        self.assertFalse(before['hit']);self.assertFalse(before['inputs_present'])
        self.assertFalse(self.call('record',before['stamp'])['recorded'])

    def test_receipt_corruption_and_valid_checksum_bad_framing(self):
        self.record();original=self.receipt.read_bytes()
        for data in (b'',original[:50],b'badmagic'+original[8:],original[:-1]+bytes([original[-1]^1])):
            self.receipt.write_bytes(data);self.assertFalse(self.call()['hit'])
        damaged=bytearray(original[:-32]);damaged[104:112]=(10000).to_bytes(8,'little')
        self.receipt.write_bytes(damaged+hashlib.sha256(damaged).digest());self.assertFalse(self.call()['hit'])

    def test_output_list_and_watch_membership_changes_invalidate(self):
        self.record();other=self.root/'other';other.write_bytes(b'compiled output')
        self.outputs.write_text('GAIA-WATCH-1\n'+str(other)+'\n');self.assertFalse(self.call()['hit'])
        self.outputs.write_text('GAIA-WATCH-1\n'+str(self.output)+'\n')
        self.watch.write_text('GAIA-WATCH-1\n'+str(self.source)+'\n'+str(other)+'\n')
        self.assertFalse(self.call()['hit'])


@unittest.skipUnless(HISTORY and LLVM,'Set GAIA_HISTORY_HOST and GAIA_LLVM')
class HistoricalCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='gaia history ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'unit.c';self.cache=self.root/'cache';self.cache.mkdir()
        self.output=self.root/'out';self.output.mkdir()
        llvm=Path(LLVM);self.clang=llvm/'bin/clang';self.lld=llvm/'bin/ld.lld'
        self.command=[str(self.clang),'--target=x86_64-unknown-linux-gnu','-x','c','-O1','-fPIC',
            '-Werror=date-time','-nostdinc','-c',str(self.source),'-o','unit.o']
        self.link=[str(self.lld),'-shared','-o','libanswer.so','unit.o']
        self.linkplan=self.root/'link.gcr';self.linkplan.write_bytes(wire.encode_requests([self.link]))
        self.views=self.root/'views';self.views.write_text('GAIACV1\n1\n')
        self.seen={}

    def request(self,value,extra=(),mode='journal-history',body=None,files=None):
        self.source.write_text(body or f'int answer(void){{return {value};}}\n')
        inputs={str(self.source):self.source.read_bytes(),**(files or {})}
        for name,content in (files or {}).items():Path(name).write_bytes(content)
        self.views.write_text('GAIACV1\n'+'1\n'*len(inputs))
        blob=self.root/'inputs';blob.write_bytes(wire.encode_inputs(inputs))
        plan=self.root/'plan';plan.write_bytes(wire.encode_requests([[*self.command,*extra]]))
        return [HISTORY,'memory',str(self.clang),str(self.root),str(blob),hashlib.sha256(blob.read_bytes()).hexdigest(),
            str(self.output),str(plan),'1','internal',str(self.lld),str(self.linkplan),'direct',mode,str(self.cache),str(self.views),'b'*64]

    def consume(self,cmd,value):
        p=subprocess.run(cmd,cwd=self.output,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
        d=json.loads(p.stdout);self.assertTrue(d['correct']);self.assertEqual(d['cache_write_errors'],0)
        # Compare to an independently compiled/linked CLI reference.
        ref=self.root/'ref';ref.mkdir(exist_ok=True)
        actual=self.command.copy();actual[actual.index('-o')+1]=str(ref/'unit.o')
        subprocess.run(actual,capture_output=True,check=True)
        subprocess.run(self.link,cwd=ref,capture_output=True,check=True)
        self.assertEqual(d['object_sha256'],[hashlib.sha256((ref/'unit.o').read_bytes()).hexdigest()])
        self.assertEqual((self.output/'libanswer.so').read_bytes(),(ref/'libanswer.so').read_bytes())
        subprocess.run([sys.executable,'-c','import ctypes,sys; p=ctypes.CDLL(sys.argv[1]); assert p.answer()==int(sys.argv[2])',
                        str(self.output/'libanswer.so'),str(value)],check=True,capture_output=True)
        return d

    def build(self,value):return self.consume(self.request(value),value)

    def test_history_revert_eviction_and_corruption(self):
        for value in (1,2,3,4):self.assertEqual(self.build(value)['compiler_executions'],1)
        self.assertEqual(len(list(self.cache.glob('*.gdo'))),3)
        self.assertEqual(self.build(1)['compiler_executions'],1)  # Oldest was evicted.
        hit=self.build(3);self.assertEqual(hit['compiler_executions'],0);self.assertEqual(hit['historical_hits'],1)
        for p in self.cache.glob('*.gdo'):
            b=bytearray(p.read_bytes());b[-1]^=1;p.write_bytes(b)
        self.assertEqual(self.build(3)['compiler_executions'],1)
        self.assertFalse(list(self.cache.glob('*.tmp.*')))

    def test_exact_flags_remain_part_of_action_identity(self):
        self.build(1)
        cmd=self.request(1,extra=('-DUNRELATED=1',))
        p=subprocess.run(cmd,cwd=self.output,capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)['compiler_executions'],1)

    def test_negative_lookup_appearance_and_historical_absence(self):
        body='#if __has_include("optional.h")\n#include "optional.h"\n#else\n#define ANSWER 1\n#endif\nint answer(void){return ANSWER;}\n'
        cmd=self.request(1,body=body);self.assertEqual(self.consume(cmd,1)['compiler_executions'],1)
        optional=self.root/'optional.h'
        cmd=self.request(2,body=body,files={str(optional):b'#define ANSWER 2\n'})
        self.assertEqual(self.consume(cmd,2)['compiler_executions'],1)
        optional.unlink();cmd=self.request(1,body=body)
        hit=self.consume(cmd,1);self.assertEqual(hit['compiler_executions'],0);self.assertEqual(hit['historical_hits'],1)

    def test_concurrent_publication_and_single_candidate_control(self):
        cmd=self.request(1)
        requests=[]
        for i in range(2):
            out=self.root/('writer-'+str(i));out.mkdir();argv=cmd.copy();argv[6]=str(out);requests.append((argv,out))
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(lambda pair:subprocess.run(pair[0],cwd=pair[1],capture_output=True,text=True),requests))
        for p in results:self.assertEqual(p.returncode,0,p.stderr);self.assertTrue(json.loads(p.stdout)['correct'])
        self.assertEqual(self.build(1)['compiler_executions'],0)
        self.assertLessEqual(len(list(self.cache.glob('*.gdo'))),3)
        shutil.rmtree(self.cache);self.cache.mkdir()
        for value in (1,2,1):
            d=self.consume(self.request(value,mode='journal'),value);self.assertEqual(d['compiler_executions'],1)


if __name__=='__main__':unittest.main()

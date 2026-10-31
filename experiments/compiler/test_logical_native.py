"""Real C++ compiler journals feed the logical generation publication contract."""
import hashlib
import json
import os
from pathlib import Path
import unittest

import condition_index as reference
from logical_workspace import Workspace,Checker,LogicalEmitter,logical_projection
from retained_conditions import Producer
import test_shared_history as previous

@unittest.skipUnless(os.environ.get('GAIA_SHARED_INPUTS')=='1','set shared native providers')
class LogicalNativeTests(unittest.TestCase):
    def setUp(self):
        self.native=previous.SharedHistoryTests('runTest');self.native.setUp();self.addCleanup(self.native.doCleanups)
        self.root=self.native.root;self.index=self.root/'logical';self.receipt=self.root/'logical-receipt';self.watch=self.root/'logical-tools';self.outputs=self.root/'logical-outputs'
        self.host=Path(os.environ['GAIA_HISTORY_HOST']).resolve();self.watch.write_text('GAIA-WATCH-1\n'+str(self.host)+'\n')
        self.outputs.write_text('GAIA-WATCH-1\n'+str(self.native.output/'libanswer.so')+'\n'+str(self.index)+'\n')
        self.producer=Producer(LogicalEmitter());self.request='d'*64
    def call(self,mode='selective-check',stamp=None):
        argv=['logical',mode,str(self.receipt),self.request,str(self.watch),str(self.outputs),'unused',str(self.index)]
        if stamp is not None:argv.append(stamp)
        return self.checker.call(argv)
    def setup_generation(self):
        cmd=self.native.request(1);files=dict(self.native.session.state.files);self.workspace=Workspace(files,{n:1 for n in files},1)
        self.checker=Checker(self.workspace,{str(self.host):hashlib.sha256(self.host.read_bytes()).hexdigest()})
        before=self.call();captured=self.workspace.snapshot();result=self.native.consume(cmd,1)
        wire,stats=self.producer.build(self.native.cache,result,captured.files,captured.masks,str(self.root),self.root/'logical-fragments')
        expected=reference.build_index(reference.selected_journals(self.native.cache,result),captured.files,captured.masks,str(self.root))[0]
        self.assertEqual(wire,logical_projection(expected));self.assertEqual(stats['physical_reads'],0);self.index.write_bytes(wire)
        return before
    def test_unrelated_epoch_update_preserves_real_compiler_completion(self):
        before=self.setup_generation();self.workspace.apply({str(self.root/'unrelated'):b'new admitted file'})
        self.assertTrue(self.call('selective-record',before['stamp'])['recorded']);self.assertTrue(self.call()['hit'])
    def test_relevant_update_after_real_compile_refuses_current_receipt(self):
        before=self.setup_generation();self.workspace.apply({str(self.native.source):b'int answer(void){return 2;}\n'})
        result=self.call('selective-record',before['stamp']);self.assertFalse(result['recorded']);self.assertFalse(self.receipt.exists())

if __name__=='__main__':unittest.main()

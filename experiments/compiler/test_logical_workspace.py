"""Selective immutable generations preserve input and output publication proofs."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import struct
from unittest import mock

import logical_workspace as logical
import condition_index as reference
from test_condition_index import journal

class LogicalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.a=self.root/'a.c';self.b=self.root/'unused';self.a.write_bytes(b'aaa');self.b.write_bytes(b'bbb')
        self.files={str(self.a):b'aaa',str(self.b):b'bbb'};self.masks={n:1 for n in self.files};self.workspace=logical.Workspace(self.files,self.masks,1)
        self.tool=self.root/'compiler';self.tool.write_bytes(b'compiler');self.watch=self.root/'tools';self.watch.write_text('GAIA-WATCH-1\n'+str(self.tool)+'\n')
        self.output=self.root/'output';self.output.write_bytes(b'correct artifact');self.index=self.root/'index';self.receipt=self.root/'receipt';self.outputs=self.root/'outputs'
        self.outputs.write_text('GAIA-WATCH-1\n'+str(self.output)+'\n'+str(self.index)+'\n')
        self.checker=logical.Checker(self.workspace,{str(self.tool):hashlib.sha256(b'compiler').hexdigest()})
        self.request='a'*64;self.emit([(3,0,str(self.a))])
    def emit(self,records):
        wire,_=reference.build_index([journal(records)],self.files,self.masks,str(self.root))
        self.index.write_bytes(logical.logical_projection(wire));return logical.decode_index(self.index.read_bytes())
    def call(self,mode='selective-check',stamp=None):
        argv=['checker',mode,str(self.receipt),self.request,str(self.watch),str(self.outputs),'unused-physical-namespace',str(self.index)]
        if stamp is not None:argv.append(stamp)
        return self.checker.call(argv)
    def test_epoch_updates_are_selective_and_compare_exchange_is_explicit(self):
        rows=logical.decode_index(self.index.read_bytes());old=self.workspace.snapshot()
        same,stats=self.workspace.apply({str(self.a):bytes(bytearray(b'aaa'))});self.assertIs(same,old);self.assertFalse(stats['changed'])
        changed,_=self.workspace.apply({str(self.b):b'new'},expected=old.number);self.assertTrue(logical.validate(rows,changed)[0]);self.assertEqual(old.files[str(self.b)],b'bbb')
        with self.assertRaises(logical.GenerationChanged):self.workspace.apply({str(self.a):b'new'},expected=old.number)
        changed,_=self.workspace.apply({str(self.a):b'new'});self.assertFalse(logical.validate(rows,changed)[0])
        with self.assertRaises(TypeError):old.files[str(self.a)]=b'mutated'
    def test_unreported_physical_edits_do_not_mutate_authoritative_state(self):
        rows=logical.decode_index(self.index.read_bytes());self.a.write_bytes(b'physical mirror edited')
        self.assertTrue(logical.validate(rows,self.workspace.head)[0])
        self.workspace.apply({str(self.a):self.a.read_bytes()});self.assertFalse(logical.validate(rows,self.workspace.head)[0])
    def test_negative_visibility_directory_and_listing_semantics(self):
        optional=self.root/'optional.h';rows=self.emit([(2,1,str(optional))]);self.assertTrue(logical.validate(rows,self.workspace.head)[0])
        self.workspace.apply({str(optional):b'x'},masks={**self.masks,str(optional):0});self.assertTrue(logical.validate(rows,self.workspace.head)[0])
        self.workspace.apply({},masks={**self.masks,str(optional):1});self.assertFalse(logical.validate(rows,self.workspace.head)[0])
        rows=self.emit([(6,0,str(self.root))]);self.assertFalse(logical.validate(rows,self.workspace.head)[0])
    def test_publication_checks_current_generation_and_allows_unrelated_edits(self):
        before=self.call();captured=self.checker.capture(before['stamp']);self.workspace.apply({str(self.b):b'after capture'})
        self.assertIsNot(captured,self.workspace.head);self.assertTrue(self.call('selective-record',before['stamp'])['recorded']);self.assertTrue(self.call()['hit'])
        self.receipt.unlink();before=self.call();self.workspace.apply({str(self.a):b'changed while compiling'})
        result=self.call('selective-record',before['stamp']);self.assertFalse(result['recorded']);self.assertFalse(result['inputs_unchanged']);self.assertFalse(self.receipt.exists())
    def test_output_corruption_request_and_tool_changes_are_rejected(self):
        before=self.call();self.assertTrue(self.call('selective-record',before['stamp'])['recorded']);self.assertTrue(self.call()['hit'])
        self.output.write_bytes(b'bad artifact');self.assertFalse(self.call()['hit']);self.output.write_bytes(b'correct artifact')
        self.request='b'*64;self.assertFalse(self.call()['hit']);self.request='a'*64
        self.tool.write_bytes(b'compiler changed')
        with self.assertRaises(ValueError):self.call()
    def test_codec_bounds_and_mutable_admission(self):
        data=self.index.read_bytes()
        for bad in (b'',data[:-1],data+b'x',b'GAIACQ01'+data[8:]):
            with self.assertRaises(ValueError):logical.decode_index(bad)
        value=bytearray(b'owned');self.workspace.apply({str(self.b):value});value[0]=120;self.assertEqual(self.workspace.head.files[str(self.b)],b'owned')
        old=self.workspace.head
        with self.assertRaises(ValueError):self.workspace.apply({'/a/../bad':b'bad'})
        self.assertIs(self.workspace.head,old)
    def test_full_history_horizon_keeps_original_capture_until_record(self):
        before=self.call()
        for _ in range(3):self.call('selective-history-check')
        self.assertTrue(self.call('selective-record',before['stamp'])['recorded'])
    def test_generation_lock_protects_publication(self):
        import threading
        started=threading.Event();finished=threading.Event();original=logical.atomic_write;thread=None
        def write(path,body):
            nonlocal thread
            def update():started.set();self.workspace.apply({str(self.a):b'later'});finished.set()
            thread=threading.Thread(target=update);thread.start();self.assertTrue(started.wait(1));self.assertFalse(finished.is_set());original(path,body)
        before=self.call()
        with mock.patch.object(logical,'atomic_write',side_effect=write):self.assertTrue(self.call('selective-record',before['stamp'])['recorded'])
        thread.join(2);self.assertTrue(finished.is_set());self.assertFalse(self.call()['hit'])

    def test_randomized_generation_checks_match_independent_reference(self):
        import random
        rng=random.Random(741);names=[str(self.a),str(self.b),str(self.root/'optional.h')]
        state={n:(b'initial '+str(i).encode()) for i,n in enumerate(names)};visibility={n:3 for n in state}
        workspace=logical.Workspace(state,visibility,2)
        queries=[journal([(3,0,names[0]),(2,1,names[2]),(6,0,str(self.root))]),journal([(3,0,names[1]),(2,1,str(self.root/'missing/deep.h'))])]
        def wire():
            for n,b in state.items():Path(n).write_bytes(b)
            return logical.logical_projection(reference.build_index(queries,state,visibility,str(self.root))[0])
        for _ in range(80):
            old=wire();rows=logical.decode_index(old)
            name=rng.choice(names)
            if name not in state:
                state[name]=b'new';visibility[name]=rng.randrange(4);workspace.apply({name:state[name]},masks=visibility)
            elif rng.randrange(3)==0 and len(state)>1:
                del state[name];del visibility[name];Path(name).unlink(missing_ok=True);workspace.apply({},deleted=[name],masks=visibility)
            else:
                state[name]=rng.randbytes(rng.randrange(20));visibility[name]=rng.randrange(4);workspace.apply({name:state[name]},masks=visibility)
            self.assertEqual(logical.validate(rows,workspace.head)[0],old==wire())

    def test_physical_adapter_charges_reads_and_rejects_racing_import(self):
        self.a.write_bytes(b'imported');old=self.workspace.head
        generation,stats=logical.import_physical(self.workspace,self.files,self.masks)
        self.assertEqual(generation.files[str(self.a)],b'imported');self.assertEqual(stats['physical_reads'],2);self.assertEqual(stats['stat_calls'],4)
        self.assertEqual(old.files[str(self.a)],b'aaa')
        original=logical.bounded;before=self.workspace.head
        def read(path,limit):
            body=original(path,limit)
            if path==self.b:self.a.write_bytes(b'changed while importing')
            return body
        with mock.patch.object(logical,'bounded',side_effect=read):
            with self.assertRaises(logical.GenerationChanged):logical.import_physical(self.workspace,self.files,self.masks)
        self.assertIs(self.workspace.head,before)

if __name__=='__main__':unittest.main()

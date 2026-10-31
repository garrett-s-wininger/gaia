"""Same snapshot bytes without a producer subprocess or old-bundle reread."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import dependency_cache_benchmark as delta
import inline_snapshot as inline
import project_benchmark as wire
import test_build_decisions as native


class InlineSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='gaia inline $ ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.blob=self.root/'out';self.views=self.root/'views'
        self.files={str(self.root/'a'):b'\0raw\xff',str(self.root/'é'):b'old'}
        self.masks={p:3 for p in self.files}

    def test_wire_identity_and_masks(self):
        result=inline.publish(self.files,self.masks,2,self.blob,self.views)
        self.assertEqual(self.blob.read_bytes(),wire.encode_inputs(self.files))
        self.assertEqual(result['pin'],hashlib.sha256(self.blob.read_bytes()).hexdigest())
        self.assertEqual(result['view_pin'],hashlib.sha256(self.views.read_bytes()).hexdigest())
        self.assertEqual(result['loose_reads'],0)

    def test_invalid_inputs_do_not_replace_outputs(self):
        self.blob.write_bytes(b'old');self.views.write_bytes(b'old views')
        for files,masks,jobs in [({}, {}, 1),(self.files,{},2),({'relative':b'x'},{'relative':1},1),
                                  ({'/a/../b':b'x'},{'/a/../b':1},1),({'/a':b'x'},{'/a':4},2)]:
            with self.assertRaises(ValueError):inline.publish(files,masks,jobs,self.blob,self.views)
            self.assertEqual(self.blob.read_bytes(),b'old');self.assertEqual(self.views.read_bytes(),b'old views')
        with mock.patch.object(inline.os,'replace',side_effect=OSError('publication failure')):
            with self.assertRaises(OSError):inline.publish(self.files,self.masks,2,self.blob,self.views)
        self.assertFalse(list(self.root.glob('*.tmp.*')))

    @unittest.skipUnless(os.environ.get('GAIA_SNAPSHOT_HOST'),'Set GAIA_SNAPSHOT_HOST')
    def test_native_delta_equivalence_with_add_remove_contents_and_masks(self):
        base=self.root/'base';base.write_bytes(wire.encode_inputs(self.files))
        masks=self.root/'base.views';masks.write_text('GAIACV1\n3\n3\n')
        variant={str(self.root/'a'):b'new',str(self.root/'added'):b'added'}
        new_masks={str(self.root/'a'):1,str(self.root/'added'):2}
        sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
        patch,_=delta.delta_bytes(self.files,variant,new_masks,sha(base),sha(masks))
        change=self.root/'delta';change.write_bytes(patch)
        old=self.root/'native';old_views=self.root/'native.views'
        p=subprocess.run([os.environ['GAIA_SNAPSHOT_HOST'],'delta',str(base),str(masks),str(change),
                          str(old),str(old_views),'-','2'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        result=inline.publish(variant,new_masks,2,self.blob,self.views)
        self.assertEqual(old.read_bytes(),self.blob.read_bytes());self.assertEqual(old_views.read_bytes(),self.views.read_bytes())
        self.assertEqual(json.loads(p.stdout)['pin'],result['pin'])

    @unittest.skipUnless(native.HISTORY and native.LLVM,'Set GAIA_HISTORY_HOST and GAIA_LLVM')
    def test_native_consumer_validation_and_corruption(self):
        fixture=native.HistoricalCandidateTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        cmd=fixture.request(3,mode='journal-history-memo')
        files={str(fixture.source):fixture.source.read_bytes()}
        result=inline.publish(files,{p:1 for p in files},1,Path(cmd[4]),fixture.views)
        cmd[5]=result['pin'];fixture.consume(cmd,3)
        damaged=bytearray(Path(cmd[4]).read_bytes());damaged[-2]^=1;Path(cmd[4]).write_bytes(damaged)
        p=subprocess.run(cmd,cwd=fixture.output,capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0)


if __name__=='__main__':unittest.main()

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'compiler/followthrough'))
from run_ir import Host


@unittest.skipUnless(os.environ.get('GAIA_PASS_HOST'),'set GAIA_PASS_HOST')
class PassTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'unit.c';self.output=self.root/'unit.o'
        self.command=[os.environ.get('GAIA_CLANG','/usr/lib/llvm22/bin/clang'),'-O2','-Werror=date-time','-c',str(self.source),'-o',str(self.output)]
        self.host=Host(Path(os.environ['GAIA_PASS_HOST']),self.root);self.addCleanup(self.host.close)
        self.body='unsigned f(unsigned a,unsigned n){unsigned s=0;for(unsigned i=0;i<n;++i){if(i&1)s+=a^i;else s+=a+i;}return s;}\n'
        self.source.write_text(self.body)

    def oracle(self):
        target=self.root/'oracle.o';cmd=list(self.command);cmd[-1]=str(target)
        subprocess.run(cmd,capture_output=True,check=True);return target.read_bytes()

    def call(self,**options):return self.host.call(self.command,self.root,self.output,**options)

    def test_real_llvm_analyses_and_backend_agree(self):
        expected=self.oracle();counts=None
        for pipeline in ('serial','parallel'):
            for speculate in (False,True):
                row=self.call(mode='native',pipeline=pipeline,speculate=speculate)
                self.assertTrue(row['ok'],row);self.assertEqual(self.output.read_bytes(),expected)
                value=(row['dom'],row['loops'],row['postdom'],row['dom_sha256'],row['postdom_sha256'])
                self.assertGreater(value[0],0);self.assertGreater(value[1],0)
                if counts is None:counts=value
                self.assertEqual(value,counts)

    def test_speculative_hit_discards_private_output(self):
        row=self.call(store=True);self.assertTrue(row['ok']);expected=self.output.read_bytes()
        self.source.write_text(self.body+'typedef long unused;\n')
        row=self.call(speculate=True,pipeline='parallel')
        self.assertTrue(row['ok']);self.assertTrue(row['hit']);self.assertTrue(row['speculation_canceled'])
        self.assertEqual(self.output.read_bytes(),expected)
        self.assertFalse(list(self.root.glob('*.speculative*')))

    def test_speculative_miss_matches_cli(self):
        self.call(store=True);self.source.write_text(self.body+'unsigned another(unsigned x){return x+17;}\n')
        row=self.call(speculate=True)
        self.assertTrue(row['ok'],row);self.assertFalse(row['hit']);self.assertEqual(self.output.read_bytes(),self.oracle())

    def test_error_failure_and_worker_recovery(self):
        self.source.write_text('int f(void){__asm__("gaia_invalid_instruction");return 1;}\n')
        row=self.call(speculate=True,pipeline='parallel');self.assertFalse(row['ok']);self.assertIn('invalid instruction',row['stderr'])
        self.source.write_text(self.body);row=self.call(speculate=True,pipeline='parallel');self.assertTrue(row['ok']);self.assertEqual(self.output.read_bytes(),self.oracle())

    def test_fork_contract_rejects_extra_outputs(self):
        args=self.command[:1]+['-MMD']+self.command[1:]
        row=self.host.call(args,self.root,self.output,speculate=True)
        self.assertFalse(row['ok']);self.assertIn('object-only',row['error'])

    def test_fork_contract_rejects_side_outputs_and_forwarding(self):
        for option in ('-gsplit-dwarf','--coverage','-fsave-optimization-record',
                       '-foptimization-record-file=side.yaml','-Xclang','-mllvm','@hidden.rsp'):
            with self.subTest(option=option):
                args=self.command[:1]+[option]+self.command[1:]
                row=self.host.call(args,self.root,self.output,speculate=True)
                self.assertFalse(row['ok']);self.assertIn('object-only',row['error'])
        self.assertFalse(list(self.root.glob('*.speculative*')))
        # Ordinary warning options must not be confused with -Wa forwarding.
        args=self.command[:1]+['-Wall','-Wextra','-Wa,--noexecstack']+self.command[1:]
        self.assertTrue(self.host.call(args,self.root,self.output,speculate=True)['ok'])

    def test_publication_failure_reaps_and_removes_unique_staging(self):
        sentinel=self.root/'unit.o.speculative';sentinel.write_bytes(b'existing unrelated output')
        self.output.mkdir()
        row=self.host.request(dict(args=self.command,cwd=str(self.root),output=str(self.output),
                                   context='fixed',mode='ir',analysis='off',speculate=True,pipeline='parallel'))
        self.assertFalse(row['ok']);self.assertIn('publication failed',row['error'])
        self.assertEqual(sentinel.read_bytes(),b'existing unrelated output')
        self.assertEqual(list(self.root.glob('*.speculative*')),[sentinel])
        self.output.rmdir();row=self.call(speculate=True,pipeline='parallel')
        self.assertTrue(row['ok']);self.assertEqual(self.output.read_bytes(),self.oracle())

    def test_discard_large_backend_leaves_no_staging_files(self):
        self.source.write_text(''.join(f'unsigned f{i}(unsigned x){{for(unsigned j=0;j<20;++j)x=(x+j)^(x>>1);return x;}}\n' for i in range(300)))
        first=self.call(store=True);self.assertTrue(first['ok']);expected=self.output.read_bytes()
        row=self.call(speculate=True);self.assertTrue(row['ok']);self.assertTrue(row['hit']);self.assertEqual(self.output.read_bytes(),expected)
        self.assertFalse(list(self.root.glob('*.speculative*')))


@unittest.skipUnless(os.environ.get('GAIA_CHILD_HARNESS'),'set GAIA_CHILD_HARNESS')
class ChildLifecycleTests(unittest.TestCase):
    def test_records_larger_than_pipe_capacity_and_cancellation(self):
        for mode in ('large-success','over-bound','cancel','cancel-blocked'):
            with self.subTest(mode=mode):
                subprocess.run([os.environ['GAIA_CHILD_HARNESS'],mode],check=True,capture_output=True,timeout=10)


if __name__=='__main__':unittest.main()

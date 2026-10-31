import os
from pathlib import Path
import tempfile
import unittest
from run import Host,sources,call,command


@unittest.skipUnless(os.environ.get('GAIA_OBSERVED_HOST'),'set GAIA_OBSERVED_HOST and GAIA_CLANG')
class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.host=Host(Path(os.environ['GAIA_OBSERVED_HOST']),self.root);self.addCleanup(self.host.close)
        self.clang=Path(os.environ.get('GAIA_CLANG','/usr/lib/llvm22/bin/clang'));self.files=sources()
        self.generation=0;self.admit(self.files)
    def admit(self,files):
        result=self.host.request(dict(edits={str(self.root/n):v for n,v in files.items()},source_root=str(self.root),expected_generation=self.generation));self.assertTrue(result['ok']);self.generation=result['generation'];return result
    def compile(self,index=0):return call(self.host,self.clang,self.root,self.root/f'unit{index}.o',index,0,self.generation,'observed')

    def test_hit_restores_outputs_and_stale_generation_rejected(self):
        first=self.compile();self.assertTrue(first['ok']);self.assertFalse(first['validation_hit'])
        obj=(self.root/'unit0.o').read_bytes();dep=(self.root/'unit0.d').read_bytes();(self.root/'unit0.o').unlink();(self.root/'unit0.d').unlink()
        self.assertTrue(self.compile()['validation_hit']);self.assertEqual((self.root/'unit0.o').read_bytes(),obj);self.assertEqual((self.root/'unit0.d').read_bytes(),dep)
        self.assertFalse(call(self.host,self.clang,self.root,self.root/'unit0.o',0,0,self.generation-1,'observed')['ok'])

    def test_ir_hit_refreshes_observations_and_current_depfile(self):
        self.compile();self.admit({'unit0.c':self.files['unit0.c'].replace('"a.h"','"b.h"')});row=self.compile();self.assertTrue(row['hit']);self.assertFalse(row['validation_hit'])
        contents=[o['path'] for o in row['observations'] if o['kind']=='content'];self.assertIn(str(self.root/'b.h'),contents);self.assertNotIn(str(self.root/'a.h'),contents)
        self.assertIn('b.h',(self.root/'unit0.d').read_text());self.admit({'a.h':'#define VALUE 99\n'});self.assertTrue(self.compile()['validation_hit'])
        self.admit({'b.h':'#define VALUE 7\n'});self.assertFalse(self.compile()['validation_hit'])

    def test_optional_negative_and_shadowing_observations(self):
        first=self.compile(1);self.assertTrue(any(o['value']=='absent' and o['path'].endswith('optional.h') for o in first['observations']))
        self.admit({'early/optional.h':'#define EXTRA 6\n'});self.assertFalse(self.compile(1)['validation_hit']);self.admit({'early/optional.h':None});self.assertFalse(self.compile(1)['validation_hit'])
        self.admit({'early/selected.h':'#define VALUE 8\n'});self.assertFalse(self.compile(1)['validation_hit'])

    def test_diagnostics_are_not_suppressed_by_validation_skip(self):
        self.admit({'unit0.c':'#warning current diagnostic\n'+self.files['unit0.c']})
        for _ in range(2):
            row=self.compile();self.assertTrue(row['ok']);self.assertGreater(row['warnings'],0);self.assertFalse(row['validation_hit'])

    def test_volatile_macro_is_not_cached_even_when_warnings_disabled(self):
        self.admit({'unit0.c':'const char *date=__DATE__;\nint f0(void){return 1;}\n'})
        out=self.root/'unit0.o';args=command(self.clang,self.root,out,0,0,out.with_suffix('.d'));args.remove('-Werror=date-time');args.insert(1,'-w')
        for _ in range(2):
            row=self.host.request(dict(args=args,cwd=str(self.root),output=str(out),mode='observed',context='fixed',analysis='off',store=True,logical=True,generation=self.generation))
            self.assertTrue(row['ok']);self.assertTrue(row['volatile_macro']);self.assertFalse(row['validation_hit'])

    def test_directory_membership_is_observed_by_native_interface(self):
        first=self.host.request(dict(probe_directory=str(self.root/'early')));self.assertTrue(first['ok'])
        self.admit({'early/new.h':'new\n'});second=self.host.request(dict(probe_directory=str(self.root/'early')))
        self.assertTrue(second['ok']);self.assertNotEqual(first['value'],second['value']);self.assertIn(str(self.root/'early/new.h'),second['names'])

    def test_physical_input_outside_admitted_namespace_cannot_seed_cache(self):
        out=self.root/'unit0.o';args=command(self.clang,self.root,out,0,0,out.with_suffix('.d'));args[args.index('-c')+1]='/tmp/not-admitted-input.c'
        row=self.host.request(dict(args=args,cwd=str(self.root),output=str(out),mode='observed',context='fixed',analysis='off',store=True,logical=True,generation=self.generation))
        self.assertFalse(row['ok']);self.assertIn('admitted',row['error'])


if __name__=='__main__':unittest.main()

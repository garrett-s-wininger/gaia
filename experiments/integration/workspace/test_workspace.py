import os,tempfile,unittest,subprocess
from pathlib import Path
from protocol import Host,admit,request,scan

@unittest.skipUnless(os.environ.get('GAIA_WORKSPACE_HOST'),'set GAIA_WORKSPACE_HOST')
class IntegrationTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.host=Host(Path(os.environ['GAIA_WORKSPACE_HOST']),self.root);self.addCleanup(self.host.close)
  self.files={'main.cc':'#include "active.h"\n#if __has_include("optional.h")\n#include "optional.h"\n#endif\nint gaia_f(){return VALUE;}\n','active.h':'#include "a.h"\n','a.h':'#define VALUE 1\n','b.h':'#define VALUE 1\n'}
  self.gen=admit(self.host,self.root,self.files,0);self.cmd=[os.environ.get('GAIA_CLANG','/usr/lib/llvm22/bin/clang++'),'-std=c++14','-O2','-Werror=date-time','-I'+str(self.root),'-MMD','-MF','main.d','-MT','main.o','-c','main.cc','-o','main.o']
 def compile(self,analysis=False):return request(self.host,self.root,self.cmd,'main',self.gen,analysis=analysis)
 def test_symbols_match_independent_syntax_and_physical_object(self):
  build=self.compile();obj=(self.root/'main.o').read_bytes();facts=build['facts'];self.assertTrue(any('gaia_f' in x for x in facts['matches']))
  self.assertEqual(facts,self.compile(True)['facts']);self.assertEqual(scan(self.host,['main'],self.gen)['dirty'],[])
  for n,b in self.files.items():(self.root/n).write_text(b)
  subprocess.run(self.cmd,cwd=self.root,check=True,capture_output=True);self.assertEqual(obj,(self.root/'main.o').read_bytes())
 def test_refresh_after_identical_ir_rewire(self):
  self.compile();self.gen=admit(self.host,self.root,{'active.h':'#include "b.h"\n'},self.gen);self.assertEqual(scan(self.host,['main'],self.gen)['dirty'],['main']);row=self.compile();self.assertTrue(row['hit'])
  self.gen=admit(self.host,self.root,{'a.h':'#define VALUE 9\n'},self.gen);self.assertEqual(scan(self.host,['main'],self.gen)['dirty'],[])
  self.gen=admit(self.host,self.root,{'b.h':'#define VALUE 8\n'},self.gen);self.assertEqual(scan(self.host,['main'],self.gen)['dirty'],['main'])
 def test_absence_current_error_and_stale_generation(self):
  self.compile();self.gen=admit(self.host,self.root,{'optional.h':'int gaia_optional;\n'},self.gen);self.assertEqual(scan(self.host,['main'],self.gen)['dirty'],['main']);self.assertTrue(any('gaia_optional' in x for x in self.compile()['facts']['matches']))
  self.assertFalse(self.host.request(dict(scan=['main'],generation=self.gen-1,context='configuration-0'))['ok'])
  self.gen=admit(self.host,self.root,{'main.cc':'int broken(;\n'},self.gen)
  with self.assertRaises(RuntimeError):self.compile()
  self.assertEqual(scan(self.host,['main'],self.gen)['dirty'],['main'])
 def test_configuration_and_unknown_target_are_dirty(self):
  self.compile();self.assertEqual(scan(self.host,['main','unknown'],self.gen)['dirty'],['unknown']);self.assertEqual(scan(self.host,['main'],self.gen,'configuration-1')['dirty'],['main'])

if __name__=='__main__':unittest.main()

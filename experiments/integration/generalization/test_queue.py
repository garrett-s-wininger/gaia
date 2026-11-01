import os,sys,tempfile,unittest,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'refinements'))
from refined_protocol import Host,admit,require

@unittest.skipUnless(os.environ.get('GAIA_QUEUE_HOST'),'set GAIA_QUEUE_HOST')
class QueueTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.h=Host(Path(os.environ['GAIA_QUEUE_HOST']),self.root/'log',True);self.addCleanup(self.h.close)
  self.g=admit(self.h,self.root,{'a.cc':'int a(){return 1;}\n','b.cc':'int b(){return 2;}\n'},0)
 def compile(self,name):
  output=str(self.root/(name+'.o'));args=['/usr/lib/llvm22/bin/clang++','-O2','-MMD','-MF',str(self.root/(name+'.d')),'-c',str(self.root/(name+'.cc')),'-o',output]
  return self.h.request(dict(args=args,cwd=str(self.root),output=output,target=name,generation=self.g,context='test',family='test',mode='observed',analysis='off',logical=True,store=True,emit_facts=True,defer_backend=True)),args
 def test_pipeline_requires_drain_and_preserves_objects(self):
  r,a=self.compile('a');self.assertTrue(r['backend_pending']);self.assertFalse(r['artifact_ready']);self.assertFalse((self.root/'a.o').exists())
  r,b=self.compile('b');self.assertTrue(r['backend_pending']);self.assertTrue((self.root/'a.o').exists());self.assertFalse((self.root/'b.o').exists())
  self.assertFalse(self.h.request(dict(edits={},source_root=str(self.root),expected_generation=self.g))['ok'])
  d=require(self.h.request({'drain':True}));self.assertEqual(d['children'],2)
  for name,args,body in [('a',a,'int a(){return 1;}\n'),('b',b,'int b(){return 2;}\n')]:
   p=self.root/(name+'.cc');p.write_text(body);expected=(self.root/(name+'.o')).read_bytes();subprocess.run(args,check=True);self.assertEqual(expected,(self.root/(name+'.o')).read_bytes())
  self.assertEqual(list(self.root.glob('*.speculative.*')),[])
 def test_backend_failure_is_deferred_then_recoverable(self):
  self.g=admit(self.h,self.root,{'a.cc':'int a(){__asm__("invalid_gaia_instruction");return 1;}\n'},self.g)
  row,_=self.compile('a');self.assertTrue(row['backend_pending']);self.assertFalse(self.h.request({'drain':True})['ok']);self.assertFalse((self.root/'a.o').exists())
  self.g=admit(self.h,self.root,{'a.cc':'int a(){return 1;}\n'},self.g);self.compile('a');require(self.h.request({'drain':True}));self.assertTrue((self.root/'a.o').exists());self.assertEqual(list(self.root.glob('*.speculative.*')),[])
 def test_shutdown_discards_pending_child_and_stage(self):
  self.compile('a');self.h.close();self.h.close=lambda:None
  self.assertEqual(list(self.root.glob('*.speculative.*')),[])
 def test_previous_backend_failure_stops_next_dispatch(self):
  self.g=admit(self.h,self.root,{'a.cc':'int a(){__asm__("invalid_gaia_instruction");return 1;}\n'},self.g)
  self.compile('a');row,_=self.compile('b');self.assertFalse(row['ok']);self.assertFalse((self.root/'b.o').exists());self.assertEqual(list(self.root.glob('*.speculative.*')),[])
  require(self.h.request({'drain':True}));self.compile('b');require(self.h.request({'drain':True}));self.assertTrue((self.root/'b.o').exists())

if __name__=='__main__':unittest.main()

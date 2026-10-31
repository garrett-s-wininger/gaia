"""Optional real compiler lifecycle/edit checks; GAIA_JVM_PREPARED selects setup."""
import json,os,shutil,tempfile,unittest
from pathlib import Path
import benchmark as b
HERE=Path(__file__).resolve().parent
PREPARED=os.environ.get('GAIA_JVM_PREPARED')
@unittest.skipUnless(PREPARED,'set GAIA_JVM_PREPARED to prepared.json from benchmark setup')
class CompilerLifecycleTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='jvm-compiler-check-',dir=HERE/'_work');cls.root=Path(cls.temp.name);cls.data=json.loads(Path(PREPARED).read_text())
  for field,name in (('source','source'),('second_source','second')):
   target=cls.root/name;shutil.copytree(cls.data[field],target);cls.data[field]=str(target)
  cls.data['outputs']=str(cls.root/'outputs');(cls.root/'broken').mkdir();(cls.root/'broken/Broken.java').write_text('class Broken { void wrong( }\n')
  cls.single=b.cli(cls.data,'test-reference',True);cls.pair=b.cli_pair(cls.data,'test-pair-reference')
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 @staticmethod
 def signature(value):return {k:value[k] for k in ('classes','bytes','sha256')}
 def test_memory_output_reaches_real_consumer_without_loose_classes(self):
  s=b.Session(self.data,memory=True)
  try:
   value=s.call('memory-check');self.assertTrue(value['ok']);self.assertEqual(self.signature(value),self.signature(self.single));self.assertFalse((Path(self.data['outputs'])/'memory-check').exists())
   self.assertEqual(s.call('check')['versions'],self.data['target_versions'][:1])
  finally:s.close()
 def test_private_pool_joint_targets_constant_edit_and_failure_recovery(self):
  s=b.Session(self.data,pool=True);source=Path(self.data['source'])/'picocli/CommandLine.java';old=source.read_bytes();info=source.stat()
  try:
   self.assertEqual(self.signature(s.call('pair-initial')),self.signature(self.pair));self.assertEqual(s.call('check')['versions'],self.data['target_versions'])
   source.write_bytes(old.replace(b'public static final String VERSION = "4.7.7";',b'public static final String VERSION = "4.7.7-gaia-probe";'));os.utime(source,ns=(info.st_atime_ns,info.st_mtime_ns))
   reference=b.cli_pair(self.data,'test-edited-reference');changed=s.call('pair-edited');self.assertTrue(changed['ok']);self.assertEqual(self.signature(changed),self.signature(reference));self.assertNotEqual(self.signature(changed),self.signature(self.pair));self.assertEqual(s.call('check')['versions'],['4.7.7-gaia-probe']*2)
   source.write_bytes(old);os.utime(source,ns=(info.st_atime_ns,info.st_mtime_ns))
   failure=s.call('fail');self.assertFalse(failure['ok']);self.assertIn('compiler.err.',failure['error'])
   recovered=s.call('pair-recovered');self.assertTrue(recovered['ok']);self.assertEqual(self.signature(recovered),self.signature(self.pair));self.assertEqual(s.call('check')['versions'],self.data['target_versions'])
  finally:source.write_bytes(old);os.utime(source,ns=(info.st_atime_ns,info.st_mtime_ns));s.close()
 def test_trained_cache_does_not_freeze_target_compilation(self):
  if 'aot_cache' not in self.data:self.skipTest('prepare --train to test a trained cache')
  s=b.Session(self.data,aot=True)
  try:
   value=s.call('pair-untrained-version-change');self.assertTrue(value['ok']);self.assertEqual(self.signature(value),self.signature(self.pair));self.assertEqual(s.call('check')['versions'],self.data['target_versions'])
  finally:s.close()
if __name__=='__main__':unittest.main()

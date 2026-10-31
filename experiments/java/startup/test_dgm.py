"""Optional real patched-runtime semantic checks; GAIA_DGM_RUN selects raw run."""
import json,os,subprocess,tempfile,unittest,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
RUN=os.environ.get('GAIA_DGM_RUN')
@unittest.skipUnless(RUN,'set GAIA_DGM_RUN to a completed DGM run results.json')
class DgmRuntimeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.data=json.loads(Path(RUN).read_text());cls.work=Path(cls.data['work']);cls.jdk=Path(os.environ.get('GAIA_JDK',HERE/'_work/toolchain/jdk-25.0.5.0.3')).resolve()
  cls.variants={'stock':(HERE/'_work/downloads/groovy-6.0.0.jar').resolve()}
  cls.variants.update({v:cls.work/'patched'/v/('groovy-'+v+'.jar') for v in cls.data['preparation']['variants']})
 def invoke(self,variant,mode,seed=5,extra=None,expect=True):
  token='check-'+variant+'-'+mode+'-'+str(seed);cp=[self.variants[variant],self.work/'phases.jar']
  if extra:cp.append(extra)
  cmd=[str(self.jdk/'bin/java'),'-Xshare:on','-XX:SharedArchiveFile='+str(self.work/(variant+'.jsa')),'-cp',os.pathsep.join(str(p) for p in cp),'FrameworkPhases',mode,token,str(seed)]
  # The archive includes Picocli as second fixed classpath entry.
  cmd[cmd.index('-cp')+1]=str(self.variants[variant])+os.pathsep+str((HERE/'_work/downloads/picocli-4.7.7.jar').resolve())+os.pathsep+os.pathsep.join(str(p) for p in cp[1:])
  p=subprocess.run(cmd,capture_output=True,text=True,env=dict(os.environ,GAIA_REQUEST_TOKEN=token))
  if not expect:return p
  self.assertEqual(p.returncode,0,p.stdout+p.stderr);value=json.loads(p.stdout);self.assertEqual(value['token'],token);return value
 def test_record_descriptors_and_registry_fresh_binding(self):
  identity=None
  for variant in self.variants:
   value=self.invoke(variant,'records');actual=(value['records'],value['digest'])
   if identity is None:identity=actual
   self.assertEqual(actual,identity)
   self.assertEqual(self.invoke(variant,'registry')['result'],'ready')
 def test_dynamic_metaclass_replacement_and_private_loader(self):
  for variant in self.variants:
   self.assertEqual(self.invoke(variant,'metaclass',11)['result'],'14')
   self.assertEqual(self.invoke(variant,'loader',17)['result'],'24')
 def test_new_classpath_extension_is_discovered_and_required(self):
  with tempfile.TemporaryDirectory(prefix='gaia-groovy-extension-') as name:
   root=Path(name);classes=root/'classes';classes.mkdir()
   p=subprocess.run([str(self.jdk/'bin/javac'),'--release','17','-d',str(classes),str(HERE/'GaiaExtensions.java')],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr)
   extension=root/'extension.jar'
   with zipfile.ZipFile(extension,'w') as z:
    for p in classes.rglob('*.class'):z.write(p,p.relative_to(classes).as_posix())
    z.writestr('META-INF/groovy/org.codehaus.groovy.runtime.ExtensionModule','moduleName=gaia-dgm-probe\nmoduleVersion=1\nextensionClasses=GaiaExtensions\nstaticExtensionClasses=\n')
   for variant in self.variants:
    self.assertEqual(self.invoke(variant,'extension',9,extension)['result'],'hello_9')
    missing=self.invoke(variant,'extension',9,expect=False);self.assertNotEqual(missing.returncode,0);self.assertIn('MissingMethodException',missing.stderr)
if __name__=='__main__':unittest.main()

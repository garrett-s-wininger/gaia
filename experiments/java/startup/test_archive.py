"""Meaningful archive validity boundaries, separate from performance samples."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
JDK=Path(os.environ.get('GAIA_JDK',HERE/'_work/toolchain/jdk-25.0.5.0.3'))

@unittest.skipUnless((JDK/'bin/java').exists(),'set GAIA_JDK to a matching JDK')
class ArchiveTests(unittest.TestCase):
    def test_selected_class_is_not_an_initialized_heap(self):
        with tempfile.TemporaryDirectory(prefix='gaia-java-init-') as name:
            root=Path(name);classes=root/'classes';classes.mkdir()
            source=root/'Probe.java'
            source.write_text('''import java.nio.file.*;
public class Probe {
 static String value = System.getenv("GAIA_PROBE_TOKEN");
 static { try { Files.writeString(Path.of(System.getenv("GAIA_PROBE_MARKER")), value); }
          catch (Exception e) { throw new ExceptionInInitializerError(e); } }
 public static void main(String[] args) { System.out.println(value); }
}
''')
            self.run_java_tool('javac','-d',str(classes),str(source))
            jar=root/'probe.jar';self.run_java_tool('jar','--create','--file',str(jar),'-C',str(classes),'.')
            cl=root/'classes.list';cl.write_text((JDK/'lib/classlist').read_text()+'\nProbe\n')
            archive=root/'probe.jsa';marker=root/'marker'
            env=dict(os.environ,GAIA_PROBE_TOKEN='dump-time',GAIA_PROBE_MARKER=str(marker))
            self.run_java_tool('java','-Xshare:dump','-XX:SharedClassListFile='+str(cl),'-XX:SharedArchiveFile='+str(archive),'-cp',str(jar),env=env)
            self.assertFalse(marker.exists(),'explicit app static initializer executed during dump')
            for token in ('first-launch','second-launch'):
                log=root/(token+'.log')
                p=self.run_java_tool('java','-Xshare:on','-XX:SharedArchiveFile='+str(archive),'-Xlog:class+load=info:file='+str(log),'-cp',str(jar),'Probe',
                                     env=dict(os.environ,GAIA_PROBE_TOKEN=token,GAIA_PROBE_MARKER=str(marker)))
                self.assertEqual(p.stdout.strip(),token);self.assertEqual(marker.read_text(),token)
                self.assertIn('Probe source: shared objects file',log.read_text())
            # An archive is bound to the archived classpath artifacts, not a
            # timeless library object. -Xshare:on must reject replacement bytes.
            with jar.open('ab') as stream:stream.write(b'changed-archive-identity')
            p=subprocess.run([str(JDK/'bin/java'),'-Xshare:on','-XX:SharedArchiveFile='+str(archive),'-cp',str(jar),'Probe'],capture_output=True,text=True,env=env)
            self.assertNotEqual(p.returncode,0)
            self.assertIn('Unable to use shared archive',p.stderr+p.stdout)

    @staticmethod
    def run_java_tool(tool,*args,env=None):
        p=subprocess.run([str(JDK/'bin'/tool),*args],capture_output=True,text=True,env=env)
        if p.returncode:raise AssertionError(p.stdout+p.stderr)
        return p

if __name__=='__main__':unittest.main()

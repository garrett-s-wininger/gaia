"""Optional same-manager edit/failure/GC test using a completed topology setup."""
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

from run_topology import Group,base

PREPARED=os.environ.get('GAIA_TOPOLOGY_PREPARED')

@unittest.skipUnless(PREPARED,'set GAIA_TOPOLOGY_PREPARED to a topology prepared.json')
class LifecycleTests(unittest.TestCase):
    def test_failure_retry_same_path_edit_gc_and_restore(self):
        here=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix='topology-check-',dir=here/'_work') as temp:
            work=Path(temp);data=json.loads(Path(PREPARED).read_text());original_expected=list(data['expected']);original_versions=list(data['target_versions'])
            for key in ('source','second_source'):
                dest=work/key;shutil.copytree(data[key],dest);data[key]=str(dest)
            data['work']=str(work);data['outputs']=str(work/'outputs');empty=work/'empty';empty.mkdir();data['compilation_classpath']=str(empty)
            (work/'broken').mkdir();(work/'broken/Broken.java').write_text('class Broken { void invalid( }\n')
            group=Group(data,work,2,1,4,1536,2)
            try:
                group.batch('before');self.assertFalse(group.sessions[0].call('run fail 0 2')['ok']);self.assertFalse(group.sessions[0].call('check')['ok']);group.batch('retry')
                source=Path(data['source'])/'picocli/CommandLine.java';body=source.read_bytes();stamp=source.stat();new=body.replace(b'public static final String VERSION = "4.7.7";',b'public static final String VERSION = "4.7.7-topology";')
                self.assertNotEqual(body,new);source.write_bytes(new);os.utime(source,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
                result=base.cli(data,'edited-reference',True);data['expected'][0]={key:result[key] for key in ('classes','bytes','sha256')};data['target_versions'][0]='4.7.7-topology'
                group.batch('edited');group.gc_diagnostic();group.consume()
                self.assertFalse(group.sessions[0].call('run bounds 0 9')['ok']);group.batch('afterbounds')
                source.write_bytes(body);os.utime(source,ns=(stamp.st_atime_ns,stamp.st_mtime_ns));data['expected']=original_expected;data['target_versions']=original_versions
                group.batch('restored');group.consume();group.stop()
            except Exception:group.abort();raise

if __name__=='__main__':unittest.main()

"""Incremental graph/state correctness checks for the matched build harness."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import ninja_benchmark as bench

NINJA=os.environ.get('GAIA_TEST_NINJA') or shutil.which('ninja')
CC=shutil.which('cc')


class DeltaTests(unittest.TestCase):
    def test_scan_reads_changed_files_and_elides_same_content(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'input';p.write_bytes(b'old')
            stats={str(p):(p.stat().st_mtime_ns,p.stat().st_size)}
            files={str(p):b'old'}
            edits,scan=bench.observed_delta(files,stats)
            self.assertEqual(edits,{})
            self.assertEqual(scan,dict(stat_calls=1,changed_file_reads=0))
            p.write_bytes(b'new content')
            edits,scan=bench.observed_delta(files,stats)
            self.assertEqual(edits,{str(p):b'new content'})
            self.assertEqual(scan['changed_file_reads'],1)
            p.write_bytes(b'old');os.utime(p,ns=(stats[str(p)][0]+1000000,stats[str(p)][0]+1000000))
            edits,scan=bench.observed_delta(files,stats)
            self.assertEqual(edits,{})
            self.assertEqual(scan['changed_file_reads'],1)


@unittest.skipUnless(NINJA and CC,'Ninja and C compiler required')
class IncrementalGraphTests(unittest.TestCase):
    def test_depfiles_noop_revert_and_engine_log_isolation(self):
        with tempfile.TemporaryDirectory(prefix='gaia graph $ ') as temp:
            root=Path(temp);source=root/'source';source.mkdir()
            src=source/'unit.c';src.write_text('#include "value.h"\nint value(void){return VALUE;}\n')
            header=source/'value.h';header.write_text('#define VALUE 1\n')
            cmd=[CC,'-fPIC','-c',str(src),'-o','unit.o']
            link=[CC,'-shared','-o','libzstd.so','unit.o']
            outputs=[root/'engine A',root/'engine B']
            def build(out):
                bench.write_ninja(out/'build.ninja',[cmd],link,source,out)
                p=subprocess.run([NINJA,'-f',str(out/'build.ninja')],cwd=source,capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stderr)
                return p.stdout
            for out in outputs:
                out.mkdir();self.assertIn('CC unit.o',build(out))
                self.assertTrue((out/'.ninja_log').is_file())
                self.assertTrue((out/'.ninja_deps').is_file())
            self.assertFalse((source/'.ninja_log').exists())
            for out in outputs:self.assertIn('no work to do',build(out))
            initial=bench.base.sha(outputs[0]/'unit.o')
            header.write_text('#define VALUE 2\n')
            self.assertIn('CC unit.o',build(outputs[0]))
            self.assertNotEqual(initial,bench.base.sha(outputs[0]/'unit.o'))
            header.write_text('#define VALUE 1\n')
            self.assertIn('CC unit.o',build(outputs[0]))
            self.assertEqual(initial,bench.base.sha(outputs[0]/'unit.o'))
            self.assertIn('no work to do',build(outputs[0]))
            (source/'unused.h').write_text('/* not consumed */\n')
            self.assertIn('no work to do',build(outputs[0]))


if __name__=='__main__':unittest.main()

"""Exercise the real launcher, cache counters and produced object bytes."""
import os,tempfile,unittest
from pathlib import Path
import run as replay

@unittest.skipUnless(replay.CCACHE.exists() and replay.NINJA.exists(),'prepare comparison tools')
class ControlTests(unittest.TestCase):
 def test_resource_sampler_finds_children_spawned_by_pool_threads(self):
  import subprocess,concurrent.futures
  from diagnose import descendants
  with concurrent.futures.ThreadPoolExecutor(1) as pool:
   process=pool.submit(subprocess.Popen,['/bin/cat'],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL).result()
   try:self.assertIn(process.pid,descendants(os.getpid()))
   finally:process.stdin.close();process.wait(timeout=10)
 def test_rendered_cmake_launcher_produces_a_real_cache_hit(self):
  with tempfile.TemporaryDirectory() as temporary:
   p=Path(temporary);cmake=replay.WORK/'sources/cmake-4.1.2-linux-x86_64/bin/cmake'
   (p/'CMakeLists.txt').write_text('cmake_minimum_required(VERSION 3.20)\nproject(control C)\nadd_library(control OBJECT main.c)\n')
   (p/'main.c').write_text('int control(void){return 42;}\n')
   replay.shell([cmake,'-S',p,'-B',p/'build','-G','Ninja','-DCMAKE_C_COMPILER=/usr/lib/llvm22/bin/clang',f'-DCMAKE_MAKE_PROGRAM={replay.NINJA}'],p)
   rules=p/'build/CMakeFiles/rules.ninja';rules.write_text(replay.install_launcher(rules.read_text()));replay.verify_launcher(p/'build','control')
   previous=dict(replay.ENV)
   try:
    replay.ENV.update(CCACHE_DIR=str(p/'cache'),CCACHE_TEMPDIR=str(p/'tmp'));(p/'tmp').mkdir()
    replay.shell([replay.NINJA,'control'],p/'build');obj=p/'build/CMakeFiles/control.dir/main.c.o';expected=obj.read_bytes();obj.unlink();before=replay.cache_stats(p)
    replay.shell([replay.NINJA,'control'],p/'build');after=replay.cache_stats(p)
    self.assertEqual(expected,obj.read_bytes());self.assertGreater(after['direct_cache_hit']+after['preprocessed_cache_hit'],before['direct_cache_hit']+before['preprocessed_cache_hit']);self.assertGreater(after['files_in_cache'],0)
   finally:replay.ENV.clear();replay.ENV.update(previous)

if __name__=='__main__':unittest.main()

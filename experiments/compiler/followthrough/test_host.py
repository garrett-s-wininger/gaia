"""Independent compiler and namespace regression checks for the experimental host."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from run_ir import Host,boundary_probes,sha

@unittest.skipUnless(os.environ.get('GAIA_IR_HOST'),'set GAIA_IR_HOST and optionally GAIA_CLANG')
class HostTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.host=Host(Path(os.environ['GAIA_IR_HOST']),self.root);self.addCleanup(self.host.close);self.clang=os.environ.get('GAIA_CLANG','/usr/lib/llvm22/bin/clang');self.source=self.root/'source.c';self.output=self.root/'current.o';self.command=[self.clang,'-O2','-c',str(self.source),'-o',str(self.output)]
 def oracle(self,body):
  self.source.write_text(body);reference=self.root/'oracle.o';command=self.command.copy();command[-1]=str(reference);subprocess.run(command,check=True,capture_output=True);return reference.read_bytes()
 def test_seven_codegen_and_diagnostic_boundaries(self):
  self.assertEqual(len(boundary_probes(self.host,self.root,self.clang)),7)
 def test_command_and_external_context_separate_cache(self):
  self.source.write_text('int f(void){return 1;}\n');self.assertTrue(self.host.call(self.command,self.root,self.output,store=True)['ok']);self.assertTrue(self.host.call(self.command,self.root,self.output)['hit'])
  command=self.command.copy();command.insert(1,'-DUNUSED=1');self.assertFalse(self.host.call(command,self.root,self.output)['hit']);self.assertFalse(self.host.call(self.command,self.root,self.output,key='different-sdk')['hit'])
 def test_project_namespace_has_no_physical_fallback(self):
  header=self.root/'hidden.h';header.write_text('#define VALUE 9\n');body='#include "hidden.h"\nint f(void){return VALUE;}\n';self.source.write_text(body)
  ack=self.host.request(dict(source_root=str(self.root),edits={str(self.source):body},expected_generation=0));self.assertTrue(ack['ok']);self.assertFalse(self.host.call(self.command,self.root,self.output,logical=True,generation=1)['ok'])
  ack=self.host.request(dict(source_root=str(self.root),edits={str(header):'#define VALUE 3\n'},expected_generation=1));self.assertTrue(ack['ok']);self.assertTrue(self.host.call(self.command,self.root,self.output,logical=True,generation=2)['ok']);actual=self.output.read_bytes();header.write_text('#define VALUE 3\n');self.assertEqual(actual,self.oracle(body))
 def test_editor_generation_and_conflicts(self):
  body='int f(void){return 7;}\n';self.source.write_text('int f(void){return 1;}\n');ack=self.host.request(dict(source_root=str(self.root),edits={str(self.source):body},expected_generation=0));self.assertTrue(ack['ok']);self.assertEqual(self.host.request(dict(inspect=str(self.source)))['sha256'],sha(body.encode()));self.assertTrue(self.host.call(self.command,self.root,self.output,logical=True,generation=1)['ok']);actual=self.output.read_bytes();self.assertEqual(actual,self.oracle(body));self.assertFalse(self.host.call(self.command,self.root,self.output,logical=True,generation=0)['ok']);self.assertFalse(self.host.request(dict(source_root=str(self.root),edits={str(self.source):body},expected_generation=0))['ok'])
 def test_membership_updates_and_detached_analysis(self):
  header=self.root/'optional.h';base='#if __has_include("optional.h")\n#include "optional.h"\n#else\n#define V 1\n#endif\nint f(void){return V;}\n';self.source.write_text(base);self.host.request(dict(source_root=str(self.root),edits={str(self.source):base},expected_generation=0));first=self.host.call(self.command,self.root,self.output,logical=True,generation=1,analysis='serial');self.assertTrue(first['ok']);before=self.output.read_bytes();self.host.request(dict(source_root=str(self.root),edits={str(header):'#define V 2\n'},expected_generation=1));second=self.host.call(self.command,self.root,self.output,logical=True,generation=2,analysis='parallel');self.assertTrue(second['ok']);self.assertNotEqual(before,self.output.read_bytes());self.assertEqual(first['analysis_count'],second['analysis_count']);header.write_text('#define V 2\n');self.assertEqual(self.output.read_bytes(),self.oracle(base))

 def test_backend_failure_does_not_report_success_and_worker_recovers(self):
  self.source.write_text('int f(void){__asm__("gaia_invalid_instruction");return 1;}\n')
  bad=self.host.call(self.command,self.root,self.output,store=True);self.assertFalse(bad['ok']);self.assertGreater(bad['backend_diagnostics'],0)
  self.source.write_text('int f(void){return 1;}\n');good=self.host.call(self.command,self.root,self.output,store=True);self.assertTrue(good['ok']);self.assertFalse(good['hit']);self.assertTrue(self.host.call(self.command,self.root,self.output)['hit'])

 def test_timestamp_metadata_is_an_explicit_unsupported_boundary(self):
  body='const char *stamp=__TIMESTAMP__;\n';reference=self.oracle(body);self.host.request(dict(source_root=str(self.root),edits={str(self.source):body},expected_generation=0));self.assertTrue(self.host.call(self.command,self.root,self.output,logical=True,generation=1)['ok']);self.assertNotEqual(reference,self.output.read_bytes())
  guarded=self.command.copy();guarded.insert(1,'-Werror=date-time');self.assertFalse(self.host.call(guarded,self.root,self.output,logical=True,generation=1)['ok']);self.assertFalse(self.host.call(guarded,self.root,self.output)['ok'])

 def test_ir_hit_still_emits_current_dependency_file(self):
  a=self.root/'a.h';b=self.root/'b.h';a.write_text('#define V 1\n');b.write_text('#define V 1\n');dep=self.root/'current.d';command=self.command.copy();command[1:1]=['-MMD','-MF',str(dep)]
  self.source.write_text('#include "a.h"\nint f(void){return V;}\n');self.assertTrue(self.host.call(command,self.root,self.output,store=True)['ok']);self.assertIn('a.h',dep.read_text())
  self.source.write_text('#include "b.h"\nint f(void){return V;}\n');row=self.host.call(command,self.root,self.output);self.assertTrue(row['ok']);self.assertTrue(row['hit']);self.assertIn('b.h',dep.read_text());self.assertNotIn('a.h',dep.read_text())

if __name__=='__main__':unittest.main()

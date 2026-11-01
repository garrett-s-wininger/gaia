import os,subprocess,tempfile,unittest,sys,json,select
from unittest.mock import patch
from pathlib import Path
from refined_protocol import Host,admit,request,scan

@unittest.skipUnless(os.environ.get('GAIA_REFINED_HOST'),'set GAIA_REFINED_HOST')
class RefinementTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.host=Host(Path(os.environ['GAIA_REFINED_HOST']),self.root,True);self.addCleanup(self.host.close);self.body='int gaia_f(){return 1;}\n';self.g=admit(self.host,self.root,{'main.cc':self.body},0);self.cmd=[os.environ.get('GAIA_CLANG','/usr/lib/llvm22/bin/clang++'),'-std=c++14','-O2','-g','-Werror=date-time','-MMD','-MF','main.d','-MT','main.o','-c','main.cc','-o','main.o']
 def compile(self,cmd=None,context='configuration-0',callback=None):return request(self.host,self.root,cmd or self.cmd,'main',self.g,context,on_facts=callback)
 def lookup(self,cmd=None,context='configuration-0'):return scan(self.host,['main'],self.g,context,commands={'main':cmd or self.cmd},root=self.root)
 def edit(self,body):self.g=admit(self.host,self.root,{'main.cc':body},self.g)
 def test_fact_event_precedes_object_and_matches_final(self):
  events=[]
  def receive(facts):self.assertFalse((self.root/'main.o').exists());events.append(facts)
  row=self.compile(callback=receive);self.assertEqual(events,[row['facts']]);self.assertTrue((self.root/'main.o').exists())
 def test_cached_identities_survive_empty_and_identical_admission(self):
  row=self.compile();before=self.lookup()['facts'];self.g=admit(self.host,self.root,{},self.g);self.assertEqual(before,self.lookup()['facts']);self.g=admit(self.host,self.root,{'main.cc':self.body},self.g);self.assertEqual(before,self.lookup()['facts'])
 def test_unused_numeric_define_reuses_but_used_identifier_invalidates(self):
  a=self.cmd+['-DFEATURE=1'];b=self.cmd+['-DFEATURE=2'];self.compile(a);s=self.lookup(b,'configuration-1');self.assertEqual(s['dirty'],[]);self.assertEqual(s['projected'],['main'])
  self.edit('int gaia_f(){return FEATURE;}\n');self.compile(a);self.assertEqual(self.lookup(b,'configuration-1')['dirty'],['main'])
 def test_undefined_condition_alias_and_sdk_identifiers_invalidate(self):
  for body,extra in [('#if FEATURE\nint gaia_f(){return 2;}\n#else\nint gaia_f(){return 1;}\n#endif\n',[]),('#if ALIAS\nint gaia_f(){return 2;}\n#else\nint gaia_f(){return 1;}\n#endif\n',['-DALIAS=FEATURE'])]:
   self.edit(body);self.compile(self.cmd+extra);self.assertEqual(self.lookup(self.cmd+extra+['-DFEATURE=1'],'configuration-1')['dirty'],['main'])
  sdk_temp=tempfile.TemporaryDirectory();self.addCleanup(sdk_temp.cleanup);sdk=Path(sdk_temp.name)
  (sdk/'config.h').write_text('#if FEATURE\n#define VALUE 2\n#else\n#define VALUE 1\n#endif\n')
  self.edit('#include <config.h>\nint gaia_f(){return VALUE;}\n');a=self.cmd+['-I'+str(sdk)];self.compile(a);self.assertEqual(self.lookup(a+['-DFEATURE=1'],'configuration-1')['dirty'],['main'])
 def test_paste_and_metadata_options_fall_back(self):
  self.edit('#define JOIN(a,b) a##b\n#if JOIN(FEA,TURE)\nint gaia_f(){return 2;}\n#else\nint gaia_f(){return 1;}\n#endif\n');row=self.compile();self.assertGreater(row['paste_count'],0);self.assertEqual(self.lookup(self.cmd+['-DFEATURE=1'],'configuration-1')['dirty'],['main'])
  self.edit(self.body);a=self.cmd+['-frecord-command-line','-DFEATURE=1'];b=self.cmd+['-frecord-command-line','-DFEATURE=2'];self.compile(a);self.assertEqual(self.lookup(b,'configuration-1')['dirty'],['main'])
 def test_history_restores_object_depfile_and_facts(self):
  first=self.compile();obj=(self.root/'main.o').read_bytes();dep=(self.root/'main.d').read_bytes();self.edit('int gaia_other(){return 2;}\n');self.compile();self.edit(self.body);s=self.lookup();self.assertEqual(s['dirty'],[]);self.assertEqual(s['restored'],['main']);self.assertEqual((self.root/'main.o').read_bytes(),obj);self.assertEqual((self.root/'main.d').read_bytes(),dep);self.assertEqual(s['facts']['main'],first['facts'])
 def test_frontend_failure_has_no_event_backend_failure_does_not_claim_success(self):
  events=[];self.edit('int broken(;\n')
  with self.assertRaises(RuntimeError):self.compile(callback=events.append)
  self.assertEqual(events,[]);self.edit('int gaia_f(){__asm__("gaia_invalid_instruction");return 1;}\n')
  with self.assertRaises(RuntimeError):self.compile(callback=events.append)
  self.assertEqual(len(events),1);self.edit(self.body);self.assertTrue(self.compile()['ok'])
 def test_unrelated_paste_does_not_force_every_macro_to_invalidate(self):
  self.edit('#define JOIN(a,b) a##b\nint JOIN(he,lper)(){return 1;}\n')
  self.compile(self.cmd+['-DFEATURE=1']);self.assertEqual(self.lookup(self.cmd+['-DFEATURE=2'],'configuration-1')['dirty'],[])
 def test_duplicate_definitions_and_codegen_changes_keep_exact_context(self):
  a=self.cmd+['-DFEATURE=1','-DFEATURE=1'];row=self.compile(a);self.assertFalse(row['projection_supported']);self.assertEqual(self.lookup(self.cmd+['-DFEATURE=1','-DFEATURE=2'],'configuration-1')['dirty'],['main'])
  self.compile();self.assertEqual(self.lookup(['-O0' if x=='-O2' else x for x in self.cmd],'configuration-1')['dirty'],['main'])
 def test_old_result_eviction_causes_recompute(self):
  self.compile()
  for i in range(9):self.edit('int gaia_f(){return '+str(i+2)+';}\n');self.compile()
  self.edit(self.body);self.assertEqual(self.lookup()['dirty'],['main'])
 def test_explicit_cached_compile_restores_deleted_outputs(self):
  self.compile();obj=(self.root/'main.o').read_bytes();dep=(self.root/'main.d').read_bytes();(self.root/'main.o').unlink();(self.root/'main.d').unlink();self.compile();self.assertEqual((self.root/'main.o').read_bytes(),obj);self.assertEqual((self.root/'main.d').read_bytes(),dep)
 def test_partial_restore_failure_marks_output_unknown(self):
  self.compile();self.edit('int gaia_other(){return 2;}\n');self.compile();second=(self.root/'main.o').read_bytes();self.edit(self.body);(self.root/'main.d').unlink();(self.root/'main.d').mkdir()
  with self.assertRaises(RuntimeError):self.lookup()
  self.edit('int gaia_other(){return 2;}\n');(self.root/'main.d').rmdir();self.lookup();self.assertEqual((self.root/'main.o').read_bytes(),second);self.assertTrue((self.root/'main.d').is_file())
 def framed_child(self,wrong=False):
  script="import os,json,sys; request=json.loads(sys.stdin.readline()); event={'event':'frontend_facts','frontend_ok':True,'generation':"+('0' if wrong else "request['generation']")+",'target':'main','facts':{}}; os.write(1,(json.dumps(event)+'\\n'+json.dumps({'ok':True})+'\\n').encode()); sys.stdin.readline()"
  h=Host.__new__(Host);h.log=(self.root/'child.log').open('wb');h.process=subprocess.Popen([sys.executable,'-u','-c',script],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=h.log,text=True);h.refined=True;h.pending=bytearray();self.addCleanup(h.close);return h
 def test_combined_event_and_final_frame_drain_before_polling(self):
  h=self.framed_child();original=select.select;calls=[]
  def poll(*args):calls.append(1);self.assertEqual(len(calls),1,'polled despite complete pending frame');return original(*args)
  with patch('refined_protocol.select.select',side_effect=poll):self.assertTrue(h.request({'target':'main','generation':1})['ok'])
 def test_bad_event_is_drained_before_error(self):
  h=self.framed_child(True)
  with self.assertRaises(ValueError):h.request({'target':'main','generation':1})
  self.assertEqual(h.pending,bytearray())
 def test_compiler_predefined_names_are_not_treated_as_unused_user_macros(self):
  base=['-std=gnu++14' if x=='-std=c++14' else x for x in self.cmd];a=base+['-Dlinux=1'];b=base+['-Dlinux=2'];row=self.compile(a);self.assertEqual(row['warnings'],0);self.assertEqual(self.lookup(b,'configuration-1')['dirty'],['main']);changed=self.compile(b,'configuration-1');self.assertGreater(changed['warnings'],0)
 def test_stale_request_rejected_before_event(self):
  args=list(self.cmd);args[args.index('-o')+1]=str(self.root/'main.o');events=[];r=self.host.request(dict(args=args,cwd=str(self.root),output=str(self.root/'main.o'),target='main',generation=self.g-1,context='fixed',mode='observed',analysis='off',emit_facts=True,logical=True),on_facts=events.append);self.assertFalse(r['ok']);self.assertEqual(events,[])

if __name__=='__main__':unittest.main()

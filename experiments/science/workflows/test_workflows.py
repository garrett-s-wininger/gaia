import importlib,tempfile,threading,unittest
from unittest.mock import patch
from pathlib import Path
import workspaces
from doctest_worker import execute,pin

class WorkspaceTests(unittest.TestCase):
    def test_private_overlay_and_stale_publication(self):
        base={'a.py':b'def parse_base():\n return 1\n'};cache={};a=workspaces.Workspace(base,cache);b=workspaces.Workspace(base,cache)
        generation,view=a.capture();self.assertTrue(a.edit('a.py',b'def gaia_edit():\n return 2\n',0))
        self.assertEqual(b.items['a.py'][0],base['a.py']);self.assertFalse(a.publish(generation,workspaces.query(view)));self.assertFalse(a.edit('a.py',base['a.py'],0))
    def test_hardlinked_namespace_is_copy_on_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'base';base.mkdir();(base/'a.py').write_bytes(b'x=1\n')
            workspace=workspaces.Workspace({'a.py':b'x=1\n'},{},root/'actor',base)
            self.assertTrue(workspace.edit('a.py',b'x=2\n',0));self.assertEqual((base/'a.py').read_bytes(),b'x=1\n')
    def test_syntax_errors_are_current_observations(self):
        names,error=workspaces.facts(b'def broken(:\n','a.py');self.assertEqual(names,());self.assertEqual(error['line'],1)
    def test_deferred_analysis_retains_old_bytes(self):
        workspace=workspaces.Workspace({'a.py':b'x=1\n'},{})
        self.assertTrue(workspace.edit('a.py',b'x=2\n',0,observe=False));generation,view=workspace.capture();self.assertIsNone(view['a.py'][1])
        self.assertTrue(workspace.edit('a.py',b'x=3\n',1,observe=False));self.assertEqual(view['a.py'][0],b'x=2\n');self.assertFalse(workspace.publish(generation,None))
    def test_concurrent_expected_generation_has_one_winner(self):
        workspace=workspaces.Workspace({'a.py':b'x=1\n'},{});barrier=threading.Barrier(3);results=[]
        def edit(value):barrier.wait();results.append(workspace.edit('a.py',value,0,observe=False))
        threads=[threading.Thread(target=edit,args=(body,)) for body in [b'x=2\n',b'x=3\n']]
        for thread in threads:thread.start()
        barrier.wait()
        for thread in threads:thread.join()
        self.assertEqual(sorted(results),[False,True]);self.assertEqual(workspace.generation,1)
    def test_new_edit_invalidates_published_current_view(self):
        workspace=workspaces.Workspace({'a.py':b'x=1\n'},{});self.assertTrue(workspace.publish(0,{'result':1}));self.assertIsNotNone(workspace.last_publication)
        self.assertTrue(workspace.edit('a.py',b'x=2\n',0));self.assertIsNone(workspace.last_publication);self.assertFalse(workspace.publish(0,{'result':1}))

class RealDoctestTests(unittest.TestCase):
    def test_actual_upstream_examples_repeat_with_fresh_globs(self):
        module=importlib.import_module('difflib');request=dict(module='difflib',source_sha256=pin(module),token='one');cache={}
        self.assertEqual(execute(request,cache)['attempted'],75);self.assertEqual(execute(request,cache)['failed'],0)
    def test_reject_stale_pin_and_recover_after_failure(self):
        self.assertFalse(execute(dict(module='difflib',source_sha256='0'*64,token='bad'),{})['ok'])
        self.assertEqual(execute(dict(module='invalid'),{})['failed'],1)
        module=importlib.import_module('fractions');self.assertTrue(execute(dict(module='fractions',source_sha256=pin(module),token='good'),{})['ok'])
    def test_new_source_pin_cannot_bless_already_loaded_old_module(self):
        module=importlib.import_module('difflib');loaded=pin(module);cache={'difflib':(module,loaded)}
        with patch('doctest_worker.pin',return_value='f'*64):
            result=execute(dict(module='difflib',source_sha256='f'*64,token='changed'),cache)
        self.assertFalse(result['ok']);self.assertIn('generation',result['error'])

if __name__=='__main__':unittest.main()

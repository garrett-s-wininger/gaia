import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import benchmark

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.work=Path(self.temp.name)
        self.config=self.work/'config.json'
        self.config.write_text(json.dumps(dict(adapter_root=str(benchmark.HERE),fixture_parent=str(self.work))))
        self.runner=benchmark.HERE/'runner.py'
    def tearDown(self):self.temp.cleanup()
    def call(self,token):
        return dict(cwd=str(self.work),argv=['probe',token],environment={'GAIA_REQUEST_TOKEN':token},token=token)
    def test_children_isolate_globals_environment_argv_random_and_normal_finalizers(self):
        template=benchmark.Template(self.runner,'minimal',self.config,'probe_workload')
        try:
            replies=[]
            for token in ('alpha','beta'):
                call=self.call(token);marker=self.work/(token+'.marker');call['marker']=str(marker)
                reply=template.call(call);replies.append(reply)
                self.assertTrue(reply['ok']);self.assertEqual(reply['wait_status'],0)
                self.assertEqual(reply['result'],dict(state=[token],cwd=str(self.work),argv=['probe',token],token=token))
                self.assertEqual(marker.read_text(),'normal-finalization')
            self.assertNotEqual(replies[0]['pid'],replies[1]['pid']);self.assertNotEqual(replies[0]['nonce'],replies[1]['nonce'])
        finally:template.close()
    def test_failed_child_does_not_poison_template(self):
        template=benchmark.Template(self.runner,'minimal',self.config,'probe_workload')
        try:
            call=self.call('broken');call['fail']=True;reply=template.call(call)
            self.assertFalse(reply['ok']);self.assertEqual(reply['wait_status'],1)
            reply=template.call(self.call('recovered'));self.assertTrue(reply['ok']);self.assertEqual(reply['result']['state'],['recovered'])
        finally:template.close()
    def test_preloaded_environment_and_cwd_identity_rejected(self):
        config=json.loads(self.config.read_text());config.update(protected_environment={'PIN':'fixed'},template_cwd=str(self.work));self.config.write_text(json.dumps(config))
        template=benchmark.Template(self.runner,'minimal',self.config,'probe_workload')
        try:
            call=self.call('wrong');reply=template.call(call);self.assertFalse(reply['ok']);self.assertIn('environment differs',reply['error'])
            call['environment']['PIN']='fixed';call['cwd']='/tmp';reply=template.call(call);self.assertFalse(reply['ok']);self.assertIn('cwd differs',reply['error'])
            call['cwd']=str(self.work);reply=template.call(call);self.assertTrue(reply['ok'])
        finally:template.close()
    def test_open_resource_and_thread_templates_rejected(self):
        config=json.loads(self.config.read_text());config['resource']=str(self.config);self.config.write_text(json.dumps(config))
        for stage in ('resource','thread'):
            with self.subTest(stage=stage):
                result=subprocess.run(benchmark.command(self.runner,'server',stage,self.config,'probe_workload'),input='',capture_output=True,text=True,timeout=10)
                self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,'')
                self.assertIn('unapproved open resources' if stage=='resource' else 'exactly one OS thread',result.stderr)
    def test_unknown_request_and_oversize_rejected(self):
        template=benchmark.Template(self.runner,'minimal',self.config,'probe_workload')
        try:
            call=self.call('unknown');call['mystery']=True
            self.assertFalse(template.call(call)['ok'])
        finally:template.close()
        result=subprocess.run(benchmark.command(self.runner,'once','minimal',self.config,'probe_workload'),input='x'*65538,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0);self.assertIn('request too large',result.stderr)

if __name__=='__main__':unittest.main()

"""Resident decisions preserve fresh-process semantics with bounded lifetimes."""
import struct
import subprocess
import unittest

from resident_host import ResidentHost
import test_condition_index as original


class ResidentDecisionTests(original.SelectiveTests):
    def setUp(self):
        super().setUp();self.worker=ResidentHost(original.native_tests.DECISION,completion_metadata=True)
        self.addCleanup(lambda:self.worker.close())

    def call(self,mode='selective-check',stamp=None,request=None):
        argv=[original.native_tests.DECISION,mode,str(self.receipt),request or self.request,str(self.tools),str(self.outputs),str(self.namespace),str(self.conditions)]
        if stamp is not None:argv.append(stamp)
        return self.worker.request(argv)

    def test_repeated_requests_reset_arena_and_restart_is_independent(self):
        self.publish()
        for _ in range(100):self.assertTrue(self.call()['hit'])
        self.assertLess(max(self.worker.arena_used),64*1048576)
        self.assertEqual(len(set(self.worker.arena_used[-50:])),1)
        self.worker.close();self.worker=ResidentHost(original.native_tests.DECISION,completion_metadata=True)
        self.assertTrue(self.call()['hit'])

    def test_bad_frames_fail_before_unbounded_allocation(self):
        for body in (struct.pack('<Q',4*1048576+1),struct.pack('<QI',4,65),struct.pack('<QII',8,2,65537)):
            result=subprocess.run([original.native_tests.DECISION,'--serve'],input=body,capture_output=True,timeout=5)
            self.assertNotEqual(result.returncode,0)


if __name__=='__main__':unittest.main()

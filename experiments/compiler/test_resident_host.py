"""Same cache/compiler contract over repeated, serial framed requests."""
import os
import shutil
import unittest

import test_build_decisions as previous
from resident_host import ResidentHost


class ResidentHistoryTests(previous.HistoricalCandidateTests):
    def setUp(self):
        super().setUp();self.worker=ResidentHost(previous.HISTORY,os.environ.copy())
        self.addCleanup(lambda:self.worker.close())

    def request(self,value,extra=(),mode='journal-history',body=None,files=None):
        if mode=='journal-history':mode='journal-history-memo'
        return super().request(value,extra,mode,body,files)

    def consume(self,cmd,value):
        result=self.worker.request(cmd)
        library=(self.output/'libanswer.so').read_bytes()
        # Existing helper independently compiles/links via CLI and runs the lib.
        fresh=super().consume(cmd,value)
        self.assertEqual(result['object_sha256'],fresh['object_sha256'])
        self.assertEqual(result['journal_sha256'],fresh['journal_sha256'])
        self.assertEqual(library,(self.output/'libanswer.so').read_bytes())
        return result

    def test_failed_request_ends_worker_and_fresh_worker_recovers(self):
        cmd=self.request(1);self.consume(cmd,1)
        bad=cmd.copy();bad[5]='0'*64
        with self.assertRaises(RuntimeError):self.worker.request(bad)
        self.worker.close();self.assertNotEqual(self.worker.process.returncode,0)
        self.worker=ResidentHost(previous.HISTORY,os.environ.copy());self.consume(cmd,1)

    def test_output_directory_can_be_recreated_between_requests(self):
        self.consume(self.request(1),1)
        shutil.rmtree(self.output);self.output.mkdir()
        self.consume(self.request(2),2)

    def test_repeated_requests_do_not_retain_large_input_collections(self):
        peaks=[]
        for i in range(24):
            cmd=self.request(i%3+1,files={str(self.root/'unread'):b'x'*1048576})
            result=self.worker.request(cmd);self.assertTrue(result['correct']);peaks.append(result['peak_rss_bytes'])
        # A broad regression guard, not a production hard memory quota.
        self.assertLess(max(peaks[8:])-max(peaks[:8]),16*1048576)


if __name__=='__main__':unittest.main()

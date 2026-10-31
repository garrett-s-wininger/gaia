"""Explicit BLAKE3 roots/query journals with SHA-256 output verification."""
import os
from pathlib import Path
import subprocess
import unittest

from blake3_digest import Blake3
import inline_snapshot
import test_resident_host as previous


@unittest.skipUnless(os.environ.get('GAIA_BLAKE3_HELPER'),'Set GAIA_BLAKE3_HELPER with a BLAKE3-capable host')
class Blake3ProviderTests(previous.ResidentHistoryTests):
    def setUp(self):
        super().setUp();self.blake3=Blake3(os.environ['GAIA_BLAKE3_HELPER'])

    def request(self,value,extra=(),mode='journal-history',body=None,files=None):
        if mode=='journal-history':mode='journal-history-blake3'
        cmd=super().request(value,extra,mode,body,files)
        if mode=='journal-history-blake3':
            inputs={str(self.source):self.source.read_bytes(),**(files or {})}
            result=inline_snapshot.publish(inputs,{name:1 for name in inputs},1,Path(cmd[4]),self.views,blake3=self.blake3)
            cmd[5]=result['pin']
        return cmd

    def test_known_empty_digest(self):
        # Official unkeyed BLAKE3 test vector (256-bit output).
        self.assertEqual(self.blake3(b'').hex(),'af1349b9f5f9a1a6a0404dea36dcc9499bcb25c9adc112b7cc9a93cae41f3262')

    def test_algorithm_versions_isolate_roots_actions_and_journals(self):
        first=self.consume(self.request(3),3)
        self.assertEqual(next(self.cache.glob('*.gdo')).read_bytes()[88:96],b'GAIAJR02')
        sha=self.consume(self.request(3,mode='journal-history-memo'),3)
        self.assertNotEqual(first['cache_keys'],sha['cache_keys'])
        self.assertNotEqual(first['journal_sha256'],sha['journal_sha256'])
        self.assertEqual(first['object_sha256'],sha['object_sha256'])
        again=self.consume(self.request(3),3)
        self.assertEqual(again['compiler_executions'],0)
        self.assertEqual(first['cache_keys'],again['cache_keys']);self.assertEqual(first['journal_sha256'],again['journal_sha256'])

    def test_missing_tag_and_wrong_wire_version_are_rejected(self):
        cmd=self.request(1);self.assertTrue(cmd[5].startswith('blake3:'))
        bad=cmd.copy();bad[5]=bad[5][7:]
        result=subprocess.run(bad,cwd=self.output,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        raw=Path(cmd[4]).read_bytes();self.assertEqual(raw[:8],b'GAIACIN3')
        Path(cmd[4]).write_bytes(b'GAIACIN2'+raw[8:])
        result=subprocess.run(cmd,cwd=self.output,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)


if __name__=='__main__':unittest.main()

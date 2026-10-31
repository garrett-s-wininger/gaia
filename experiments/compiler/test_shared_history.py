"""Real compilation/replay over sealed bases and explicit input overlays."""
import json
import os
from pathlib import Path
import subprocess
import unittest

from shared_inputs import Session
import test_blake3_provider as previous

@unittest.skipUnless(os.environ.get('GAIA_SHARED_INPUTS')=='1','set GAIA_SHARED_INPUTS=1 with the CIN4 host')
class SharedHistoryTests(previous.Blake3ProviderTests):
    def setUp(self):
        super().setUp();self.session=Session(self.blake3)

    def request(self,value,extra=(),mode='journal-history',body=None,files=None):
        cmd=super().request(value,extra,mode,body,files)
        if cmd[13]=='journal-history-blake3':
            inputs={str(self.source):self.source.read_bytes(),**(files or {})}
            published=self.session.publish(inputs,{n:1 for n in inputs},1,Path(cmd[4]),self.views)
            cmd[5]=published['pin']
        return cmd

    def test_missing_tag_and_wrong_wire_version_are_rejected(self):
        cmd=self.request(1);raw=Path(cmd[4]).read_bytes();self.assertEqual(raw[:8],b'GAIACIN4')
        bad=cmd.copy();bad[5]=bad[5][7:]
        self.assertNotEqual(subprocess.run(bad,cwd=self.output,capture_output=True).returncode,0)
        Path(cmd[4]).write_bytes(b'GAIACIN3'+raw[8:])
        self.assertNotEqual(subprocess.run(cmd,cwd=self.output,capture_output=True).returncode,0)

    def test_reset_prime_and_receiver_overlay_accounting(self):
        extra={str(self.root/'unused'):b'unchanged'}
        cmd=self.request(1,files=extra);first=self.consume(cmd,1)
        self.assertEqual(first['shared_new_segments'],1)
        control=self.worker.request([cmd[0],'shared-reset','']);self.assertTrue(control['correct'])
        control=self.worker.request([cmd[0],'shared-prime',cmd[4],cmd[5],self.session.keep_pins()]);self.assertTrue(control['correct'])
        repeat=self.worker.request(cmd);self.assertTrue(repeat['correct']);self.assertEqual(repeat['shared_new_segments'],0)
        self.assertEqual(repeat['shared_cached_file_digests'],2)
        changed=self.consume(self.request(2,files=extra),2)
        self.assertEqual(changed['shared_new_segments'],1);self.assertEqual(changed['shared_segment_hits'],1)
        self.assertEqual(changed['shared_cached_file_digests'],1)

    def test_hidden_optional_file_and_later_visibility(self):
        body='#if __has_include("optional.h")\n#include "optional.h"\n#else\n#define ANSWER 1\n#endif\nint answer(void){return ANSWER;}\n'
        self.consume(self.request(1,body=body),1)
        optional=self.root/'optional.h';payload=b'#define ANSWER 2\n'
        cmd=self.request(1,body=body,files={str(optional):payload})
        names=sorted(self.session.state.files);self.views.write_text('GAIACV1\n'+''.join('0\n' if n==str(optional) else '1\n' for n in names))
        optional.unlink();hidden=self.consume(cmd,1);self.assertEqual(hidden['compiler_executions'],0)
        optional.write_bytes(payload);self.views.write_text('GAIACV1\n'+'1\n'*len(names))
        visible=self.consume(cmd,2);self.assertEqual(visible['compiler_executions'],1)

if __name__=='__main__':unittest.main()

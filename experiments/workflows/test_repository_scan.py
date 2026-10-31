import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from benchmark import PATTERNS


@unittest.skipUnless(os.environ.get('GAIA_SCAN_HOST'), 'set GAIA_SCAN_HOST to native executable')
class ScanTests(unittest.TestCase):
    def test_empty_and_binary_and_boundary_matches(self):
        with tempfile.TemporaryDirectory(prefix='gaia-scan-test-') as temp:
            root=Path(temp)
            contents=[b'',b'Copyright\x00MIT LicenseTODOFIXME',b'SPDX-License-Identifier password password',b'TODO\nTODO',b'TO',b'DO']
            paths=[]
            for n,value in enumerate(contents):
                path=root/f'file{n}';path.write_bytes(value);paths.append(path)
            manifest=root/'manifest';manifest.write_text(''.join(str(p)+'\n' for p in paths))
            oracle=[sum(value.count(pattern.encode()) for value in contents) for pattern in PATTERNS]
            for mode in ('single','shared','fused'):
                for index in range(6) if mode=='single' else (0,):
                    result=subprocess.run([os.environ['GAIA_SCAN_HOST'],str(manifest),mode,str(index)],capture_output=True,check=True)
                    parsed=json.loads(result.stdout)
                    expected=oracle if mode!='single' else [n if k==index else 0 for k,n in enumerate(oracle)]
                    self.assertEqual(parsed['counts'],expected)
                    self.assertEqual(parsed['bytes'],sum(map(len,contents)))

    def test_missing_file_is_failure(self):
        with tempfile.TemporaryDirectory(prefix='gaia-scan-test-') as temp:
            manifest=Path(temp)/'manifest';manifest.write_text(str(Path(temp)/'missing')+'\n')
            result=subprocess.run([os.environ['GAIA_SCAN_HOST'],str(manifest),'fused','0'],capture_output=True)
            self.assertEqual(result.returncode,3)


if __name__=='__main__':unittest.main()

from pathlib import Path
import tempfile
import os
import unittest

from pe_info import inspect
HERE=Path(__file__).resolve().parent
RUN=Path(os.environ.get('GAIA_DOTNET_TEST_RUN',HERE/'_work/main')).resolve()
PREPARED=Path(os.environ.get('GAIA_DOTNET_TEST_PREPARED',HERE/'_work/prepared')).resolve()

class PEGuardTests(unittest.TestCase):
    def test_non_pe_and_truncated_headers_rejected(self):
        for body in (b'',b'not PE',b'MZ',b'MZ'+bytes(100)):
            with tempfile.NamedTemporaryFile() as stream:
                stream.write(body);stream.flush()
                with self.assertRaises(ValueError):inspect(stream.name)
    @unittest.skipUnless((RUN/'work/project/Application.dll').exists(),'run local compiler experiment first')
    def test_shipping_and_composite_r2r_vs_emitted_il(self):
        root=PREPARED
        self.assertTrue(inspect(root/'stock/Microsoft.CodeAnalysis.CSharp.dll')['ready_to_run'])
        self.assertTrue(inspect(root/'composite/Microsoft.CodeAnalysis.CSharp.dll')['ready_to_run'])
        self.assertFalse(inspect(RUN/'work/project/Application.dll')['ready_to_run'])

if __name__=='__main__':unittest.main()

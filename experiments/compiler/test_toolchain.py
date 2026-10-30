"""Configuration and admitted-tool checks independent of an installed compiler."""
import argparse
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark


class ToolchainTests(unittest.TestCase):
    def test_explicit_paths_override_environment(self):
        with patch.dict(os.environ, {'GAIA_LLVM': '/env/llvm', 'GAIA_LLVM_HEADERS': '/env/headers'}, clear=True):
            parser=argparse.ArgumentParser()
            benchmark.toolchain_arguments(parser)
            defaults=parser.parse_args([])
            self.assertEqual(defaults.llvm, Path('/env/llvm'))
            args=parser.parse_args(['--llvm', '/tools with spaces/llvm', '--llvm-headers', '/headers'])
            self.assertEqual(args.llvm, Path('/tools with spaces/llvm'))
            self.assertEqual(args.llvm_headers, Path('/headers'))

    def test_missing_configuration_requires_explicit_selection(self):
        with patch.dict(os.environ, {}, clear=True):
            parser=argparse.ArgumentParser()
            benchmark.toolchain_arguments(parser)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                parser.parse_args([])
            args=parser.parse_args(['--llvm', '/llvm', '--llvm-headers', '/headers'])
            self.assertEqual(args.llvm, Path('/llvm'))

    def test_prefix_header_default_and_odin_override(self):
        with patch.dict(os.environ, {'GAIA_LLVM': '/llvm', 'ODIN': '/tools/odin'}, clear=True):
            parser=argparse.ArgumentParser()
            benchmark.toolchain_arguments(parser)
            self.assertEqual(parser.parse_args([]).llvm_headers, Path('/llvm/include'))
            with patch.object(benchmark.shutil, 'which', return_value='/tools/odin') as which:
                self.assertEqual(benchmark.odin_executable(), '/tools/odin')
                which.assert_called_once_with('/tools/odin')
            with patch.object(benchmark.shutil, 'which', return_value=None), self.assertRaisesRegex(RuntimeError, 'ODIN'):
                benchmark.odin_executable()

    def test_admitted_tool_survives_arbitrary_location_but_rejects_changes(self):
        with tempfile.TemporaryDirectory(prefix='gaia toolchain ') as name:
            clang=Path(name)/'clang';clang.write_bytes(b'compiler identity')
            info={'toolchain_sha256': {str(clang): benchmark.sha(clang)}}
            self.assertEqual(benchmark.admitted_tool(info, 'clang'), clang)
            clang.write_bytes(b'changed compiler')
            with self.assertRaisesRegex(ValueError, 'regenerate'):
                benchmark.admitted_tool(info, 'clang')
            clang.unlink()
            with self.assertRaises(ValueError):benchmark.admitted_tool(info, 'clang')


if __name__=='__main__':unittest.main()

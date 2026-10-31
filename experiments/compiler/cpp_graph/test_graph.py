import tempfile
from pathlib import Path
import unittest
import graph


class GraphTests(unittest.TestCase):
    def test_capture_path_and_ninja_escaping(self):
        self.assertEqual(graph.ninja_path('a b:c$d'),'a$ b$:c$$d')
        self.assertIn('$$ORIGIN',graph.ninja_command(['ld','-rpath','$ORIGIN']))
    def test_watch_checks_content_and_inode_not_only_mtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input';path.write_bytes(b'old');watch=graph.Watch([str(path)],retain=[str(path)]);self.assertEqual(watch.refresh([str(path)])['reads'],0)
            old=path.stat();path.write_bytes(b'new')
            import os
            os.utime(path,ns=(old.st_atime_ns,old.st_mtime_ns))
            self.assertEqual(watch.refresh([str(path)])['changed'],[str(path)]);self.assertEqual(watch.records[str(path)]['body'],b'new')
    def test_library_resolution_preserves_order_and_closes_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'libsample.so';path.write_bytes(b'linker input')
            self.assertEqual(graph.resolve_libraries(['ld','-L'+tmp,'-lsample']),['ld','-L'+tmp,str(path)])
            with self.assertRaises(ValueError):graph.resolve_libraries(['ld','-L'+tmp,'-lmissing'])

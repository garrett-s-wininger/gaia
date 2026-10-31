"""Native persistence boundary checks; no claim of full workspace recovery."""
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest


def bundle(entries):
    result = bytearray(struct.pack('<Q', len(entries)))
    for name, (contents, executable) in sorted(entries.items()):
        name = name.encode()
        result.extend(struct.pack('<Q', len(name)) + name + bytes([executable]) + struct.pack('<Q', len(contents)) + contents)
    return bytes(result)


@unittest.skipUnless(os.environ.get('GAIA_CHECKPOINT_HOST'), 'set GAIA_CHECKPOINT_HOST to native executable')
class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='gaia-checkpoint-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name);self.store = self.root/'store';self.store.mkdir()
        self.input = self.root/'input.bundle';self.host = os.environ['GAIA_CHECKPOINT_HOST']

    def capture(self, entries, expected='empty', failpoint='none', code=0):
        self.input.write_bytes(bundle(entries))
        result = subprocess.run([self.host, 'capture', str(self.store), str(self.input), expected, failpoint], capture_output=True)
        self.assertEqual(result.returncode, code, result.stderr)
        return result.stdout.decode().strip()

    def read(self, snapshot, name, code=0):
        result = subprocess.run([self.host, 'read', str(self.store), snapshot, name], capture_output=True)
        self.assertEqual(result.returncode, code, result.stderr)
        return result.stdout

    def test_historical_read_dedup_and_metadata_identity(self):
        entries={'a.txt':(b'first\x00bytes',0),'nested/b':(b'other',1)}
        first=self.capture(entries);count=len(list(self.store.iterdir()))
        again=self.capture(entries,first)
        self.assertEqual(first,again);self.assertEqual(count,len(list(self.store.iterdir())))
        entries['a.txt']=(b'second',0);second=self.capture(entries,first)
        self.assertNotEqual(first,second);self.assertEqual(self.read(first,'a.txt'),b'first\x00bytes')
        self.assertEqual(self.read(second,'a.txt'),b'second')
        entries['a.txt']=(b'second',1);third=self.capture(entries,second)
        self.assertNotEqual(second,third)

    def test_interruption_before_and_after_publication(self):
        first=self.capture({'a':(b'old',0)})
        self.capture({'a':(b'new',0)},first,'before-root',75)
        self.assertEqual((self.store/'HEAD').read_text(),first)
        self.assertEqual(self.read(first,'a'),b'old')
        self.assertTrue((self.store/'writer-intent').exists())
        # Explicit private-fixture recovery: retain old HEAD and orphan objects,
        # remove the dead writer intent. Not a production automatic-recovery API.
        (self.store/'writer-intent').unlink()
        self.capture({'a':(b'new',0)},first,'after-root',76)
        second=(self.store/'HEAD').read_text()
        self.assertEqual(self.read(second,'a'),b'new')
        self.assertEqual(self.read(first,'a'),b'old')

    def test_expected_generation_and_writer_busy(self):
        first=self.capture({'a':(b'old',0)})
        self.capture({'a':(b'new',0)},'0'*64,code=3)
        self.assertEqual((self.store/'HEAD').read_text(),first)
        # Failed exclusive-writer capture leaves intent for explicit recovery.
        (self.store/'writer-intent').unlink()
        (self.store/'writer-intent').write_text('another writer')
        self.capture({'a':(b'new',0)},first,code=3)
        self.assertEqual((self.store/'HEAD').read_text(),first)

    def test_corruption_and_missing_content(self):
        first=self.capture({'a':(b'old',0)})
        content_id=hashlib.sha256(b'content\x00old').hexdigest()
        (self.store/content_id).write_bytes(b'corrupt')
        self.read(first,'a',3)
        self.capture({'a':(b'old',0)},first,code=3)
        (self.store/content_id).unlink();self.read(first,'a',3)

    def test_invalid_names_and_truncated_bundle(self):
        self.capture({'../outside':(b'bad',0)},code=3)
        self.assertFalse((self.store/'HEAD').exists())
        (self.store/'writer-intent').unlink()
        self.input.write_bytes(b'\xff'*7)
        result=subprocess.run([self.host,'capture',str(self.store),str(self.input),'empty','none'],capture_output=True)
        self.assertEqual(result.returncode,3)
        self.assertFalse((self.store/'HEAD').exists())

    def test_head_read_error_does_not_mean_empty(self):
        (self.store/'HEAD').mkdir()
        self.capture({'a':(b'new',0)},code=3)
        self.assertTrue((self.store/'HEAD').is_dir())
        self.assertEqual({p.name for p in self.store.iterdir()},{'HEAD','writer-intent'})


if __name__=='__main__':unittest.main()

"""Sealed segments preserve admitted bytes through edit/delete/compaction."""
import fcntl
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
import shared_inputs as s

# Producer protocol tests do not require the optional native BLAKE3 library;
# the fake digest below never goes to the real consumer.
class SharedInputTests(unittest.TestCase):
    def test_seals_overlay_delete_restore_and_compaction(self):
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'inputs';views=Path(folder)/'views';session=s.Session(lambda b:hashlib.sha256(b).digest())
            files={'/a':b'abc','/b':b'def'};masks={'/a':1,'/b':1}
            first=session.publish(files,masks,1,out,views);seed=session.snapshot();segment=seed.segments[0]
            self.assertTrue(first['compacted']);self.assertEqual(fcntl.fcntl(segment.owner.fileno(),fcntl.F_GET_SEALS)&s.SEALS,s.SEALS)
            with self.assertRaises(OSError):os.write(segment.owner.fileno(),b'X')
            readwrite=os.open(segment.path,os.O_RDWR)
            try:
                with self.assertRaises(OSError):os.pwrite(readwrite,b'X',0)
                with self.assertRaises(OSError):os.ftruncate(readwrite,0)
            finally:os.close(readwrite)
            current={'/a':b'new'};stats=session.publish(current,{'/a':1},1,out,views)
            self.assertEqual(stats['changed_files'],1);self.assertEqual(session.state.deleted,frozenset({'/b'}));self.assertEqual(len(session.state.segments),2)
            session.restore(seed);self.assertEqual(session.publish(files,masks,1,out,views)['created_segment_bytes'],0)
            for value in (b'new',b'abc',b'new',b'abc'):
                session.publish({'/a':value,'/b':b'def'},masks,1,out,views)
                self.assertEqual(len({x.digest for x in session.state.segments}),len(session.state.segments))
            for i in range(10):session.publish({'/a':str(i).encode()},{'/a':1},1,out,views)
            self.assertLessEqual(len(session.state.segments),8);self.assertEqual(seed.files,files)
    def test_bad_input_does_not_advance_state_and_mutable_bytes_copied(self):
        with tempfile.TemporaryDirectory() as folder:
            session=s.Session(lambda b:hashlib.sha256(b).digest());out=Path(folder)/'inputs';views=Path(folder)/'views';body=bytearray(b'a')
            session.publish({'/a':body},{'/a':1},1,out,views);old=session.snapshot();body[0]=98
            self.assertEqual(old.files['/a'],b'a')
            with self.assertRaises(ValueError):session.publish({'/../a':b'a'},{'/../a':1},1,out,views)
            self.assertIs(session.snapshot(),old)
            self.assertEqual(s.manifest(old)[:8],b'GAIACIN4')

if __name__=='__main__':unittest.main()

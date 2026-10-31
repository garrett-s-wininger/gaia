import fcntl
import os
import unittest
from shared_inputs import Broker,encode,decode,compile_rows


class SharedInputTests(unittest.TestCase):
    def test_budget_dedup_and_active_lease(self):
        broker=Broker(10)
        try:
            pin=broker.admit(b'12345');self.assertEqual(broker.admit(b'12345'),pin);self.assertEqual(broker.bytes,5)
            fd=broker.lease(pin)
            with self.assertRaises(BlockingIOError):broker.evict(pin)
            with self.assertRaises(MemoryError):broker.admit(b'123456')
            with self.assertRaises(OSError):os.write(fd,b'change')
            broker.release(pin,fd);broker.evict(pin);self.assertEqual(broker.bytes,0)
        finally:broker.close()

    def test_format_and_real_compilation(self):
        body=encode({'one.py':b'x=1\n','two.py':b'y=2\n'});rows,base=decode(body)
        self.assertEqual(compile_rows(body,rows,base,[0,1]),compile_rows(body,rows,base,[0,1]))
        with self.assertRaises(ValueError):decode(body[:10])
        with self.assertRaises(ValueError):compile_rows(body,rows,base,[9])

    def test_close_fails_with_active_lease(self):
        broker=Broker(10);pin=broker.admit(b'abc');fd=broker.lease(pin)
        with self.assertRaises(BlockingIOError):broker.close()
        broker.release(pin,fd);broker.close()

    def test_mismatched_and_duplicate_release_preserve_accounting(self):
        broker=Broker(10);left=broker.admit(b'abc');right=broker.admit(b'def')
        first=broker.lease(left);second=broker.lease(right)
        try:
            with self.assertRaises(ValueError):broker.release(left,second)
            self.assertEqual(os.pread(second,3,0),b'def')
            self.assertEqual(broker.entries[left].leases,1)
            self.assertEqual(broker.entries[right].leases,1)
            with self.assertRaises(BlockingIOError):broker.evict(left)
            broker.release(left,first)
            with self.assertRaises(ValueError):broker.release(left,first)
            broker.release(right,second);broker.evict(left);broker.evict(right)
            self.assertEqual(broker.bytes,0);self.assertFalse(broker.leases)
        finally:
            for fd,pin in list(broker.leases.items()):broker.release(pin,fd)
            broker.close()


if __name__=='__main__':unittest.main()

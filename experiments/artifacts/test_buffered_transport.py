import io
import unittest
from unittest import mock

import binary_transport as b
import test_binary_transport as baseline
import transfer as t


def local_server(*args,**kwargs):return b.local_server(*args,buffered=True,**kwargs)


class BufferedContracts(baseline.BinaryHTTPContracts):
    def setUp(self):
        super().setUp();patcher=mock.patch.object(t,'local_server',local_server);patcher.start();self.addCleanup(patcher.stop)
    def run_fetch(self,url,mode,cache,wanted=None):
        url=url.replace('http://','gaia-binary-buffered://').replace('gaia-binary://','gaia-binary-buffered://')
        return super().run_fetch(url,mode,cache,wanted)


class BufferedNetworkErrors(baseline.BinaryNetworkTests):
    def setUp(self):
        super().setUp();patcher=mock.patch.object(b,'local_server',local_server_original);patcher.start();self.addCleanup(patcher.stop)


# Preserve the original function so a patched test helper cannot recurse.
original_server=b.local_server
def local_server_original(*args,**kwargs):return original_server(*args,buffered=True,**kwargs)


class BufferTests(unittest.TestCase):
    def test_vectored_send_handles_partial_writes_and_zero_progress(self):
        class Partial:
            def __init__(self):self.data=bytearray();self.calls=0
            def sendmsg(self,buffers):
                self.calls+=1;body=b''.join(buffers);count=min(len(body),3);self.data.extend(body[:count]);return count
        sock=Partial();b.send_buffers(sock,[b'ab',b'',b'cdefg']);self.assertEqual(sock.data,b'abcdefg');self.assertEqual(sock.calls,3)
        with mock.patch.object(sock,'sendmsg',return_value=0):
            with self.assertRaises(OSError):b.send_buffers(sock,[b'x'])

    def test_vectored_fallback_preserves_bytes(self):
        class Fallback:
            def __init__(self):self.data=bytearray()
            def sendall(self,body):self.data.extend(body)
        sock=Fallback();b.send_buffers(sock,[b'ab',b'cd']);self.assertEqual(sock.data,b'abcd')

    def test_owned_read_results_survive_next_read_and_short_body_fails(self):
        class Fake:
            def makefile(self,*args,**kwargs):return io.BytesIO(b'abcd')
            def close(self):pass
        client=b.Buffered('gaia-binary-buffered://127.0.0.1:1');sock=Fake()
        first=client.receive(sock,2);second=client.receive(sock,2)
        self.assertIsInstance(first,bytes);self.assertEqual((first,second),(b'ab',b'cd'))
        with self.assertRaises(t.TransferError):client.receive(sock,1)
        client.close()


if __name__=='__main__':unittest.main()

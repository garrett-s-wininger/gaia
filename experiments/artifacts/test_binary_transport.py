import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest
from unittest import mock
from urllib.parse import urlsplit

import batch
import binary_transport as b
import test_transfer as old
import transfer as t


class CodecTests(unittest.TestCase):
    def test_independent_header_vector_and_short_reads(self):
        self.assertEqual(b.request_header(b'\x01'+bytes(32),b.BLOB,1),
            bytes.fromhex('474146310102000000000000000000010000000000000021'))
        class Short:
            def __init__(self,data):self.data=data
            def recv_into(self,view):
                if not self.data:return 0
                view[0]=self.data[0];self.data=self.data[1:];return 1
        self.assertEqual(b.receive(Short(b'abcd'),4),b'abcd')
        with self.assertRaises(t.TransferError):b.receive(Short(b'ab'),4)
        self.assertIsNone(b.receive(Short(b''),4,True))

    def test_oversized_reply_rejected_before_body_allocation(self):
        class Fake:
            reads=0
            def sendall(self,body):pass
            def close(self):pass
            def recv_into(self,view):
                self.reads+=1
                if self.reads>1:raise AssertionError('body read after oversized header')
                data=b.HEADER.pack(b.MAGIC,b.VERSION,b.BLOB,b.RESPONSE,1,b.MAX_FRAME+1)
                view[:len(data)]=data;return len(data)
        client=b.Binary('gaia-binary://127.0.0.1:1');fake=Fake();client.connections[threading.get_ident()]=[fake,1]
        with self.assertRaises(t.TransferError):client.exchange(b.BLOB,b'\x01'+bytes(32),16)
        self.assertEqual(fake.reads,1)

    def test_batch_identity_bounds_and_version(self):
        c=t.build_collection([b'a',b'bbb']);objects=t.parse_manifest(c['manifest'])['objects'];keys=[o['sha256'] for o in objects]
        request=batch.request(keys);self.assertEqual(batch.parse_request(request),keys)
        body=batch.response(keys,t.resources(c));items=batch.parse_response(body,objects)
        self.assertEqual([bytes(payload) for _,payload in items],[c['objects'][key] for key in keys])
        for bad in [request[:-1],request+b'x',request[:8]+b'\x02'+request[9:],
                    batch.HEADER.pack(batch.REQUEST_MAGIC,1,0,0,t.MAX_OBJECTS+1),
                    batch.HEADER.pack(batch.REQUEST_MAGIC,1,0,0,2)+bytes.fromhex(keys[0])*2]:
            with self.assertRaises(t.TransferError):batch.parse_request(bad)
        wrong=bytearray(body);wrong[batch.HEADER.size]^=1
        for bad in [body[:-1],body+b'x',bytes(wrong),body[:8]+b'\x02'+body[9:]]:
            with self.assertRaises(t.TransferError):batch.parse_response(bad,objects)


class BinaryHTTPContracts(old.HTTPTests):
    def setUp(self):
        super().setUp();patcher=mock.patch.object(t,'local_server',b.local_server);patcher.start();self.addCleanup(patcher.stop)
    def run_fetch(self,url,mode,cache,wanted=None):
        return super().run_fetch(url.replace('http://','gaia-binary://'),mode,cache,wanted)


class BinaryNetworkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='gaia binary $ ');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.collection=t.build_collection([b'a'*31,b'b'*47,b'c'*59])
    def fetch(self,url,mode,cache):
        return t.fetch(url,self.collection['manifest_id'],len(self.collection['manifest']),list(self.collection['objects']),cache,mode)

    def test_malformed_request_frames_close_without_unbounded_body_reads(self):
        key=bytes.fromhex(next(iter(self.collection['objects'])))
        requests=[b.HEADER.pack(b'BAD!',1,b.BLOB,0,1,33)+b'\x01'+key,
                  b.HEADER.pack(b.MAGIC,2,b.BLOB,0,1,33)+b'\x01'+key,
                  b.HEADER.pack(b.MAGIC,1,99,0,1,0),
                  b.HEADER.pack(b.MAGIC,1,b.BLOB,1,1,33)+b'\x01'+key,
                  b.HEADER.pack(b.MAGIC,1,b.BLOB,0,1,b.MAX_REQUEST+1),
                  b.HEADER.pack(b.MAGIC,1,b.BLOB,0,1,33)+b'\x02'+key,
                  b.HEADER.pack(b.MAGIC,1,b.BATCH,0,1,batch.HEADER.size)+batch.HEADER.pack(batch.REQUEST_MAGIC,1,0,0,t.MAX_OBJECTS+1),
                  b.HEADER.pack(b.MAGIC,1,b.BLOB,0,1,33)+b'\x01']
        with b.local_server(self.collection) as url:
            address=urlsplit(url)
            for request in requests:
                with socket.create_connection((address.hostname,address.port),timeout=2) as sock:
                    sock.sendall(request);sock.shutdown(socket.SHUT_WR)
                    try:self.assertEqual(sock.recv(1),b'')
                    except ConnectionResetError:pass

    def test_duplicate_request_id_is_rejected(self):
        key=bytes.fromhex(next(iter(self.collection['objects'])));body=b'\x01'+key;request=b.request_header(body,b.BLOB,1)+body
        with b.local_server(self.collection) as url:
            address=urlsplit(url)
            with socket.create_connection((address.hostname,address.port),timeout=2) as sock:
                sock.sendall(request);header=b.HEADER.unpack(b.receive(sock,b.HEADER.size));b.receive(sock,header[-1])
                sock.sendall(request)
                try:self.assertEqual(sock.recv(1),b'')
                except ConnectionResetError:pass

    def test_wrong_response_identity_version_opcode_length_and_truncation(self):
        path='/blobs/sha256/'+self.collection['pack_id']
        for fault in ['wrong-request-id','wrong-version','wrong-opcode','huge-length','truncated-header']:
            with self.subTest(fault=fault):
                cache=self.root/fault
                with b.local_server(self.collection,faults={path:fault}) as url:
                    with self.assertRaises(t.TransferError):self.fetch(url,'pack-coalesced',cache)
                self.assertFalse((cache/'ready.json').exists())

    def test_shared_batch_bytes_and_failure_contract_over_both_transports(self):
        for label,server in [('http',t.local_server),('binary',b.local_server)]:
            with server(self.collection) as url:
                cache=self.root/label;t.control(url,'reset');result=self.fetch(url,'selected-batch',cache);counts=t.control(url,'metrics')
                self.assertEqual(result['requests'],2);self.assertEqual(result['transfer_bytes'],len(self.collection['pack']))
                self.assertEqual(result['overfetch_bytes'],0)
                self.assertEqual(result['batch_framing_bytes'],batch.HEADER.size+40*len(self.collection['objects']))
                self.assertEqual(result['response_payload_bytes'],counts['response_payload_bytes'])
                self.assertEqual(result['batch_framing_bytes'],counts['batch_framing_bytes'])
                for key,body in self.collection['objects'].items():self.assertEqual((cache/'objects'/'sha256'/key).read_bytes(),body)
            for fault in ['corrupt','truncated']:
                cache=self.root/(label+'-'+fault)
                with server(self.collection,faults={'/batch/sha256':fault}) as url:
                    with self.assertRaises(t.TransferError):self.fetch(url,'selected-batch',cache)
                self.assertFalse((cache/'ready.json').exists())


if __name__=='__main__':unittest.main()

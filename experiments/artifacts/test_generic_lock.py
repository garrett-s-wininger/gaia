import json
import struct
import tempfile
from pathlib import Path
import unittest

import generic_lock as g
import transfer as t
import pipeline_transport as transport


class GenericLockTests(unittest.TestCase):
    def doc(self):
        payload=b'content';return dict(version=1,packages=[dict(ecosystem='example',name='a',version='opaque:beta+target')],artifacts=[dict(algorithm='sha256',digest=t.digest(payload),size=len(payload))],associations=[dict(package=0,artifact=0,role='variant',label='linux/a'),dict(package=0,artifact=0,role='variant',label='bsd/a')],metadata=[dict(ecosystem='example',role='opaque-graph',artifact=0)])
    def test_views_equivalent_and_multiple_associations_opaque_versions(self):
        doc=self.doc();a=g.encode_json(doc);b=g.encode_binary(doc);j=g.JSONView(a,t.digest(a));v=g.BinaryView(b,t.digest(b))
        self.assertEqual(j.counts,v.counts);self.assertEqual(v.package(0),('example','a','opaque:beta+target'))
        for name,count in (('artifact',1),('association',2),('metadata',1)):
            for i in range(count):self.assertEqual(getattr(j,name)(i),getattr(v,name)(i))
        self.assertFalse(hasattr(v,'document'));self.assertEqual(v.contents[0]['sha256'],doc['artifacts'][0]['digest'])
        empty=dict(version=1,packages=[],artifacts=[],associations=[],metadata=[]);body=g.encode_binary(empty);self.assertEqual(g.BinaryView(body,t.digest(body)).counts,(0,0,0,0))
    def test_hash_version_truncation_counts_offsets_algorithms_and_utf8(self):
        body=g.encode_binary(self.doc());view=g.BinaryView(body,t.digest(body))
        with self.assertRaises(t.TransferError):g.BinaryView(body,'0'*64)
        variants=[body[:12]]
        altered=bytearray(body);struct.pack_into('!I',altered,8,2);variants.append(altered)
        altered=bytearray(body);struct.pack_into('!I',altered,16,g.MAX_STRINGS+1);variants.append(altered)
        altered=bytearray(body);g.STRING.pack_into(altered,g.HEADER.size,0xffffffff,8);variants.append(altered)
        altered=bytearray(body);struct.pack_into('!H',altered,view.starts[2],99);variants.append(altered)
        altered=bytearray(body);struct.pack_into('!I',altered,view.starts[2]+4,0xffffffff);variants.append(altered)
        altered=bytearray(body);altered[view.pool]=255;variants.append(altered)
        altered=bytearray(body);struct.pack_into('!I',altered,view.starts[3]+4,99);variants.append(altered)
        for bad in variants:
            with self.subTest(size=len(bad)):
                with self.assertRaises(t.TransferError):g.BinaryView(bytes(bad),t.digest(bad))
    def test_json_rejects_unknown_alg_duplicate_identity_and_unbounded_reference(self):
        for mutate in (lambda d:d['artifacts'][0].update(algorithm='unknown'),lambda d:d['packages'].append(d['packages'][0]),lambda d:d['associations'][0].update(artifact=999),lambda d:d.update(version=True)):
            doc=self.doc();mutate(doc);body=t.encode(doc)
            with self.assertRaises(t.TransferError):g.JSONView(body,t.digest(body))
    def test_acquisition_both_formats_matches_counts_and_offline(self):
        collection=t.build_collection([b'content'])
        with tempfile.TemporaryDirectory() as tmp,transport.local_server(collection) as url:
            for kind,encoder in (('json',g.encode_json),('binary',g.encode_binary)):
                body=encoder(self.doc());root=Path(tmp)/kind
                view,result=g.acquire(url,body,t.digest(body),root,kind)
                self.assertEqual((result['requests'],result['manifest_requests'],result['transfer_bytes']),(1,0,7))
                self.assertEqual(g.acquire('gaia-mux://127.0.0.1:1',body,t.digest(body),root,kind)[1]['requests'],0)
    def test_mutable_input_is_frozen_before_lazy_access(self):
        original=g.encode_binary(self.doc());mutable=bytearray(original);view=g.BinaryView(mutable,t.digest(mutable))
        before=view.artifact(0);mutable[:]=b'\xff'*len(mutable)
        self.assertIsInstance(view.body,bytes);self.assertEqual(view.artifact(0),before);self.assertEqual(view.package(0),('example','a','opaque:beta+target'))
        immutable=g.BinaryView(original,t.digest(original));self.assertIs(immutable.body,original)
    def test_public_binary_record_and_string_bounds(self):
        body=g.encode_binary(self.doc());view=g.BinaryView(body,t.digest(body))
        for name,count in (('package',1),('artifact',1),('association',2),('metadata',1)):
            for index in (-1,count):
                with self.subTest(method=name,index=index):
                    with self.assertRaises(IndexError):getattr(view,name)(index)
        for index in (-1,view.ns):
            with self.assertRaises(t.TransferError):view.string(index)

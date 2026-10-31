from pathlib import Path
import hashlib,itertools,json,struct,tempfile,unittest
import adapter,delivery,locality,reconcile

class ReconciliationTests(unittest.TestCase):
    def test_exhaustive_tiny_sets(self):
        sets=[set(x) for n in range(5) for x in itertools.combinations(range(4),n)]
        for a in sets:
            for b in sets:
                for method in ('full','merkle','iblt'):
                    result=reconcile.one(a,b,method,max(1,len(a^b)))
                    self.assertEqual(result['difference'],len(a^b))
    def test_underestimate_fallback_exact(self):
        result=reconcile.one(set(range(100)),set(range(100,200)),'iblt',1)
        self.assertTrue(result['fallback']);self.assertEqual(result['difference'],200)
    def test_table_shape_and_incremental_inverse(self):
        table=reconcile.Table(11);table.update(12,1);table.update(12,-1)
        self.assertEqual(table.decode(),(set(),set()))
        with self.assertRaises(ValueError):table.subtract(reconcile.Table(12))

class DeliveryTests(unittest.TestCase):
    def test_framing_and_integrity(self):
        objects={hashlib.sha256(b'value').hexdigest():b'value'};ids=list(objects)
        self.assertEqual(delivery.parse_request(delivery.request_bytes(ids)),ids)
        body=delivery.encode_response(ids,objects);self.assertEqual(dict(delivery.parse_response(body,ids)),objects)
        for bad in [body[:-1],body+b'x',body[:-1]+b'X']:
            with self.assertRaises(ValueError):delivery.parse_response(bad,ids)
    def test_malformed_request_bounds(self):
        for bad in [b'',struct.pack('!I',0),struct.pack('!I',65),struct.pack('!I',1)+b'x'*31]:
            with self.assertRaises(ValueError):delivery.parse_request(bad)
    def test_impossible_batch_rejected_before_network(self):
        key=hashlib.sha256(b'content').hexdigest()
        with self.assertRaisesRegex(ValueError,'budget'):
            delivery.acquire('binary',('127.0.0.1',0),[key],{key:b'content'},1,1,budget=1)

class LocalityTests(unittest.TestCase):
    def test_training_order_is_complete(self):
        self.assertEqual(sorted(locality.cluster(8,[[0,2,3],[2,4,9]])),list(range(8)))
        self.assertEqual(locality.reinforced([0,1,2,0],3),locality.reinforced([0,1,2,0],3))
    def test_pack_equivalence_and_corruption(self):
        payload=b'A'*65536+b'B'*65536+b'C'*5;meta=[{'size':len(payload[i:i+65536]),'sha256':hashlib.sha256(payload[i:i+65536]).hexdigest()} for i in range(0,len(payload),65536)]
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'pack';locations,_,_=locality.build_layout(payload,[2,0,1],2,p)
            result=locality.evaluate(p,locations,meta,[0,2,1,0],2*65536)
            self.assertLessEqual(result['peak_cache_bytes'],2*65536)
            p.write_bytes(b'bad')
            with self.assertRaises(ValueError):locality.evaluate(p,locations,meta,[0],2*65536)

class AdapterTests(unittest.TestCase):
    def fixture(self):return adapter.fixture({'name':'package/a.pyc','size':7,'offset':4,'sha256':'a'*64},5)
    def test_opaque_and_presence_roundtrip(self):
        body=self.fixture();self.assertEqual(adapter.lossless_json(body)[0],body)
        lossy=adapter.lossy_json(body);self.assertNotEqual(lossy,body);self.assertEqual(adapter.project(adapter.decode(lossy)),adapter.project(adapter.decode(body)))
    def test_bounds_unknown_required_and_duplicates(self):
        body=self.fixture()
        for bad in (body[:8],body[:-1],body+b'bad'):
            with self.assertRaises(ValueError):adapter.decode(bad)
        fields=adapter.decode(body)
        for tag in (2,3,4):
            invalid=tuple((t,b'x') if t==tag else (t,v) for t,v in fields)
            with self.assertRaises(ValueError):adapter.encode(invalid)
        with self.assertRaises(ValueError):adapter.encode((*fields,(6,b'future')))
        with self.assertRaises(ValueError):adapter.encode((*fields,fields[0]))
    def test_default_presence_is_not_erased(self):
        fields=tuple((tag,value) for tag,value in adapter.decode(self.fixture()) if tag!=5)
        variants=[adapter.encode(fields),adapter.encode((*fields,(5,b'\0default'))),adapter.encode((*fields,(5,b'\1default')))]
        self.assertEqual(len(set(variants)),3)
        self.assertEqual(len({json.dumps(adapter.project(adapter.decode(body)),sort_keys=True) for body in variants}),1)
        for body in variants:self.assertEqual(adapter.lossless_json(body)[0],body)

if __name__=='__main__':unittest.main()

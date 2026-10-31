"""Correctness boundaries for admission and borrowed catalogue consumers."""
from pathlib import Path
import json,os,struct,tempfile,unittest,hashlib,subprocess
import admission,catalogue
from admission import ChunkStore,digest
from service import ModelIO,Profile

class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.body=bytes(range(256))*40;self.path=self.root/'payload';self.path.write_bytes(self.body);self.hashes=[digest(self.body[i:i+1024]) for i in range(0,len(self.body),1024)]
    def tearDown(self):self.temp.cleanup()
    def store(self,budget=2048):return ChunkStore(self.path,1024,budget,ModelIO(self.root,Profile('nominal')),self.hashes)
    def test_cross_chunk_and_zero_reads(self):
        store=self.store()
        try:self.assertEqual(store.read(900,1500),self.body[900:2400]);self.assertEqual(store.read(len(self.body),0),b'');self.assertLessEqual(store.bytes,2048)
        finally:store.close()
    def test_lru_budget_and_reload(self):
        store=self.store(1024)
        try:
            for offset in (0,2048,0):self.assertEqual(store.read(offset,512),self.body[offset:offset+512])
            self.assertEqual(store.evictions,2);self.assertEqual(store.model.read_bytes,3072);self.assertEqual(store.peak,1024)
        finally:store.close()
    def test_zero_retention_and_bad_bounds(self):
        store=self.store(0)
        try:
            store.read(0,512);store.read(0,512);self.assertEqual(store.bytes,0);self.assertEqual(store.misses,2)
            for off,size in [(-1,1),(0,-1),(len(self.body),1)]:
                with self.assertRaises(ValueError):store.read(off,size)
        finally:store.close()
    def test_corrupt_chunk_not_published(self):
        store=self.store();self.path.write_bytes(b'!' + self.body[1:])
        try:
            with self.assertRaisesRegex(ValueError,'digest'):store.read(0,10)
            self.assertEqual(store.bytes,0)
        finally:store.close()
    def test_full_is_one_charged_read(self):
        store=self.store(len(self.body))
        try:
            store.admit_all();self.assertEqual(store.model.read_calls,1);self.assertEqual(store.model.read_bytes,len(self.body));self.assertEqual(store.read(8000,1000),self.body[8000:9000]);self.assertEqual(store.model.read_calls,1)
        finally:store.close()
    def test_wrong_chunk_geometry(self):
        with self.assertRaises(ValueError):ChunkStore(self.path,1024,2048,ModelIO(self.root,Profile('nominal')),[])

class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.rows=[dict(name='django/a.pyc',offset=0,size=12,sha256='a'*64),dict(name='other/a.py',offset=12,size=3,sha256='b'*64)];self.body=catalogue.encode(self.rows)
        library=os.environ.get('GAIA_CATALOGUE_LIBRARY');self.native=catalogue.Native(Path(library)) if library else None
    def test_equivalent_queries(self):
        expected=catalogue.query_objects(self.rows);self.assertEqual(catalogue.query_direct(self.body),expected);self.assertEqual(catalogue.objects(self.body),self.rows)
        if self.native:self.assertEqual(self.native.query(self.body),expected)
    def test_truncated_and_bad_geometry(self):
        cases=[self.body[:10],self.body[:-1],b'BADMAGIC'+self.body[8:]]
        bad_utf=bytearray(self.body);bad_utf[24+2*56]=255;cases.append(bytes(bad_utf))
        overflow=bytearray(self.body);struct.pack_into('<Q',overflow,24+8,(1<<64)-1);cases.append(bytes(overflow))
        broken=bytearray(self.body);struct.pack_into('<I',broken,24+16,999999);cases.append(bytes(broken))
        for body in cases:
            with self.assertRaises(ValueError):catalogue.query_direct(body)
            if self.native:
                with self.assertRaises(ValueError):self.native.query(body)
            with tempfile.NamedTemporaryFile() as temp:
                temp.write(body);temp.flush()
                child=subprocess.run(['node',str(Path(__file__).parent/'catalogue_node.js'),temp.name,'direct','1',hashlib.sha256(body).hexdigest()],capture_output=True)
                self.assertNotEqual(child.returncode,0)
    def test_results_do_not_borrow_source_lifetime(self):
        if not self.native:self.skipTest('GAIA_CATALOGUE_LIBRARY not provided')
        result=self.native.query(bytes(bytearray(self.body)));self.body=None;self.assertEqual(result,[2,15,1,12,1,12])

if __name__=='__main__':unittest.main()

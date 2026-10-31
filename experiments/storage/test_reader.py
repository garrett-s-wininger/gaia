import mmap
import os
from pathlib import Path
import sys
import tempfile
import unittest

from service import ModelIO,Profile,Sealed,checked_digest
from reader import Reader,validate_index
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'artifacts'))
from preindexed_bundle_benchmark import produce
import locked_python


class ReaderTests(unittest.TestCase):
    def fixture(self,root):
        source=root/'input';(source/'pkg').mkdir(parents=True);(source/'pkg/__init__.py').write_bytes(b'VALUE=1\n');(source/'pkg/data.txt').write_bytes(b'resource\n')
        body,payloads=locked_python.make_lock(source,dict(versions={'pkg':'opaque'},resources={}))
        artifacts=produce(root/'producer',body,payloads,'flat');cache=root/'cache';cache.mkdir();(cache/'index').write_bytes(artifacts['index']);(cache/'payload').write_bytes(artifacts['payload'])
        return dict(mode='range',root=str(cache),scope=str(root),index=artifacts['index_descriptor'],payload=artifacts['payload_descriptor'],index_path=str(cache/'index'),payload_path=str(cache/'payload'))
    def test_range_never_maps_private_file_data_and_audits_every_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=self.fixture(root);model=ModelIO(root,Profile('nominal'));mapped=[];active=[True]
            def audit(event,args):
                if event=='mmap.__new__' and active[0]:mapped.append(os.readlink('/proc/self/fd/'+str(args[0])))
            sys.addaudithook(audit)
            try:
                reader=Reader(job,model);self.assertEqual(reader.read('pkg/data.txt'),b'resource\n')
                with self.assertRaises(TypeError):reader.mapping[0]=0
                reader.close()
            finally:active[0]=False
            self.assertEqual(model.read_calls,2);self.assertEqual(model.read_bytes,job['index']['size']+9)
            self.assertTrue(mapped);self.assertTrue(all('/memfd:' in path for path in mapped),mapped)
    def test_memory_import_is_charged_then_readonly_consumption_has_no_storage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=self.fixture(root);model=ModelIO(root,Profile('nominal'));snapshots=[]
            try:
                for kind in ('index','payload'):
                    body=model.read(job[kind+'_path'],job[kind]['size']);checked_digest(body,job[kind]);snapshots.append(Sealed(body))
                job.update(mode='memory',index_fd=snapshots[0].fd,payload_fd=snapshots[1].fd);child_model=ModelIO(root,Profile('nominal'));reader=Reader(job,child_model)
                self.assertEqual(reader.read('pkg/data.txt'),b'resource\n')
                with self.assertRaises(TypeError):reader.data[0][1][0]=0
                reader.close();self.assertEqual(child_model.read_calls,0);self.assertEqual(model.read_calls,2)
                self.assertEqual(os.pread(snapshots[1].fd,8,0),b'GAPK0001')
            finally:
                for snapshot in snapshots:snapshot.close()
    def test_bad_index_or_requested_bytes_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=self.fixture(root);body=Path(job['index_path']).read_bytes();validate_index(body,job['payload']);reader=Reader(job,ModelIO(root,Profile('nominal')))
            payload=Path(job['payload_path']);changed=bytearray(payload.read_bytes());changed[-1]^=1;payload.write_bytes(changed)
            with self.assertRaises(ValueError):
                for name in reader.entries:reader.read(name)
            reader.close()
            with self.assertRaises(ValueError):validate_index(body[:20],job['payload'])
    def test_memory_provider_rejects_ordinary_file_mappings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);job=self.fixture(root);index=os.open(job['index_path'],os.O_RDONLY);payload=os.open(job['payload_path'],os.O_RDONLY)
            try:
                job.update(mode='memory',index_fd=index,payload_fd=payload)
                with self.assertRaises((OSError,ValueError)):Reader(job,ModelIO(root,Profile('nominal')))
            finally:os.close(index);os.close(payload)

import os
import gc
import importlib.util
import marshal
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

import benchmark
import binary_index
from bundle_access import BundlePath
from native_benchmark import compile_extension
from native_loader import NativeBundleReader
from precomputed_index import build_index

ODIN = shutil.which(os.environ.get("ODIN", "odin")) or os.environ.get("ODIN", "odin")


@unittest.skipUnless(sys.platform == "linux" and Path(ODIN).is_file() and shutil.which("cc"), "Linux Odin/C toolchain unavailable")
class ExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory()
        cls.library, _ = compile_extension(Path(cls.build.name), ODIN)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def fixture(self, root):
        archive, index = root/"data.zip", root/"data.index"
        values = {"pkg/__init__.py": b"", "pkg/data": bytes(range(256))*32, "root": b"root", "π/β": b"unicode"}
        with zipfile.ZipFile(archive, "w") as bundle:
            for name, value in values.items():
                bundle.writestr(name, value)
        built = build_index(archive, index, encoding="binary")
        return archive, index, values, built

    def open(self, archive, index, pin, policy="local"):
        return NativeBundleReader(archive, index, index_sha256=pin, library=self.library, verify=policy)

    def test_bytes_resources_and_explicit_close_ownership(self):
        with tempfile.TemporaryDirectory() as temp:
            archive, index, values, built = self.fixture(Path(temp))
            for policy in ("hash", "local"):
                reader = self.open(archive,index,built["index_sha256"],policy)
                for name, value in values.items():
                    self.assertEqual(reader.read(name), value)
                self.assertEqual(BundlePath(reader,"pkg").joinpath("data").read_bytes(), values["pkg/data"])
                with self.assertRaises(KeyError):
                    reader.read("missing")
                with self.assertRaises(IndexError):
                    reader._ffi.read(reader._handle,len(values))
                retained = reader.read("pkg/data")
                reader.close(); reader.close()
                self.assertEqual(retained,values["pkg/data"])
                with self.assertRaises(ValueError):
                    reader.read("root")
                with self.assertRaises(ValueError):
                    reader._ffi.catalog(reader._handle)

    def test_failed_opens_and_capsule_cleanup_release_mappings(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,_,built = self.fixture(Path(temp))
            reader=self.open(archive,index,built["index_sha256"])
            reader.close()
            original=index.read_bytes()
            baseline=len(list(Path("/proc/self/fd").iterdir()))
            for _ in range(30):
                with self.assertRaises(ValueError):
                    self.open(archive,index,"0"*64)
                reader=self.open(archive,index,built["index_sha256"])
                self.assertEqual(len(list(Path("/proc/self/fd").iterdir())),baseline+2)
                del reader
                gc.collect()
            self.assertEqual(len(list(Path("/proc/self/fd").iterdir())),baseline)
            # A well-pinned but malformed file must raise, not exit the interpreter.
            import hashlib
            for change in ("truncated", "version", "flags", "pool", "range", "directory", "utf8"):
                encoded=bytearray(original)
                header=list(binary_index.HEADER.unpack_from(encoded))
                row=list(binary_index.ENTRY.unpack_from(encoded,binary_index.HEADER.size))
                if change in ("version","flags","pool"):
                    header[{"version":1,"flags":2,"pool":-1}[change]]+=1
                    binary_index.HEADER.pack_into(encoded,0,*header)
                elif change in ("range","directory"):
                    row[0 if change=="range" else 3]=archive.stat().st_size+1
                    binary_index.ENTRY.pack_into(encoded,binary_index.HEADER.size,*row)
                elif change=="utf8":
                    encoded[-1]=0xff
                else:
                    encoded=encoded[:80]
                index.write_bytes(encoded)
                with self.subTest(change=change):
                    with self.assertRaises(ValueError):
                        self.open(archive,index,hashlib.sha256(encoded).hexdigest())
                    self.assertEqual(len(list(Path("/proc/self/fd").iterdir())),baseline)

    def test_live_payload_crc_failure_is_python_exception(self):
        with tempfile.TemporaryDirectory() as temp:
            archive,index,_,built=self.fixture(Path(temp))
            reader=self.open(archive,index,built["index_sha256"])
            row=next(row for row in binary_index.decode(index.read_bytes())["entries"] if row[0]=="pkg/data")
            # Deliberately violate immutability to reach the retained per-read check.
            with archive.open("r+b") as stream:
                stream.seek(row[1]);stream.write(b"\xff")
            try:
                with self.assertRaisesRegex(zipfile.BadZipFile,"CRC"):
                    reader.read("pkg/data")
            finally:
                reader.close()

    def test_bytecode_handoffs_validate_and_own_code_after_close(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'code.zip';index=root/'code.index'
            code=compile('VALUE="retained-string"\ndef answer():\n    return VALUE, b"retained-bytes"\n','gaia-test:///code.py','exec')
            header=importlib.util.MAGIC_NUMBER+(3).to_bytes(4,'little')+b'12345678'
            good=header+marshal.dumps(code)
            payloads={'good.pyc':good,'short.pyc':b'x','magic.pyc':b'xxxx'+good[4:],
                      'flags.pyc':good[:4]+(4).to_bytes(4,'little')+good[8:],
                      'body.pyc':header+b'?', 'object.pyc':header+marshal.dumps(42)}
            with zipfile.ZipFile(archive,'w') as bundle:
                for name,body in payloads.items():bundle.writestr(name,body)
            built=build_index(archive,index,encoding='binary')
            for mode in ('bytes','view','native'):
                with self.subTest(mode=mode):
                    reader=NativeBundleReader(archive,index,index_sha256=built['index_sha256'],library=self.library,
                                              verify='hash',bytecode_handoff=mode)
                    result=reader.load_code('good.pyc',source_hash=b'12345678')
                    self.assertEqual(result,code)
                    for name in payloads:
                        if name!='good.pyc':
                            with self.assertRaises(ImportError):reader.load_code(name)
                    with self.assertRaises(ImportError):reader.load_code('good.pyc',source_hash=b'87654321')
                    with self.assertRaises(KeyError):reader.load_code('missing.pyc')
                    row=next(r for r in binary_index.decode(index.read_bytes())['entries'] if r[0]=='good.pyc')
                    with archive.open('r+b') as stream:stream.seek(row[1]);stream.write(b'X')
                    with self.assertRaises(zipfile.BadZipFile):reader.load_code('good.pyc')
                    with archive.open('r+b') as stream:stream.seek(row[1]);stream.write(good[:1])
                    reader.close();gc.collect()
                    namespace={};exec(result,namespace)
                    self.assertEqual(namespace['answer'](),('retained-string',b'retained-bytes'))
                    with self.assertRaises(ValueError):reader.load_code('good.pyc')

    def test_bytecode_handoffs_preserve_audit_payload_and_rejection(self):
        state={'enabled':False,'reject':False};retained=[]
        def audit(event,args):
            if event=='marshal.loads' and state['enabled']:
                retained.append(args[0])
                if state['reject']:raise RuntimeError('audit rejected decode')
                if state.get('close'):state['close']()
        sys.addaudithook(audit)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'code.zip';index=root/'code.index'
            body=marshal.dumps(compile('VALUE=17','gaia-test:///audit.py','exec'))
            with zipfile.ZipFile(archive,'w') as bundle:
                bundle.writestr('code.pyc',importlib.util.MAGIC_NUMBER+b'\x00'*12+body)
            built=build_index(archive,index,encoding='binary')
            for mode in ('bytes','view','native'):
                reader=NativeBundleReader(archive,index,index_sha256=built['index_sha256'],library=self.library,
                                          verify='local',bytecode_handoff=mode)
                try:
                    state.update(enabled=True,reject=False)
                    reader.load_code('code.pyc')
                    state['reject']=True
                    with self.assertRaisesRegex(RuntimeError,'audit rejected'):reader.load_code('code.pyc')
                    state.update(reject=False,close=reader.close)
                    code=reader.load_code('code.pyc')
                    namespace={};exec(code,namespace);self.assertEqual(namespace['VALUE'],17)
                    with self.assertRaises(ValueError):reader.load_code('code.pyc')
                finally:
                    state.update(enabled=False,close=None);reader.close()
            self.assertEqual([bytes(v) for v in retained],[body]*9)

    def test_source_bytecode_relative_imports_resources_and_origins(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            source=root/"source"
            manifest=benchmark.make_fixture(source,16)
            manifest_path=root/"manifest.json"
            benchmark.write_json(manifest_path,manifest)
            bytecode=root/"bytecode"
            benchmark.precompile(source,bytecode)
            for mode,directory in (("source",source),("bytecode",bytecode)):
                archive,index=root/(mode+".zip"),root/(mode+".index")
                benchmark.pack(directory,archive,zipfile.ZIP_STORED)
                built=build_index(archive,index,encoding="binary")
                for policy in ("hash","local"):
                    command=benchmark.worker_command(manifest_path,archive,"access-mmap",mode)
                    command += ["--index",str(index),"--index-sha256",built["index_sha256"],
                                "--index-verification",policy,"--native-library",str(self.library)]
                    result=benchmark.consume(command)
                    self.assertTrue(result["correct"])
                    self.assertEqual(result["verified_modules"],40)
                    self.assertEqual(result["verified_resources"],32)
                    self.assertEqual(result["shared_archive_opens"],1)
                    self.assertEqual(result["persistent_module_reads"],40)
                    self.assertIsNotNone(result["native_timings"])


if __name__ == "__main__":
    unittest.main()

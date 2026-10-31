import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

import fetch_typescript
import node_dependency_benchmark

class CorpusTests(unittest.TestCase):
    def corpus(self,root,member='package/package.json',version='5.9.3'):
        archive=root/'typescript-5.9.3.tgz'
        body=json.dumps(dict(name='typescript',version=version)).encode()
        with tarfile.open(archive,'w:gz') as tf:
            item=tarfile.TarInfo(member);item.size=len(body);tf.addfile(item,io.BytesIO(body))
        raw=archive.read_bytes();provenance=dict(dist={'integrity':'sha512-'+base64.b64encode(hashlib.sha512(raw).digest()).decode()},
            tarball_sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        (root/'provenance.json').write_text(json.dumps(provenance));return raw,provenance
    def test_corrupt_download_and_sha256_identity_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            raw,p=self.corpus(Path(temp));fetch_typescript.admit(raw,p)
            with self.assertRaisesRegex(ValueError,'SHA-512'):fetch_typescript.admit(raw+b'x',p)
            p['tarball_sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'identity'):fetch_typescript.admit(raw,p)
    def test_bad_archive_and_wrong_package_version_rejected(self):
        for member,version,message in [('../outside','5.9.3','unsafe'),('package/package.json','0.0.0','wrong compiler')]:
            with self.subTest(member=member),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);self.corpus(root,member,version)
                with self.assertRaisesRegex(ValueError,message):node_dependency_benchmark.extract(root,root/'extracted')
                self.assertFalse((root.parent/'outside').exists())

if __name__=='__main__':unittest.main()

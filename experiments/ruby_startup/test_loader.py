import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
RUN=Path(os.environ.get('GAIA_RUBY_TEST_RUN',HERE/'_work/openssl-main')).resolve()
GEMS=Path(os.environ.get('GAIA_RUBY_GEM_HOME',HERE/'_work/gems')).resolve()
PACK=RUN/'work/code.pack'

@unittest.skipUnless(PACK.exists(),'generate the pinned local pack first')
class PackGuardTests(unittest.TestCase):
    def run_ruby(self,script,**changes):
        pin=json.loads((RUN/'results.json').read_text())['producer']['sha256']
        env=dict(os.environ,GEM_HOME=str(GEMS),GEM_PATH=str(GEMS),
          GAIA_RUBY_PACK=str(PACK),GAIA_RUBY_PACK_SHA256=pin,GAIA_RUBY_SHA256_PROVIDER='openssl')
        env.update(changes)
        return subprocess.run(['ruby','-e',script],env=env,capture_output=True,text=True,timeout=10)
    def test_wrong_checksum_and_runtime_options_rejected(self):
        loader=str(HERE/'packed_loader.rb')
        p=self.run_ruby('require '+json.dumps(loader),GAIA_RUBY_PACK_SHA256='0'*64)
        self.assertNotEqual(p.returncode,0);self.assertIn('pack checksum',p.stderr)
        p=self.run_ruby('RubyVM::InstructionSequence.compile_option={peephole_optimization:false};require '+json.dumps(loader))
        self.assertNotEqual(p.returncode,0);self.assertIn('runtime/options mismatch',p.stderr)
    def test_short_header_and_unknown_earlier_load_path_fall_back(self):
        loader=str(HERE/'packed_loader.rb')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);small=root/'bad.pack';small.write_bytes(b'x')
            p=self.run_ruby('require '+json.dumps(loader),GAIA_RUBY_PACK=str(small))
            self.assertNotEqual(p.returncode,0);self.assertIn('pack file size',p.stderr)
            (root/'gaia_probe.rb').write_text('GAIA_PROBE=42\n')
            script='require '+json.dumps(loader)+';$LOAD_PATH.unshift('+json.dumps(tmp)+');raise unless require("gaia_probe");raise unless GAIA_PROBE==42;raise if require("gaia_probe")'
            p=self.run_ruby(script);self.assertEqual(p.returncode,0,p.stderr)
    def test_sha256_provider_vectors_match(self):
        p=self.run_ruby('require "digest";require "openssl";["", "abc", "x"*1048576].each{|s|raise unless Digest::SHA256.hexdigest(s)==OpenSSL::Digest::SHA256.hexdigest(s)}')
        self.assertEqual(p.returncode,0,p.stderr)

if __name__=='__main__':unittest.main()

import json
import unittest
from semantic_cache import canonical_ast

class CanonicalTests(unittest.TestCase):
    def test_locations_and_process_ids_normalize_but_relations_remain(self):
        a={'id':'0x123','kind':'Decl','loc':{'line':1},'inner':[{'id':'0x456','previousDecl':'0x123'}]}
        b={'id':'0xaa','kind':'Decl','loc':{'line':9},'inner':[{'id':'0xbb','previousDecl':'0xaa'}]}
        self.assertEqual(canonical_ast(json.dumps(a).encode())[0],canonical_ast(json.dumps(b).encode())[0])
        b['inner'][0]['previousDecl']='0xbb'
        self.assertNotEqual(canonical_ast(json.dumps(a).encode())[0],canonical_ast(json.dumps(b).encode())[0])
    def test_values_flags_and_literal_hex_strings_are_not_erased(self):
        for key,left,right in [('value','0x123','0x456'),('isVolatile',True,False),('name','a','b')]:
            self.assertNotEqual(canonical_ast(json.dumps({key:left}).encode())[0],canonical_ast(json.dumps({key:right}).encode())[0])
    def test_bad_json_fails(self):
        with self.assertRaises(ValueError):canonical_ast(b'{')


# The native encoding is domain-separated tokens, not Python's JSON bytes.
# Verify its invariants and relation preservation, not a digest coincidence.
import os,subprocess,tempfile
from pathlib import Path
NATIVE=os.environ.get('GAIA_AST_HELPER')
@unittest.skipUnless(NATIVE,'set GAIA_AST_HELPER to compiled native helper')
class NativeCanonicalTests(unittest.TestCase):
    def fingerprint(self,value):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'ast.json';path.write_text(json.dumps(value))
            p=subprocess.run([NATIVE,str(path)],check=True,capture_output=True,text=True)
            return json.loads(p.stdout)
    def test_key_order_locations_and_address_renaming(self):
        a={'id':'0x123','kind':'Decl','loc':{'line':1},'inner':[{'id':'0x456','previousDecl':'0x123'}]}
        b={'inner':[{'previousDecl':'0xaa','id':'0xbb'}],'kind':'Decl','id':'0xaa','range':{'line':9}}
        self.assertEqual(self.fingerprint(a)['sha256'],self.fingerprint(b)['sha256'])
        b['inner'][0]['previousDecl']='0xbb'
        self.assertNotEqual(self.fingerprint(a)['sha256'],self.fingerprint(b)['sha256'])
    def test_values_flags_and_null_identity(self):
        for key,left,right in [('value','0x123','0x456'),('isVolatile',True,False),('id','0x0','0x1')]:
            self.assertNotEqual(self.fingerprint({key:left})['sha256'],self.fingerprint({key:right})['sha256'])
    def test_repeated_process_determinism_and_counts(self):
        value={'id':'0x1','inner':[{'previousDecl':'0x1'}]};a=self.fingerprint(value);b=self.fingerprint(value)
        self.assertEqual(a['sha256'],b['sha256']);self.assertEqual(a['ast_ids'],1);self.assertEqual(a['ast_nodes'],2)
    def test_invalid_json_and_missing_input_fail_closed(self):
        with tempfile.TemporaryDirectory() as name:
            path=Path(name)/'bad.json';path.write_text('{')
            self.assertNotEqual(subprocess.run([NATIVE,str(path)],capture_output=True).returncode,0)
            self.assertNotEqual(subprocess.run([NATIVE,str(path)+'missing'],capture_output=True).returncode,0)

class CacheModeTests(unittest.TestCase):
    def test_ir_mode_avoids_ast_and_preserves_text_fast_path(self):
        from semantic_cache import Cache,sha
        class Fake:
            def __init__(self,root):self.source=root/'source.c';self.source.write_bytes(b'changed');self.ir_calls=0;self.full_calls=0
            def ast(self):raise AssertionError('IR mode must not build AST')
            def ir(self):self.ir_calls+=1;return b'IR',{}
            def full(self,output):self.full_calls+=1;output.write_bytes(b'new-object');return {}
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);compiler=Fake(root);cache=Cache(compiler,'ir');cache.entries=[dict(source=sha(b'original'),ir=b'IR',object=b'seed')];output=root/'out.o'
            self.assertEqual(cache.call(output)['reason'],'ir');self.assertEqual(output.read_bytes(),b'seed');self.assertEqual(compiler.full_calls,0)
            cache.entries[0]['source']=sha(b'changed');self.assertEqual(cache.call(output)['reason'],'text');self.assertEqual(compiler.ir_calls,1)
            compiler.source.write_bytes(b'another');cache.entries[0]['ir']=b'other';self.assertEqual(cache.call(output)['reason'],'compiled');self.assertEqual(output.read_bytes(),b'new-object')

class ContextTests(unittest.TestCase):
    def test_header_change_and_project_arrival_are_rejected(self):
        import context,hashlib
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);source=root/'source.c';source.write_text('');header=root/'header.h';header.write_text('old')
            fixed=dict(project_root=str(root),mutable_source=str(source),project_files=[str(header)],files={str(header):context.sha_file(header)},environment_sha256=hashlib.sha256(json.dumps(dict(os.environ),sort_keys=True).encode()).hexdigest(),bindings={str(header):str(header.resolve())})
            self.assertTrue(context.verify(fixed)['passed']);header.write_text('changed')
            with self.assertRaises(ValueError):context.verify(fixed)
            header.write_text('old');(root/'new.h').write_text('')
            with self.assertRaises(ValueError):context.verify(fixed)

if __name__=='__main__':unittest.main()

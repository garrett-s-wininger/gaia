import json
from pathlib import Path
import tempfile
import unittest
from evidence import EvidenceStore,generation,symbols,observed_symbols


class EvidenceChecks(unittest.TestCase):
    def test_lexical_containment_and_new_definition(self):
        text='def outer():\n    def inner():\n        return 1\n    return inner()\n'
        defs=symbols(text)
        self.assertEqual(observed_symbols(defs,[2,3,4]),['outer','outer.inner'])
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'src').mkdir();(root/'tests').mkdir();p=root/'src/a.py';p.write_text(text)
            store=EvidenceStore(root,'fixed')
            run={'context':'fixed','generation':store.current(),'unchanged_during_run':True,
                 'observed':{'tests/test_a.py::test_a':['src/a.py::outer']},
                 'functions':{'src/a.py::outer':defs['outer']},'outcomes':{'tests/test_a.py::test_a':'passed'}}
            store.publish(run)
            self.assertEqual(store.inspect('src/a.py','outer')['observations'][0]['status'],'current')
            p.write_text(text.replace('return 1','return 2'))
            result=store.inspect('src/a.py','outer')
            self.assertEqual(result['observations'][0]['status'],'historical')
            self.assertFalse(result['observations'][0]['same_function_ast'])
            with self.assertRaises(ValueError):store.publish(run)
            with self.assertRaises(ValueError):store.inspect('../outside.py','outer')
            p.write_text(text.replace('outer','renamed'))
            self.assertEqual(store.inspect('src/a.py','outer')['status'],'absent')
            self.assertEqual(store.inspect('src/a.py','renamed')['observations'],[])

    def test_extensionless_native_dependency_compatibility(self):
        from testmon.testmon_core import SourceTree
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'foo';p.write_text('hello template')
            one=SourceTree(d).get_file('foo')
            self.assertEqual(len(one.blocks),1)
            before=one.method_checksums
            p.write_text('changed template')
            two=SourceTree(d).get_file('foo')
            self.assertNotEqual(before,two.method_checksums)


if __name__=='__main__':unittest.main()

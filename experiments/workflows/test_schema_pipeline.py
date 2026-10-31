import dataclasses
import json
import unittest
import schema_pipeline as pipeline


class PipelineTests(unittest.TestCase):
    def test_shared_and_parallel_match_independent(self):
        payload = pipeline.fixture(4, 3)
        oracle = pipeline.generate(payload, shared=False)
        for parallel in (False, True):
            self.assertEqual(pipeline.generate(payload, parallel=parallel), oracle)
        for name, output in oracle.items():
            self.assertGreater(pipeline.consume(name, output), 0)

    def test_fresh_immutable_bindings(self):
        records = pipeline.resolve(pipeline.fixture(2, 2))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            records[0].name = 'changed'
        data = json.loads(pipeline.fixture(2, 2));data['records']['Record00000']['fields']['parent']['type'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            pipeline.resolve(json.dumps(data))

    def test_early_cutoff_observes_each_output(self):
        payload = pipeline.fixture(2, 2);base = pipeline.operation(payload)
        data = json.loads(payload);data['records']['Record00000']['description'] += ' changed'
        next_payload = json.dumps(data).encode()
        cutoff = pipeline.operation(next_payload, base, True)
        full = pipeline.operation(next_payload, base, False)
        self.assertEqual({k:v[:2] for k,v in cutoff.items()}, {k:v[:2] for k,v in full.items()})
        self.assertEqual([k for k,v in cutoff.items() if v[2]], ['docs'])
        data['records']['Record00000']['fields']['field00']['type'] = 'integer'
        changed = pipeline.operation(json.dumps(data), base, True)
        self.assertTrue(all(v[2] for v in changed.values()))

    def test_reorder_is_unchanged_and_removal_invalidates(self):
        payload = pipeline.fixture(3, 2);base = pipeline.operation(payload)
        data = json.loads(payload)
        self.assertFalse(any(v[2] for v in pipeline.operation(json.dumps(data, sort_keys=True), base, True).values()))
        del data['records']['Record00000']['fields']['field00']
        self.assertTrue(all(v[2] for v in pipeline.operation(json.dumps(data), base, True).values()))

    def test_bad_identifiers_and_version(self):
        data = json.loads(pipeline.fixture(2, 2));data['records']['bad name'] = data['records']['Record00000']
        with self.assertRaises(ValueError):pipeline.resolve(json.dumps(data))
        with self.assertRaises(ValueError):pipeline.resolve('{"format":"unknown"}')

    def test_shared_output_namespace_restrictions(self):
        for names in [('dataclass','Other'),('str','Other'),('Foo','foo'),('sqlite_reserved','Other')]:
            data={'format':'gaia-schema-experiment-1','records':{n:{'fields':{'value':{'type':'string'}}} for n in names}}
            with self.assertRaises(ValueError):pipeline.resolve(json.dumps(data))
        data={'format':'gaia-schema-experiment-1','records':{'Good':{'fields':{'value':{'type':'string'},'Value':{'type':'integer'}}}}}
        with self.assertRaises(ValueError):pipeline.resolve(json.dumps(data))

    def test_generated_python_declarations_execute(self):
        import sys,types
        name='gaia_schema_execution_test';module=types.ModuleType(name);sys.modules[name]=module
        try:
            exec(pipeline.emit_python(pipeline.resolve(pipeline.fixture(3,2))),module.__dict__)
            self.assertEqual(module.Record00000('value',4,None).field00,'value')
        finally:sys.modules.pop(name,None)


if __name__ == '__main__':unittest.main()

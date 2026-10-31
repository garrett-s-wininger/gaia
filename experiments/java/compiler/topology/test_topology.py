import unittest
from run_topology import parse_smaps,validate

class MemoryTests(unittest.TestCase):
    def test_pss_and_private_are_distinct_from_double_counted_rss(self):
        value=parse_smaps('Rss: 100 kB\nPss: 60 kB\nPrivate_Clean: 10 kB\nPrivate_Dirty: 20 kB\nPss_Anon: 30 kB\nPss_File: 30 kB\n')
        self.assertEqual(value['rss_bytes'],102400);self.assertEqual(value['pss_bytes'],61440);self.assertEqual(value['private_bytes'],30720)
    def test_missing_memory_fields_are_not_silently_zero(self):
        with self.assertRaises(ValueError):parse_smaps('Rss: 0 kB\n')
    def test_each_independent_target_must_match_its_cli_reference(self):
        expected=[dict(classes=1,bytes=2,sha256='a'),dict(classes=1,bytes=3,sha256='b')]
        rows=[dict(target=i,**expected[i%2]) for i in range(4)];result=dict(replies=[dict(ok=True,outputs=rows)])
        validate(result,expected,4)
        rows[3]['sha256']='a'
        with self.assertRaises(ValueError):validate(result,expected,4)
    def test_duplicate_or_missing_targets_are_rejected(self):
        expected=[dict(classes=1,bytes=2,sha256='a')]*2;row=dict(target=0,**expected[0])
        for outputs in ([row,row],[]):
            with self.assertRaises(ValueError):validate(dict(replies=[dict(ok=True,outputs=outputs)]),expected,2)

if __name__=='__main__':unittest.main()

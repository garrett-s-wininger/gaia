import unittest

from node_project_benchmark import diagnostic_counts

class DiagnosticCounterTests(unittest.TestCase):
    def test_padding_and_process_memory_do_not_change_exact_counts(self):
        first='Files: 57\nTypes: 15899\nMemory used: 99999K\nCheck time: 0.52s\nTotal time: 0.70s\n'
        wider='Files:    57\nTypes:  15899\nMemory used: 100001K\nCheck time: 0.54s\nTotal time: 0.72s\n'
        self.assertEqual(diagnostic_counts(first,0.8),{'Files':57,'Types':15899})
        self.assertEqual(diagnostic_counts(first,0.8),diagnostic_counts(wider,0.8))
        self.assertNotEqual(diagnostic_counts(first,0.8),diagnostic_counts(wider.replace('15899','15900'),0.8))
    def test_invalid_counts_and_stale_clock_metrics_fail(self):
        for text in ('Files: unknown','Files: -1','Check time: -0.01s','Total time: 100.0s','Memory used: unknown'):
            with self.subTest(text=text),self.assertRaises(ValueError):diagnostic_counts(text,0.8)

if __name__=='__main__':unittest.main()

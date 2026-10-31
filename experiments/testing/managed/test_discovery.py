import pathlib,tempfile,unittest
from discovery import class_identity,require_current
class InputGenerationTests(unittest.TestCase):
    def test_change_addition_and_removal_invalidate(self):
        with tempfile.TemporaryDirectory() as d:
            root=pathlib.Path(d);a=root/'A.class';a.write_bytes(b'a');pins=class_identity(root)
            require_current(root,pins)
            a.write_bytes(b'b')
            with self.assertRaises(ValueError):require_current(root,pins)
            a.write_bytes(b'a');b=root/'B.class';b.write_bytes(b'b')
            with self.assertRaises(ValueError):require_current(root,pins)
            b.unlink();a.unlink()
            with self.assertRaises(ValueError):require_current(root,pins)
if __name__=='__main__':unittest.main()

import concurrent.futures, sqlite3, unittest
from database import Fixture,schema,fingerprint
class DatabaseTests(unittest.TestCase):
    def test_modes_restore_after_success_and_failure(self):
        f=Fixture(schema(2,31))
        try:
            for mode in ['replay','backup','deserialize','rollback']:
                for fail in [False,True]:self.assertEqual(f.operation(mode,100,fail)['failure_injected'],fail)
        finally:f.close()
    def test_parallel_private_state(self):
        f=Fixture(schema(2,31))
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                self.assertEqual(len(list(pool.map(lambda i:f.operation('rollback',i,i%2==0),range(16)))),16)
            self.assertEqual(fingerprint(f.template),f.expected)
        finally:f.close()
    def test_rollback_does_not_hide_commit_escape(self):
        f=Fixture(schema(2,31));db=f.make('rollback')
        try:
            db.execute("UPDATE t0 SET value='escaped'");db.commit();db.rollback()
            self.assertNotEqual(fingerprint(db),f.expected)
        finally:db.close();f.close()
if __name__=='__main__':unittest.main()

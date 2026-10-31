"""Bounded SQLite fixture reuse: replay, backup, deserialize and private rollback."""
import argparse, concurrent.futures, contextlib, fcntl, hashlib, json, os, pathlib, random, sqlite3, statistics, sys, threading, time
HERE=pathlib.Path(__file__).resolve().parent

def schema(tables, rows):
    parts=['PRAGMA foreign_keys=ON; BEGIN;']
    for table in range(tables):
        parts += [f'CREATE TABLE t{table}(id INTEGER PRIMARY KEY, value TEXT NOT NULL, n INTEGER NOT NULL);']
        parts += [f"INSERT INTO t{table} VALUES({i},'fixture-{i%37}',{i%101});" for i in range(rows)]
        parts += [f'CREATE INDEX idx{table} ON t{table}(n);']
    return '\n'.join(parts+['COMMIT;'])

def fingerprint(db):
    h=hashlib.sha256()
    for line in db.iterdump():h.update(line.encode());h.update(b'\n')
    return h.hexdigest()

class Fixture:
    def __init__(self, sql):
        self.sql=sql;self.local=threading.local();self.connections=[];self.lock=threading.Lock()
        begin=time.perf_counter_ns();self.template=sqlite3.connect(':memory:',check_same_thread=False);self.template.executescript(sql)
        self.seed_ns=time.perf_counter_ns()-begin
        self.expected=fingerprint(self.template)
        begin=time.perf_counter_ns();self.image=self.template.serialize();self.serialize_ns=time.perf_counter_ns()-begin
    def make(self,mode):
        db=sqlite3.connect(':memory:',check_same_thread=False)
        if mode=='replay':db.executescript(self.sql)
        elif mode in ('backup','rollback'):
            with self.lock:self.template.backup(db)
        elif mode=='deserialize':db.deserialize(self.image)
        else:raise ValueError(mode)
        return db
    def operation(self,mode,number,fail=False,validate=True):
        begin=time.perf_counter_ns();created=False
        if mode=='rollback':
            if not hasattr(self.local,'db'):
                self.local.db=self.make(mode);self.connections.append(self.local.db);created=True
            db=self.local.db
        else:db=self.make(mode);created=True
        setup=time.perf_counter_ns()-begin
        expected_count=db.execute('SELECT count(*) FROM t0').fetchone()[0]
        try:
            db.execute('BEGIN')
            db.execute('UPDATE t0 SET value=?,n=n+1 WHERE id%17=0',(f'test-{number}',))
            db.execute('INSERT INTO t0(value,n) VALUES(?,?)',(f'private-{number}',number))
            assert db.execute('SELECT count(*) FROM t0').fetchone()[0]==expected_count+1
            assert db.execute('SELECT value FROM t0 ORDER BY id DESC LIMIT 1').fetchone()[0]==f'private-{number}'
            if fail:db.execute('INSERT INTO missing_table VALUES(1)')
        except sqlite3.OperationalError:
            if not fail:raise
        finally:
            db.rollback()
        assert db.execute('SELECT count(*) FROM t0').fetchone()[0]==expected_count
        end=time.perf_counter_ns()
        # Full logical equality is an independent post-operation oracle outside timings.
        if validate:assert fingerprint(db)==self.expected
        if mode!='rollback':db.close()
        return dict(setup_ns=setup,whole_ns=end-begin,first_private_fixture=created,failure_injected=fail)
    def close(self):
        for db in self.connections:db.close()
        self.template.close()

def run(args):
    sql=schema(args.tables,args.rows);allrows=[];rng=random.Random(818)
    preflight=Fixture(sql)
    try:
        for mode in ['replay','backup','deserialize','rollback']:
            preflight.operation(mode,999,fail=False);preflight.operation(mode,1000,fail=True)
    finally:preflight.close()
    for block in range(args.trials):
        modes=['replay','backup','deserialize','rollback'];rng.shuffle(modes)
        for workers in args.workers:
            for mode in modes:
                fixture=Fixture(sql);begin=time.perf_counter_ns();cpu=time.process_time_ns()
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                    values=list(pool.map(lambda i:fixture.operation(mode,i,fail=(i%7==0),validate=False),range(args.tasks)))
                for connection in fixture.connections:connection.close()
                fixture.connections.clear()
                if mode!='replay':fixture.template.close()
                elapsed=time.perf_counter_ns()-begin;cpu=time.process_time_ns()-cpu
                if mode=='replay':fixture.template.close()  # replay's template is an independent oracle, not required setup
                allrows.append(dict(block=block,mode=mode,workers=workers,tasks=args.tasks,seed_ns=fixture.seed_ns,serialize_ns=fixture.serialize_ns,serialized_bytes=len(fixture.image),session_ns=elapsed,charged_session_ns=elapsed+(fixture.seed_ns if mode!='replay' else 0)+(fixture.serialize_ns if mode=='deserialize' else 0),cpu_ns=cpu,operations=values,logical_sha256=fixture.expected))
    out=dict(schema='GAIA-TEST-FIXTURE-1',sqlite=sqlite3.sqlite_version,python=sys.version,workload=dict(tables=args.tables,rows_per_table=args.rows,tasks=args.tasks),scope='Synthetic migration/fixture workload, SQLite in-memory database; rollback supports no committing/external side effects; serialization and backup are copying not COW.',rows=allrows)
    summary=[]
    for workers in args.workers:
        for mode in ['replay','backup','deserialize','rollback']:
            rows=[r for r in allrows if r['workers']==workers and r['mode']==mode]
            summary.append(dict(mode=mode,workers=workers,median_session_ms=statistics.median(r['session_ns']/1e6 for r in rows),median_charged_session_ms=statistics.median(r['charged_session_ns']/1e6 for r in rows),median_operation_ms=statistics.median(v['whole_ns']/1e6 for r in rows for v in r['operations']),median_setup_ms=statistics.median(v['setup_ns']/1e6 for r in rows for v in r['operations'])))
    args.output.mkdir(parents=True,exist_ok=True);raw=args.output/'results.json';raw.write_text(json.dumps(out,indent=2)+'\n')
    (args.output/'summary.json').write_text(json.dumps(dict(cases=summary,raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),raw_bytes=raw.stat().st_size),indent=2)+'\n')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--tables',type=int,default=12);p.add_argument('--rows',type=int,default=1000);p.add_argument('--tasks',type=int,default=16);p.add_argument('--workers',type=int,nargs='+',default=[1,4]);p.add_argument('--trials',type=int,default=3);a=p.parse_args()
    if min(a.tables,a.rows,a.tasks,a.trials,*a.workers)<1:p.error('positive bounds required')
    run(a)

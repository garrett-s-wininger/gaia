"""Shared serial validation must preserve private compiler visibility and cwd."""
import hashlib
import json
from pathlib import Path
import subprocess
import struct
import sys
import unittest

import test_build_decisions as previous


class SharedHistoryTests(previous.HistoricalCandidateTests):
    def request(self, value, extra=(), mode='journal-history', body=None, files=None):
        if mode == 'journal-history':mode = 'journal-history-shared'
        return super().request(value, extra, mode, body, files)

    def test_equal_and_distinct_views_with_parallel_misses(self):
        # Three actions: two share membership; the third cannot see optional.h,
        # although that file exists physically and is visible to the others.
        body = '#if __has_include("optional.h")\n#include "optional.h"\n#else\n#define VALUE 7\n#endif\nint answer(void){return VALUE;}\n'
        header = self.root/'optional.h'
        argv = self.request(11, body=body, files={str(header):b'#define VALUE 11\n'})
        self.views.write_text('GAIACV1\n'+''.join(f'{3 if p==str(header) else 7}\n' for p in sorted([str(self.source),str(header)])))
        commands=[]
        for i in range(3):
            command=self.command.copy();command[command.index('-o')+1]=f'unit{i}.o'
            command += [f'-Danswer=answer{i}'];commands.append(command)
        Path(argv[7]).write_bytes(previous.wire.encode_requests(commands));argv[8]='3'
        link=[str(self.lld),'-shared','-o','libanswer.so',*[f'unit{i}.o' for i in range(3)]]
        self.linkplan.write_bytes(previous.wire.encode_requests([link]))

        def run():
            p=subprocess.run(argv,cwd=self.output,capture_output=True,text=True)
            self.assertEqual(p.returncode,0,p.stderr);result=json.loads(p.stdout)
            self.assertTrue(result['correct']);self.assertEqual(result['cache_write_errors'],0)
            return result

        cold=run();self.assertEqual(cold['compiler_executions'],3)
        warm=run();self.assertEqual(warm['compiler_executions'],0)
        self.assertEqual(warm['validation_groups'],2);self.assertEqual(warm['view_builds'],2)
        self.assertEqual(cold['object_sha256'],warm['object_sha256'])
        # Independently compile each visibility variant, then compare all bytes.
        ref=self.root/'ref';ref.mkdir()
        for i,command in enumerate(commands):
            if i==2:header.unlink()
            subprocess.run(command,cwd=ref,check=True,capture_output=True)
            self.assertEqual(warm['object_sha256'][i],hashlib.sha256((ref/f'unit{i}.o').read_bytes()).hexdigest())
        subprocess.run(link,cwd=ref,check=True,capture_output=True)
        self.assertEqual((ref/'libanswer.so').read_bytes(),(self.output/'libanswer.so').read_bytes())
        subprocess.run([sys.executable,'-c',
            'import ctypes,sys; p=ctypes.CDLL(sys.argv[1]); assert [getattr(p,"answer"+str(i))() for i in range(3)]==[11,11,7]',
            str(self.output/'libanswer.so')],check=True,capture_output=True)


class MemoHistoryTests(SharedHistoryTests):
    def request(self, value, extra=(), mode='journal-history', body=None, files=None):
        if mode == 'journal-history':mode = 'journal-history-memo'
        return super().request(value, extra, mode, body, files)

    def test_replay_memo_tracks_cwd_transitions(self):
        a=self.root/'a';b=self.root/'b';a.mkdir();b.mkdir()
        cmd=self.request(1,files={str(a/'optional.h'):b'unused',str(b/'marker'):b'unused'})
        self.consume(cmd,1)
        path=next(self.cache.glob('*.gdo'));record=path.read_bytes()
        n,size=struct.unpack_from('<QQ',record,72);raw=record[88:88+n];obj=record[88+n:]
        def text(s):
            encoded=s.encode();return struct.pack('<Q',len(encoded))+encoded
        def query(op,p,outcome,value):
            encoded=p.encode();return struct.pack('<BBI',op,outcome,len(encoded))+encoded+hashlib.sha256(value).digest()
        def cwd(p):return query(9,str(p),0,b'\x09'+text('system')+struct.pack('<Q',0))
        def exists(value):return query(2,'optional.h',int(not value),bytes([2,int(value)]))
        prefix=b''.join([cwd(a),exists(True),cwd(b),exists(False)]*2)+cwd(self.root)
        # Leave cwd changed at the end: the next candidate must start at root.
        journal=b'GAIAJR01'+struct.pack('<I',struct.unpack_from('<I',raw,8)[0]+10)+prefix+raw[12:]+cwd(a)
        rest=struct.pack('<QQ',len(journal),size)+journal+obj;key=record[8:40]
        path.write_bytes(b'GAIADC01'+key+hashlib.sha256(key+rest).digest()+rest)
        for _ in range(2):
            hit=self.consume(cmd,1);self.assertEqual(hit['compiler_executions'],0)
            self.assertGreaterEqual(hit['memo_hits'],2)

    def test_memo_saturation_falls_back_to_observation(self):
        cmd=self.request(1);self.consume(cmd,1)
        path=next(self.cache.glob('*.gdo'));record=path.read_bytes()
        n,size=struct.unpack_from('<QQ',record,72);raw=record[88:88+n];obj=record[88+n:]
        negative=hashlib.sha256(bytes([2,0])).digest();queries=[]
        for i in range(50000):
            name=f'missing-{i:05}'.encode();queries.append(struct.pack('<BBI',2,1,len(name))+name+negative)
        # Once insertion stops, even a repeated late query must still replay.
        queries.append(queries[-1])
        journal=b'GAIAJR01'+struct.pack('<I',struct.unpack_from('<I',raw,8)[0]+len(queries))+b''.join(queries)+raw[12:]
        rest=struct.pack('<QQ',len(journal),size)+journal+obj;key=record[8:40]
        path.write_bytes(b'GAIADC01'+key+hashlib.sha256(key+rest).digest()+rest)
        hit=self.consume(cmd,1);self.assertEqual(hit['compiler_executions'],0)
        self.assertLessEqual(hit['memo_bytes'],8*1024*1024)
        self.assertGreater(hit['memo_bytes'],8*1024*1024-1024)


if __name__=='__main__':unittest.main()

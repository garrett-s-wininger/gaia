"""Separate allocation/call diagnostic; intrusive samples are not benchmark medians."""
import argparse
import cProfile
import json
from pathlib import Path
import pstats
import shutil
import socket
import tempfile
import tracemalloc
from unittest import mock

import benchmark as baseline
import binary_transport as binary
import transfer as t


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--corpus',choices=('small','mixed','large'),default='mixed')
    parser.add_argument('--modes',nargs='+',choices=t.MODES,default=['pack-coalesced','pack-full','selected-batch'])
    parser.add_argument('--transports',nargs='+',choices=('http','binary','binary-buffered'),default=['http','binary','binary-buffered'])
    args=parser.parse_args();collection=t.build_collection(baseline.synthetic(args.corpus));results=[]
    original_recv=socket.socket.recv_into;original_send=socket.socket.sendall
    for transport in args.transports:
        server=t.local_server(collection) if transport=='http' else binary.local_server(collection,buffered=transport=='binary-buffered')
        with server as url:
            for mode in args.modes:
                with tempfile.TemporaryDirectory(prefix='gaia allocation profile ') as tmp:
                    cache=Path(tmp)/'cache';baseline.seed_cache(collection,cache,[],False)
                    io=dict(recv_calls=0,recv_bytes=0,requested_recv_bytes=0,max_requested_recv_bytes=0,sendall_calls=0,sendall_bytes=0)
                    def recv(sock,buffer,*rest):
                        count=original_recv(sock,buffer,*rest);io['recv_calls']+=1;io['recv_bytes']+=count
                        io['requested_recv_bytes']+=len(buffer);io['max_requested_recv_bytes']=max(io['max_requested_recv_bytes'],len(buffer));return count
                    def send(sock,data,*rest):
                        io['sendall_calls']+=1;io['sendall_bytes']+=len(data);return original_send(sock,data,*rest)
                    profile=cProfile.Profile();tracemalloc.start()
                    with mock.patch.object(socket.socket,'recv_into',recv),mock.patch.object(socket.socket,'sendall',send):
                        profile.enable()
                        sample=t.fetch(url,collection['manifest_id'],len(collection['manifest']),list(collection['objects']),cache,mode)
                        profile.disable()
                    current,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
                    baseline.validate(collection,cache,list(collection['objects']))
                    functions=[]
                    for (filename,line,name),(primitive,calls,total,cumulative,callers) in pstats.Stats(profile).stats.items():
                        if Path(filename).name not in ('transfer.py','binary_transport.py','batch.py'):continue
                        functions.append(dict(file=Path(filename).name,line=line,function=name,calls=calls,self_seconds=total,cumulative_seconds=cumulative))
                    functions.sort(key=lambda f:f['cumulative_seconds'],reverse=True)
                    results.append(dict(transport=transport,mode=mode,traced_current_bytes=current,traced_peak_bytes=peak,client_socket_calls=io,
                                        sample=sample,functions=functions))
    result=dict(scope='one cold fetch per case under cProfile/tracemalloc/client socket wrappers; diagnostic overhead is substantial; not performance medians',
        corpus=args.corpus,payload_bytes=len(collection['pack']),objects=len(collection['objects']),cases=results,
        source_sha256={p.name:t.digest(p.read_bytes()) for p in Path(__file__).resolve().parent.glob('*.py')})
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()

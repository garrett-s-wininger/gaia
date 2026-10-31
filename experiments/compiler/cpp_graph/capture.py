"""Capture the bounded real fmt/integration graph without compiling objects."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import graph

HERE=Path(__file__).resolve().parent


def arguments():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=HERE/'_work/downloads/fmt-12.2.0.tar.gz')
    parser.add_argument('--llvm',type=Path,required=True)
    parser.add_argument('--host',type=Path,required=True)
    parser.add_argument('--blake3-helper',type=Path,required=True)
    parser.add_argument('--blake3-library',type=Path,default=Path('/usr/lib/libblake3.so'))
    parser.add_argument('--ninja',type=Path,required=True)
    parser.add_argument('--ccache',type=Path,required=True)
    parser.add_argument('--tool-library-path',type=Path)
    parser.add_argument('--output',type=Path,default=HERE/'_work/capture.json')
    return parser.parse_args()


def main(args):
    args.output.parent.mkdir(parents=True,exist_ok=True);work=HERE/'_work'/('capture-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ'));work.mkdir(parents=True)
    info=graph.prepare(args,work)
    result=dict(source_url=graph.SOURCE_URL,archive_sha256=graph.SOURCE_SHA,targets=info['targets'],sdk_search=info['roots'],input_files=len(info['files']),input_bytes=sum(map(len,info['files'].values())),crt_aliases=info['aliases'],sdk_link_inputs=sorted(info['sdk_inputs']),work=str(work))
    args.output.write_text(json.dumps(result,indent=2)+'\n');print(args.output);print(len(info['files']),'admitted files,',result['input_bytes'],'bytes')

if __name__=='__main__':main(arguments())

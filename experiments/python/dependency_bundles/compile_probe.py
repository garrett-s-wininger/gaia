"""Separate untimed compile audit; record filenames/sizes, never source text."""
import atexit
import json
from pathlib import Path
import runpy
import sys

command=json.loads(Path(sys.argv[1]).read_text());output=Path(sys.argv[2]);events=[]
def audit(event,args):
    if event=='compile':
        source,filename=args
        events.append(dict(filename=filename,source_bytes=len(source) if isinstance(source,(str,bytes)) else None))
sys.addaudithook(audit)
atexit.register(lambda:output.write_text(json.dumps(events,indent=2)+'\n'))
script=next(i for i,v in enumerate(command) if v.endswith(('.py','.pyc')) and Path(v).is_file())
sys.argv=command[script:]
runpy.run_path(sys.argv[0],run_name='__main__')

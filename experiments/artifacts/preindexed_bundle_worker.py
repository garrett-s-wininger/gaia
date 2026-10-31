"""Identical compact import/resource provider, portable producer index reader."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import compact_python
import preindexed_bundle as bundle
import os
import runpy

if __name__=='__main__':
    binding=Path(os.environ['GAIA_BINDING']).read_bytes()
    compact_python.Reader=lambda root,index_path,index_pin,logical_pin:bundle.Reader(root,index_path,index_pin,binding,os.environ['GAIA_BINDING_PIN'])
    runpy.run_path(str(Path(__file__).with_name('compact_python_worker.py')),run_name='__main__')

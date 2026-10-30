"""Interpreter-only and shared-harness controls for lifecycle characterization."""
import time
import sys
_entered=time.perf_counter();_cpu=time.process_time();observer=None
if sys._xoptions.get('gaia_phases'):
    sys.path.insert(0,sys.argv[0].rsplit('/',1)[0])
    from process_phases import Observer
    observer=Observer(_entered,_cpu)


def phase(name):
    if observer is not None:observer.mark(name)


kind=sys.argv[1]
if kind=='harness':
    sys.path.insert(0,sys.argv[0].rsplit('/',1)[0])
    options={k:sys._xoptions.pop(k) for k in ('gaia_phases','gaia_profile') if k in sys._xoptions}
    import django_worker
    sys._xoptions.update(options)
elif kind!='empty':raise ValueError('unknown control')
phase('common_prepared');phase('main_entered');phase('workload_begin');phase('workload_finished')
phase('validation_finished');phase('result_built');phase('result_encoded')
print('{"correct":true,"kind":"'+kind+'"}',flush=observer is not None)
phase('result_flushed')
if observer is not None:observer.finish()

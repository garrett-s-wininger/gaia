"""Opt-in lifecycle diagnostics; no producer/loader behavior changes."""
import atexit
import gc
import os
import sys
import time


class Observer:
    def __init__(self,entered,cpu_entered):
        self.path=sys._xoptions['gaia_phases'];self.prefix=sys._xoptions.get('gaia_profile')
        self.fast=sys._xoptions.get('gaia_exit')=='fast'
        self.batch=sys._xoptions.get('gaia_gc')=='batch';self.gc_was_enabled=gc.isenabled();self.gc_restored=False
        self.gc_events=[];self.gc_active={}
        self.points=[('worker_entered',entered,cpu_entered)];self.completed=[];self.profile=None
        if self.prefix:
            import cProfile
            self.profile_type=cProfile.Profile
        self.mark('observer_ready')
        self.callback=self.gc_callback;gc.callbacks.append(self.callback)
        if self.batch:gc.disable()
        if self.prefix:self.profile=self.profile_type();self.profile.enable()
        atexit.register(self.on_exit)
    def mark(self,name,stamp=None):
        old=self.profile
        if old is not None:old.disable()
        self.points.append((name,time.perf_counter() if stamp is None else stamp,time.process_time()))
        if old is not None:
            self.completed.append((self.points[-2][0],name,old))
            self.profile=self.profile_type();self.profile.enable()
    def stop_profile(self):
        if self.profile is not None:
            self.profile.disable();self.profile=None
        for i,(start,end,profile) in enumerate(self.completed):
            profile.dump_stats(f'{self.prefix}.{i:02}-{start}--{end}.pstats')
    def write(self):
        # repr avoids importing a serializer into otherwise empty controls.
        if self.callback in gc.callbacks:gc.callbacks.remove(self.callback)
        with open(self.path,'w') as stream:stream.write(repr(dict(points=self.points,gc_events=self.gc_events)))
    def gc_callback(self,stage,info):
        generation=info['generation']
        if stage=='start':self.gc_active[generation]=(time.perf_counter(),time.process_time(),self.points[-1][0])
        else:
            start,cpu,phase=self.gc_active.pop(generation)
            self.gc_events.append(dict(generation=generation,phase=phase,wall_seconds=time.perf_counter()-start,
                                       cpu_seconds=time.process_time()-cpu,collected=info['collected'],uncollectable=info['uncollectable']))
    def restore_gc(self):
        if self.batch and not self.gc_restored:
            self.mark('batch_gc_begin')
            if self.gc_was_enabled:gc.enable()
            gc.collect();self.gc_restored=True
            self.mark('batch_gc_finished')
    def finish(self):
        self.mark('worker_returned')
        self.restore_gc()
        if self.fast:
            self.mark('fast_exit_requested');self.stop_profile();self.write();os._exit(0)
    def on_exit(self):
        self.restore_gc()
        self.mark('atexit_entered');self.stop_profile()
        self.mark('telemetry_write_begin');self.write()

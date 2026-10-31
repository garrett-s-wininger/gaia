"""Real dependency objects across cache growth, eviction and injected failures."""
from pathlib import Path
import argparse,errno,hashlib,json,os,random,statistics,sys,time
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
import cache_store as cache
from run_catalogue import source_rows

def digest(body):return hashlib.sha256(body).hexdigest()
def object_desc(body):return dict(sha256=digest(body),size=len(body))
def available(store,objects):
    result={key:bytes(body) for key,body in store.iter_available(objects)}
    for key,body in result.items():
        if digest(body)!=key:raise ValueError('bad cache bytes')
    return result

def commit(store,items):
    store.prepare([obj for obj,body in items])
    for obj,body in items:store.put_verified(obj,body)
    store.finish()

def run(args):
    args.work.mkdir(parents=True,exist_ok=True);args.output.mkdir(parents=True,exist_ok=True)
    source=source_rows(args.index);payload=args.payload.read_bytes();unique={}
    for row in source:
        body=payload[row['offset']:row['offset']+row['size']]
        if digest(body)!=row['sha256']:raise ValueError('producer file hash')
        unique.setdefault(row['sha256'],(object_desc(body),body))
    items=list(unique.values());random.Random(114).shuffle(items);rows=[]
    for layout in ('files','packed'):
        root=args.work/layout;published=[];held=[];started=time.perf_counter();offset=0
        for epoch,end in enumerate((100,400,900,1600,len(items))):
            store=cache.make(root,layout)
            try:
                new=items[offset:end];commit(store,new);offset=end;published=items[:end]
                if layout=='packed' and epoch==1:
                    held=list(available(store,[obj for obj,body in published[:8]]).items())
                # Measure selected single-object lookup in a populated store, not full scan.
                wanted=[published[-1][0]];samples=[]
                for repeat in range(args.lookups):
                    begin=time.perf_counter();got=available(store,wanted);samples.append((time.perf_counter()-begin)*1000)
                    if got.get(wanted[0]['sha256'])!=published[-1][1]:raise ValueError('lookup miss')
                stats=store.stats.copy()
            finally:store.close()
            # Reopen costs include index parsing and startup cleanup.
            reopened=[]
            for repeat in range(args.lookups):
                begin=time.perf_counter();store=cache.make(root,layout)
                try:got=available(store,wanted)
                finally:store.close()
                reopened.append((time.perf_counter()-begin)*1000)
            rows.append(dict(layout=layout,epoch=epoch,objects=end,lookup_ms=samples,reopen_lookup_ms=reopened,stats=stats))
        if layout=='packed':
            # Eviction is an experimental policy wrapper over Packed; explicit full
            # compaction publishes its reduced live set, preserving owned old views.
            store=cache.Packed(root)
            try:
                victim={obj['sha256'] for obj,body in published[::2]};kept=[pair for pair in published if pair[0]['sha256'] not in victim]
                for key in victim:store.invalidate(key)
                store.compact=True;newbody=b'gaia lifecycle marker';obj=object_desc(newbody);store.put_verified(obj,newbody);store.finish()
                if any(key in available(store,[o for o,b in published]) for key in victim):raise ValueError('eviction not effective')
                if any(available(store,[o])[o['sha256']]!=b for o,b in kept):raise ValueError('live entry lost')
                if any(digest(body)!=key for key,body in held):raise ValueError('old reader view lost')
                rows.append(dict(layout='packed',event='evict-compact',evicted=len(victim),retained_views=len(held),stats=store.stats.copy()))
            finally:store.close()
        rows.append(dict(layout=layout,event='complete',seconds=time.perf_counter()-started))
    # Fault probes use their own tiny real-data cache so a failure never mutates the
    # measured populated stores. Atomic visibility is tested; power loss is not.
    checks=[];root=args.work/'faults';first=items[:2];store=cache.Packed(root);commit(store,first);store.close()
    def intact():
        with_store=cache.Packed(root)
        try:return available(with_store,[o for o,b in first])=={o['sha256']:b for o,b in first}
        finally:with_store.close()
    # Complete record followed by a truncated record: only verified complete data
    # is offered to put_verified; abort's documented policy publishes that prefix.
    store=cache.Packed(root);good=items[2];truncated=items[3]
    try:
        store.prepare([good[0],truncated[0]]);store.put_verified(*good)
        partial=truncated[1][:-1]
        if digest(partial)==truncated[0]['sha256']:raise ValueError('invalid truncation probe')
        store.abort()
    finally:store.close()
    if not intact():raise ValueError('prefix recovery lost prior data')
    checks.append('interrupted body preserves prior and verified prefix')
    # Inject ENOSPC during staged data write. Existing head remains usable.
    store=cache.Packed(root)
    try:
        store.prepare([items[4][0]]);store._begin()
        with patch.object(store.stage,'write',side_effect=OSError(errno.ENOSPC,'injected disk full')):
            try:store.put_verified(*items[4]);raise AssertionError('write unexpectedly succeeded')
            except OSError:pass
    finally:store.close()
    if not intact():raise ValueError('disk full lost previous head')
    checks.append('disk full before publication preserves previous head')
    # Head publication fails after durable-name pack/index writes (no fsync claim).
    store=cache.Packed(root);original=store._publish_bytes
    try:
        store.prepare([items[5][0]]);store.put_verified(*items[5])
        def fail(name,path,body):
            if name=='head.tmp':raise OSError(errno.EIO,'injected head write failure')
            return original(name,path,body)
        with patch.object(store,'_publish_bytes',side_effect=fail):
            try:store.finish();raise AssertionError('head unexpectedly published')
            except OSError:pass
    finally:store.close()
    if not intact():raise ValueError('publication failure lost head')
    checks.append('head failure recovers previous index and cleans orphan pack')
    # Malformed locator geometry triggers existing fail-closed empty-cache policy.
    badroot=args.work/'corrupt-locator';store=cache.Packed(badroot);commit(store,first);store.close()
    head=json.loads((badroot/'head.json').read_text());idx=badroot/'indexes'/(head['index']['digest']+'.gai');raw=idx.read_bytes();data=json.loads(raw[16:]);data['objects'][0]['offset']=1
    body=json.dumps(data,separators=(',',':'),sort_keys=True).encode();import struct
    raw=cache.INDEX_MAGIC+struct.pack('!Q',len(body))+body;desc=cache.descriptor(raw);(badroot/'indexes'/(desc['digest']+'.gai')).write_bytes(raw);(badroot/'head.json').write_text(json.dumps(dict(version=1,index=desc)));idx.unlink()
    store=cache.Packed(badroot)
    try:
        if store.entries or not store.stats['corrupt_index']:raise ValueError('invalid locator accepted')
    finally:store.close()
    checks.append('invalid locator rejected; availability discarded by existing policy')
    data=dict(version=1,scope='warm local cache; existing research store plus explicit eviction wrapper; no fsync/power-loss or concurrent-writer guarantee',objects=len(items),logical_bytes=sum(o['size'] for o,b in items),index_sha256=digest(args.index.read_bytes()),payload_sha256=digest(payload),source_hashes={p.name:digest(p.read_bytes()) for p in (HERE/'lifecycle.py',HERE.parent/'cache_store.py')},observations=rows,checks=checks)
    raw=json.dumps(data,sort_keys=True).encode();(args.output/'results.json').write_bytes(raw)
    reduced=[dict(layout=r['layout'],objects=r['objects'],median_lookup_ms=statistics.median(r['lookup_ms']),median_reopen_lookup_ms=statistics.median(r['reopen_lookup_ms'])) for r in rows if 'lookup_ms' in r]
    (args.output/'summary.json').write_text(json.dumps(dict(rows=reduced,checks=checks,objects=len(items),raw_identity=dict(bytes=len(raw),sha256=digest(raw))),indent=2)+'\n');print(json.dumps(reduced,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--index',type=Path,required=True);p.add_argument('--payload',type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--lookups',type=int,default=7);run(p.parse_args())

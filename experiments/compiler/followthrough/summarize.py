"""Publish compact portable review artifacts; full observations remain ignored."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import statistics
from run_ir import save,sha

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]

def stats(rows,key):
    values=[r[key] for r in rows]
    return dict(median=statistics.median(values),min=min(values),max=max(values),samples=len(values))

def main(a):
    entries=[];evidence=[]
    def publish(path,name,identifier,status,summary,report):
        data=json.loads(path.read_text());assert data['status']=='complete';dest=HERE/'results'/name;dest.mkdir(parents=True,exist_ok=True);raw=dest/'results.json';shutil.copyfile(path,raw);validation=path.with_name('validation.json');check=json.loads(validation.read_text());assert check['passed'] and check['raw_sha256']==sha(raw.read_bytes());shutil.copyfile(validation,dest/'validation.json')
        save(dest/'summary.json',summary);(dest/'REPORT.md').write_text(report)
        item=dict(path=raw.relative_to(ROOT).as_posix(),bytes=raw.stat().st_size,sha256=sha(raw.read_bytes()));save(dest/'raw-identity.json',item);evidence.append(item)
        provenance={k:data[k] for k in ('source_archive_sha256','host_sha256','implementation_sha256','compiler_version','archiver_version','scope','cache_policy','frozen_inputs_verified_after','origin_sha256') if k in data}
        if 'compiler_version' not in provenance and 'preparation' in data:provenance['compiler_version']=next(iter(data['preparation'].values()))['context']['compiler_version']
        if 'fixed_sdk_tool_files' in data:provenance['fixed_sdk_tool_file_count']=len(data['fixed_sdk_tool_files']);provenance['fixed_sdk_tool_identity_sha256']=sha(json.dumps(data['fixed_sdk_tool_files'],sort_keys=True).encode())
        save(dest/'provenance.json',provenance)
        runid=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
        base=dest.relative_to(ROOT).as_posix();entries.append(dict(id=identifier,run_id=runid,status=status,report=base+'/REPORT.md',raw=base+'/results.json',summary=base+'/summary.json',validation=base+'/validation.json',provenance=base+'/provenance.json',raw_identity=base+'/raw-identity.json',implementation='experiments/compiler/followthrough/README.md',findings='research/compiler/followthrough/findings.md'))

    d=json.loads(a.ir.read_text());summary=dict(trials=d['trials'],object_checks=len(d['cases']),boundary_probes=len(d['boundaries']),sources={});table=[]
    for source,prep in d['preparation'].items():
        scenarios={}
        for scenario in ('unchanged','comment','unused-macro','unused-type','semantic'):
            values={mode:stats([r for r in d['cases'] if r['source']==source and r['scenario']==scenario and r['mode']==mode],'endpoint_seconds') for mode in ('native','ir','ccache')};scenarios[scenario]=values
            table.append('| '+source+' | '+scenario+' | '+' | '.join(f"{values[m]['median']*1000:.2f}" for m in ('native','ir','ccache'))+' |')
        summary['sources'][source]=dict(scenarios=scenarios,seed_seconds=prep['seed']['endpoint_seconds'],seed_ir_bytes=prep['seed']['ir_bytes'],shared_analysis={m:stats([r for r in prep['shared_analysis'] if r['mode']==m],'endpoint_seconds') for m in ('off','independent','serial','parallel')})
    report='''# One frontend for screening and fallback

The host now checks current pre-optimization IR and sends that same module to the backend on a miss. It avoids the previous prototype's second frontend. Equal exact IR permits object reuse only inside the fixed tool/SDK/options context measured here.

Three randomized blocks use private Zstandard 1.5.7 sources and one baseline-only object candidate per TU. Ccache is independently primed and restored to its baseline seed before every request; changed-result history hits are excluded. Each output is compared with an independent CLI object. Measurements are warm local Linux operations on one shared developer machine, with an advisory lock between measured research lanes; unrelated activity/preparation is not excluded.

| Translation unit | Edit | Native full compile, ms | Current IR, ms | Seeded ccache, ms |
| --- | --- | ---: | ---: | ---: |
'''+ '\n'.join(table)+'''

The heavy unused-typedef edit preserves emitted IR and objects while changing preprocessed input. IR reuse wins all three pairs against both full native compilation and seeded ccache. On a real emitted semantic change the backend still dominates; the host continues current IR without another parse. The small timing differences between the two full-compilation paths are not an established general gain. Exact unchanged inputs remain much cheaper through ccache's direct lookup, and ccache also wins the heavy comment comparison. A practical design should preserve a source/content fast path before deeper screening.

For the heavy semantic miss, stage medians are about 69 ms frontend, 7 ms IR printing/hash and 3.35 seconds backend. The heavy unused-type hit takes about 67 ms frontend, 6 ms screening and less than 1 ms object publication. Stage medians are independently aggregated and do not sum exactly to complete endpoint medians.

Validation covers 90 matched object requests, 24 additional shared-analysis compilation operations, two baseline seeds and seven code-generation/diagnostic boundary probes. Packing, target attributes, inline assembly and debug-line edits miss safely; a current source warning is emitted on an IR hit. Separate host regressions cover backend failure/recovery and a changed include's current depfile on a hit. Source/binary hashes are unchanged before/after the matrix.

The parsed-source analysis in this primary run compares separate sequential parses with shared serial/parallel execution. Use the [separate-worker parallel control](../analysis-parallel/REPORT.md) for the stronger wall-time comparison. This is a Clang-local compiler API experiment, not a portable AST/CST interchange specification. [Implementation, supported inputs and reproduction](../../README.md) document side-product and metadata limits.
'''
    publish(a.ir,'ir','CC-IR-CONTINUATION','measured-single-frontend-current-ir-reuse',summary,report)

    d=json.loads(a.analysis.read_text());summary=dict(trials=d['trials'],objects_checked=len(d['cases']),sources={});table=[]
    for source in sorted({r['source'] for r in d['cases']}):
        modes={}
        for mode in ('independent-serial','independent-parallel','shared-serial','shared-parallel'):
            rows=[r for r in d['cases'] if r['source']==source and r['mode']==mode];modes[mode]=dict(wall=stats(rows,'seconds'),cpu=stats(rows,'cpu_seconds'))
            table.append(f"| {source} | {mode} | {modes[mode]['wall']['median']*1000:.2f} | {modes[mode]['cpu']['median']*1000:.0f} |")
        summary['sources'][source]=modes
    report='''# Shared parsing versus separate parallel workers

One initialized Clang worker shares a frontend between code generation and a detached-name analysis. The stronger control uses two initialized workers: one parses for analysis while the other compiles, either sequentially or concurrently. The analysis hashes declaration names and counts a selected digest predicate; it is a deliberately small surrogate, not a production linter.

Three randomized blocks verify all 24 object outputs and analysis results. Time is the complete host-request operation; CPU is sampled for both child processes outside its clock using Linux process counters (10 ms tick granularity on the measured host).

| Translation unit | Arrangement | Median wall, ms | Sampled process CPU, ms |
| --- | --- | ---: | ---: |
'''+ '\n'.join(table)+'''

For the small TU, shared serial work and independent parallel work have nearly equal wall time. Sharing reduces sampled CPU from about 100 to 50 ms against the parallel control; merely moving the tiny detached analysis to another thread does not establish a latency win. Comparing only with independent sequential parsing would overstate the wall-time result. For the heavy TU, several seconds of backend work dominate the tens of milliseconds potentially saved by frontend sharing; three blocks do not establish a broad latency advantage.

Threads never concurrently traverse Clang's mutable/lazy AST. A consumer detaches immutable declaration-name records while the AST is alive, then independent analysis can overlap the backend. The result supports a narrow shared-facts boundary; arbitrary AST passes, compiler versions and language frontends are not interchangeable.

Both worker processes stay alive throughout this control, including an idle analysis worker in shared modes. Recorded RSS samples therefore do not establish a one-worker memory saving or peak/PSS bound. Host and relevant implementation identities are checked before/after. [Reproduction and limits](../../README.md).
'''
    publish(a.analysis,'analysis-parallel','CC-SHARED-ANALYSIS','measured-shared-parse-cpu-with-parallel-control',summary,report)

    d=json.loads(a.repro.read_text());summary=dict(probes=[dict(name=r['name'],correct=r['correct'],**({'equal':r['equal']} if 'equal' in r else {})) for r in d['cases']]);table=[]
    for row in summary['probes']:table.append('| '+row['name']+' | '+('Equal' if row.get('equal') else 'Different' if 'equal' in row else 'Order changes bytes; sorted order matches')+' |')
    report='''# Inputs beyond source bytes

Six small compiler/archive probes exercise concrete request-identity requirements. They are deterministic counterexamples and controls, not a production-project reproducibility survey.

| Perturbation | Object/archive comparison |
| --- | --- |
'''+ '\n'.join(table)+'''

Absolute source paths affect `__FILE__` and debug information; explicit file-prefix and debug-compilation-directory mappings restore equality in the tested pair. `CPATH` selects different header contents. `SOURCE_DATE_EPOCH` changes the tested expanded date/time strings. C and C.UTF-8 locales preserve the selected object's bytes here, which is not proof that every tool or diagnostic is locale independent. Reversing ordered archive inputs changes archive bytes; sorting the same inputs restores the reference archive.

The native source-provider tests separately expose `__TIMESTAMP__`: normalized in-memory mtimes differ from physical source metadata. Supported logical-graph commands reject date/time builtins with `-Werror=date-time`. A general source collection needs explicit metadata/environment/clock semantics or declared restrictions, not merely a source-content digest.

All six probes pass their expected equal/different assertions. The measured archive tool is GNU ar 2.47; an initial attempt using an unavailable llvm-ar path was retried with the installed archiver. [Reproduce](../../README.md).
'''
    publish(a.repro,'reproducibility','CC-REQUEST-IDENTITY','measured-path-environment-order-identity-probes',summary,report)

    if a.graph:
        d=json.loads(a.graph.read_text());summary=dict(compile_units=d['compile_units'],source_files=d['source_files'],source_bytes=d['source_bytes'],initial_ninja_ccache_seconds=d['initial_ninja_ccache_seconds'],initial_shared_seconds=d['initial_shared_seconds'],admission_seconds=d['admission_seconds'],cache_policy=d['cache_policy'],cases={});table=[]
        for scenario in ('noop','source','header','generated','configuration'):
            modes={m:stats([r for r in d['cases'] if r['scenario']==scenario and r['mode']==m],'seconds') for m in ('shared','ninja-ccache')};wins=sum(next(r['seconds'] for r in d['cases'] if r['block']==b and r['scenario']==scenario and r['mode']=='shared')<next(r['seconds'] for r in d['cases'] if r['block']==b and r['scenario']==scenario and r['mode']=='ninja-ccache') for b in range(3));summary['cases'][scenario]=dict(modes=modes,paired_wins=wins);table.append(f"| {scenario} | {modes['shared']['median']*1000:.2f} | {modes['ninja-ccache']['median']*1000:.2f} | {wins}/3 |")
        report='''# A production C++ graph from admitted source generations

The upstream Ninja 1.13.2 executable provides 33 production C++ translation units, one static archive, a generated Python browse header and a final link. Both controls use the same flags, paths, SDK and one compiler worker. The candidate retains one initialized Clang host and an authoritative in-memory source namespace; Ninja uses a baseline-only ccache seed restored outside every timed operation. Changed-result history hits are excluded.

**The scheduler is a controlled fixed-dependency edit trace.** It uses baseline depfiles and known generator rules; it does not refresh dependencies or retain negative include queries. Newly introduced includes and optional-header appearance are not soundly covered by this scheduler. The source-provider unit tests establish VFS lookup behavior, not general graph invalidation. This is not the previous stronger logical-condition checker integrated into a production graph.

Three randomized blocks measure complete edit/admission, known dirty-TU compilation and archive/link work. The header probe appends an emitted used static function; the source probe appends an emitted function. The generator changes the embedded browse script, and the configuration probe enables assertions through `-UNDEBUG`. These labelled probes exercise real production code while keeping the change scope explicit. Runtime/byte validation is outside the operation clock for both paths.

| Operation | Shared host, ms | Ninja + seeded ccache, ms | Shared paired wins |
| --- | ---: | ---: | ---: |
'''+ '\n'.join(table)+f'''

The source and generated-input cases win all three pairs in this trace. Header and configuration changes win two of three, with substantial spread: the shared configuration run ranges from about 23.3 to 30.3 seconds. Three blocks do not establish a reliable general configuration/cold-build advantage. The no-op comparison applies only to this admitted fixed-dependency contract; it is not full physical workspace validation.

Initial CLI/ccache building takes {d['initial_ninja_ccache_seconds']:.2f} s; the subsequent host full build takes {d['initial_shared_seconds']:.2f} s. These run sequentially and are preparation observations, not a randomized cold-build speed comparison. Source admission separately costs {d['admission_seconds']*1000:.2f} ms for {d['source_files']} files / {d['source_bytes']:,} UTF-8 bytes. The complete initial host/tool/SDK acquisition cost is not represented by that admission number.

All 33 initial objects and the executable match the independent CLI. Each of the 30 measured operations verifies every object's identity and runs the built executable's version query. One additional editor interaction inspects an admitted unsaved generation, compiles its bytes, matches a physical CLI oracle, and rejects stale compile/update generations. This is a narrow input-sharing proof, not a complete editor diagnostics loop or multi-client completion-publication protocol.

The source-root filesystem has no fallback to physical source files. An initial integration attempt correctly failed when a third-party `.hpp` was omitted; the final adapter imports actual baseline project dependencies rather than trusting filename suffixes. Fixed baseline positive SDK dependencies and tool linkage are hashed before/after, while actual SDK reads remain physical. Source mtimes are normalized; `-Werror=date-time` rejects time-sensitive builtins. Immutable source generations do not establish a complete POSIX replacement.

The advisory measurement lock excludes other measured research lanes, not unrelated activity. Results establish this bounded single-worker trace; broader parallel scheduling, dynamic dependency discovery, negative conditions, cancellation, long-lived memory bounds and a larger target graph remain open. [Implementation and reproduction](../../README.md).
'''
        publish(a.graph,'graph','CC-NINJA-SOURCE-GENERATIONS','measured-fixed-dependency-production-cpp-trace',summary,report)

    save(ROOT/'research/compiler/followthrough/experiments.json',dict(schema_version=1,path_base='repository-root',track='native-shared-work-followthrough',experiments=entries))
    save(a.evidence_output,dict(artifacts=evidence))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('ir','analysis','repro','evidence-output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--graph',type=Path);main(p.parse_args())

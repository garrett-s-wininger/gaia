// Fixed-size Odin worker set draining a bounded, admitted job table.
package main
import "core:c"
import "core:crypto/sha2"
import "core:fmt"
import "core:os"
import "core:strconv"
import "core:strings"
import "core:sync"
import "core:thread"
import "core:time"
import "core:sys/posix"

Stats :: struct {
    compiled, errors, warnings, setup_ns, link_ns, input_files, input_bytes: u64,
    job_count, peak_active, link_calls, link_result, can_run_again: u64,
}
foreign import shim "system:c"
foreign shim {
    gaia_shared_cache_reset :: proc(keep: cstring) -> c.int ---
    gaia_shared_cache_prime :: proc(data: [^]u8,size:c.size_t,pin:cstring) -> c.int ---
    gaia_shared_input_stat :: proc(handle:rawptr,field:c.int) -> u64 ---
    gaia_blake3_backend :: proc(enabled: c.int) ---
    gaia_sha256_backend :: proc(accelerated: c.int) -> c.int ---
    gaia_pool_open :: proc(memory: c.int, clang, output: cstring, data: [^]u8, size: c.size_t,
        pin: cstring, plan: [^]u8, plan_size: c.size_t, linker: cstring, link: [^]u8, link_size: c.size_t) -> rawptr ---
    gaia_pool_count :: proc(handle: rawptr) -> c.int ---
    gaia_worker_open :: proc(handle: rawptr) -> rawptr ---
    gaia_worker_compile :: proc(worker: rawptr, index: c.int) -> c.int ---
    gaia_worker_close :: proc(worker: rawptr) ---
    gaia_pool_link :: proc(handle: rawptr, invalid: c.int) -> c.int ---
    gaia_pool_stats :: proc(handle: rawptr, stats: ^Stats) ---
    gaia_pool_messages :: proc(handle: rawptr) -> cstring ---
    gaia_pool_job_time :: proc(handle: rawptr, index, end: c.int) -> u64 ---
    gaia_handoff_mode :: proc(handle: rawptr, mode: c.int) ---
    gaia_handoff_stat :: proc(handle: rawptr, field, index: c.int) -> u64 ---
    gaia_handoff_digest :: proc(handle: rawptr, index: c.int, out: [^]u8) ---
    gaia_handoff_export :: proc(handle: rawptr) -> c.int ---
    gaia_cache_worker_open :: proc(handle: rawptr) -> rawptr ---
    gaia_cache_compile :: proc(worker: rawptr, index: c.int, masks: [^]u64, count: c.size_t, cwd: cstring) -> c.int ---
    gaia_cache_import :: proc(handle: rawptr, index: c.int, data: [^]u8, size: c.size_t) -> c.int ---
    gaia_cache_object :: proc(handle: rawptr, index: c.int, size: ^c.size_t) -> [^]u8 ---
    gaia_dep_open :: proc(handle: rawptr, masks: [^]u64, count: c.size_t, cwd: cstring, enabled: c.int) -> rawptr ---
    gaia_dep_journal :: proc(handle: rawptr, index: c.int, size: ^c.size_t) -> [^]u8 ---
    gaia_dep_validate :: proc(handle: rawptr, index: c.int, data: [^]u8, size: c.size_t) -> c.int ---
    gaia_dep_stat :: proc(handle: rawptr, field: c.int) -> u64 ---
    gaia_dep_close :: proc(handle: rawptr) ---
    gaia_pool_close :: proc(handle: rawptr) ---
}
Mapping :: struct {fd: posix.FD, data: []u8}
map_file :: proc(path: cstring, limit: i64) -> Mapping {
    fd:=posix.open(path,{.CLOEXEC});if fd<0 {os.exit(3)}
    info: posix.stat_t
    if posix.fstat(fd,&info)!=nil || info.st_size<16 || i64(info.st_size)>limit {os.exit(3)}
    ptr:=posix.mmap(nil,c.size_t(info.st_size),{.READ},{.PRIVATE},fd,0)
    if ptr==posix.MAP_FAILED {os.exit(3)}
    return Mapping{fd,([^]u8)(ptr)[:int(info.st_size)]}
}
unmap :: proc(m: Mapping) {if len(m.data)>0 {posix.munmap(raw_data(m.data),c.size_t(len(m.data)));posix.close(m.fd)}}
Pool :: struct {handle: rawptr, next_job, failed, count, executions: i32, hits: [64]bool, masks: []u64, cwd: cstring}
worker_main :: proc(t: ^thread.Thread) {
    p:=cast(^Pool)t.data;worker: rawptr
    defer {if worker!=nil {gaia_worker_close(worker)}}
    for sync.atomic_load(&p.failed)==0 {
        job:=sync.atomic_add(&p.next_job,1)
        if job>=p.count {break}
        if p.hits[job] {continue}
        if worker==nil {worker=gaia_cache_worker_open(p.handle)}
        if worker==nil {sync.atomic_store(&p.failed,1);break}
        sync.atomic_add(&p.executions,1)
        if gaia_cache_compile(worker,c.int(job),raw_data(p.masks),c.size_t(len(p.masks)),p.cwd)!=0 {sync.atomic_store(&p.failed,1);break}
    }
}
peak_rss :: proc() -> u64 {
    data,err:=os.read_entire_file("/proc/self/status",context.allocator);if err!=nil {return 0};defer delete(data)
    lines:=strings.split_lines(string(data));defer delete(lines)
    for line in lines {
        if strings.has_prefix(line,"VmHWM:") {
            fields:=strings.fields(line);defer delete(fields)
            n,okay:=strconv.parse_int(fields[1]);if okay {return u64(n)*1024}
        }
    }
    return 0
}
request :: proc(args: []string) {
    if len(args)==3 && args[1]=="shared-reset" {
        keep:=strings.clone_to_cstring(args[2]);defer delete(keep)
        status:=gaia_shared_cache_reset(keep)
        fmt.print("{");fmt.printf("\"correct\":%s,\"peak_rss_bytes\":%d}\n",("true" if status==0 else "false"),peak_rss());return
    }
    if len(args)==5 && args[1]=="shared-prime" {
        gaia_sha256_backend(1);gaia_blake3_backend(1)
        keep:=strings.clone_to_cstring(args[4]);defer delete(keep)
        if gaia_shared_cache_reset(keep)!=0 {os.exit(3)}
        path:=strings.clone_to_cstring(args[2]);defer delete(path)
        input:=map_file(path,4*1024*1024);defer unmap(input)
        pin:=strings.clone_to_cstring(args[3]);defer delete(pin)
        status:=gaia_shared_cache_prime(raw_data(input.data),c.size_t(len(input.data)),pin)
        fmt.print("{");fmt.printf("\"correct\":%s,\"peak_rss_bytes\":%d}\n",("true" if status==0 else "false"),peak_rss());return
    }
    if len(args)!=17 {fmt.eprintln("host memory|physical CLANG ROOT BUNDLE PIN OUT PLAN WORKERS internal|external|retry LINKER LINKPLAN direct off|whole|scoped|journal CACHE VIEWS CONTEXT-ID");os.exit(2)}
    mode:=args[1];if mode!="memory" {os.exit(2)}
    count,ok:=strconv.parse_int(args[8]);if !ok || count<1 || count>16 {os.exit(2)}
    link_mode:=args[9];if link_mode!="internal" && link_mode!="external" && link_mode!="retry" {os.exit(2)}
    handoff:=args[12];handoff_id: c.int
    switch handoff {case "file": handoff_id=0;case "buffer-file": handoff_id=1;case "direct", "direct-export": handoff_id=2;case: os.exit(2)}
    if handoff_id==2 && link_mode=="external" {os.exit(2)}
    if handoff!="direct" || link_mode!="internal" {os.exit(2)}
    cache_mode:=args[13];blake3:=cache_mode=="journal-history-blake3";fast_hash:=cache_mode=="journal-history-fast-hash" || blake3;memo:=cache_mode=="journal-history-memo" || fast_hash;shared:=cache_mode=="journal-history-shared" || memo;history:=cache_mode=="journal-history" || shared
    if cache_mode!="off" && cache_mode!="whole" && cache_mode!="scoped" && cache_mode!="journal" && !history {os.exit(2)}
    if gaia_sha256_backend(c.int(fast_hash))!=0 {fmt.eprintln("requested SHA-256 provider unavailable");os.exit(2)}
    gaia_blake3_backend(c.int(blake3))
    journal_mode:=cache_mode=="journal" || history
    paths:=[]string{args[2],args[6],args[5],args[4],args[7],args[10],args[11]}
    names: [7]cstring;for path,i in paths {names[i]=strings.clone_to_cstring(path)}
    defer {for name in names {delete(name)}}
    start:=time.tick_now();input: Mapping
    plan:=map_file(names[4],4*1024*1024);defer unmap(plan)
    link:=map_file(names[6],4*1024*1024);defer unmap(link)
    if mode=="memory" {input=map_file(names[3],64*1024*1024)}
    defer unmap(input)
    handle:=gaia_pool_open(c.int(mode=="memory"),names[0],names[1],raw_data(input.data),c.size_t(len(input.data)),
        names[2],raw_data(plan.data),c.size_t(len(plan.data)),names[5],raw_data(link.data),c.size_t(len(link.data)))
    if handle==nil {fmt.eprintln("input/request admission failed");os.exit(3)}
    opened:=time.tick_now()
    defer gaia_pool_close(handle)
    gaia_handoff_mode(handle,handoff_id)
    p:=Pool{handle=handle,count=i32(gaia_pool_count(handle))}
    if p.count<1 || p.count>64 {os.exit(3)}
    p.cwd=strings.clone_to_cstring(args[3]);defer delete(p.cwd)
    admission:=cache_admit(input.data,plan.data,args[15],int(p.count),args[3],args[16],"journal" if history else cache_mode,blake3)
    admitted:=time.tick_now()
    defer {delete(admission.masks);delete(admission.keys)}
    p.masks=admission.masks;hits,corrupt,writes,write_errors,historical_hits: int
    dep:=gaia_dep_open(handle,raw_data(p.masks),c.size_t(len(p.masks)),p.cwd,(3 if memo else 2 if shared else c.int(journal_mode)))
    if dep==nil {os.exit(3)};defer gaia_dep_close(dep)
    hashed:=time.tick_now()
    if cache_mode!="off" {
        for key,i in admission.keys {
            found,bad: bool
            if journal_mode {
                for slot in 0..<(3 if history else 1) {
                    h,b:=dependency_load(handle,i,key,args[14],slot)
                    bad=bad || b
                    if h {found=true;if slot>0 {historical_hits+=1};break}
                }
            }
            else {found,bad=cache_load(handle,i,key,args[14])}
            if found {p.hits[i]=true;hits+=1}
            if bad {corrupt+=1}
        }
    }
    threads:=make([]^thread.Thread,min(count,int(p.count)-hits));defer delete(threads)
    ready:=time.tick_now()
    for &t in threads {t=thread.create(worker_main);t.data=&p;thread.start(t)}
    for t in threads {thread.join(t);thread.destroy(t)}
    compiled:=time.tick_now();status:=int(sync.atomic_load(&p.failed));retry_result: c.int
    if status==0 && link_mode!="external" {
        if link_mode=="retry" {retry_result=gaia_pool_link(handle,1);if retry_result==0 {status=9}}
        if status==0 {status=int(gaia_pool_link(handle,0))}
    }
    finished:=time.tick_now();s: Stats;gaia_pool_stats(handle,&s)
    if status==0 && handoff=="direct-export" {status=int(gaia_handoff_export(handle))}
    messages:=gaia_pool_messages(handle)
    // Cache only diagnostic-free results. Re-executing warning/remark-producing
    // requests preserves their messages without a diagnostic replay format.
    if status==0 && len(string(messages))==0 && cache_mode!="off" {
        for key,i in admission.keys {if !p.hits[i] {
            okay: bool
            if journal_mode {okay=dependency_store(handle,i,key,args[14],history)}
            else {okay=cache_store(handle,i,key,args[14])}
            if okay {writes+=1} else {write_errors+=1}
        }}
    }
    published:=time.tick_now()
    if len(string(messages))>0 {fmt.eprint(string(messages))}
    fmt.print("{")
    if string(input.data[:8])=="GAIACIN4" {
        fmt.printf("\"shared_segment_hits\":%d,\"shared_new_segments\":%d,\"shared_new_segment_bytes\":%d,\"shared_cache_bytes\":%d,\"shared_cache_segments\":%d,\"shared_cached_file_digests\":%d,\"shared_manifest_bytes\":%d,",gaia_shared_input_stat(handle,0),gaia_shared_input_stat(handle,1),gaia_shared_input_stat(handle,2),gaia_shared_input_stat(handle,3),gaia_shared_input_stat(handle,4),gaia_shared_input_stat(handle,5),gaia_shared_input_stat(handle,6))
    }
    fmt.printf("\"input_admission_ns\":%d,\"action_admission_ns\":%d,\"content_hash_ns\":%d,\"candidate_load_ns\":%d,",time.duration_nanoseconds(time.tick_diff(start,opened)),time.duration_nanoseconds(time.tick_diff(opened,admitted)),time.duration_nanoseconds(time.tick_diff(admitted,hashed)),time.duration_nanoseconds(time.tick_diff(hashed,ready)))
    fmt.printf("\"correct\":%v,\"workers\":%d,\"compiled\":%d,\"errors\":%d,\"warnings\":%d,"+
        "\"job_count\":%d,\"peak_active\":%d,\"link_calls\":%d,\"link_result\":%d,\"can_run_again\":%v,"+
        "\"retry_result\":%d,\"setup_ns\":%d,\"compile_wall_ns\":%d,\"link_ns\":%d,\"workload_ns\":%d,\"peak_rss_bytes\":%d,\"jobs\":[",
        status==0,count,s.compiled-u64(hits),s.errors,s.warnings,s.job_count,s.peak_active,s.link_calls,s.link_result,s.can_run_again!=0,
        retry_result,time.duration_nanoseconds(time.tick_diff(start,ready)),time.duration_nanoseconds(time.tick_diff(ready,compiled)),
        s.link_ns,time.duration_nanoseconds(time.tick_diff(start,finished)),peak_rss())
    for i in 0..<int(s.job_count) {
        if i>0 {fmt.print(",")}
        fmt.printf("[%d,%d]",gaia_pool_job_time(handle,c.int(i),0),gaia_pool_job_time(handle,c.int(i),1))
    }
    fmt.print("],")
    fmt.printf("\"buffer_hits\":%d,\"buffer_bytes\":%d,\"buffer_misses\":%d,\"object_sizes\":[",gaia_handoff_stat(handle,2,0),gaia_handoff_stat(handle,3,0),gaia_handoff_stat(handle,4,0))
    for i in 0..<int(s.job_count) {if i>0 {fmt.print(",")};fmt.print(gaia_handoff_stat(handle,0,c.int(i)))}
    fmt.print("],\"export_ns\":[")
    for i in 0..<int(s.job_count) {if i>0 {fmt.print(",")};fmt.print(gaia_handoff_stat(handle,1,c.int(i)))}
    fmt.print("],\"object_sha256\":[")
    if handoff_id!=0 {
        for i in 0..<int(s.job_count) {
            if i>0 {fmt.print(",")};digest: [65]u8
            gaia_handoff_digest(handle,c.int(i),raw_data(digest[:]))
            fmt.printf("\"%s\"",string(cstring(raw_data(digest[:]))))
        }
    }
    fmt.print("],")
    fmt.printf("\"historical_hits\":%d,",historical_hits)
    fmt.printf("\"cache_hits\":%d,\"cache_corrupt\":%d,\"cache_writes\":%d,\"cache_write_errors\":%d,\"compiler_executions\":%d,\"ready_objects\":%d,\"cache_keys\":[",hits,corrupt,writes,write_errors,sync.atomic_load(&p.executions),s.compiled)
    if cache_mode!="off" {for key,i in admission.keys {if i>0 {fmt.print(",")};hex:=hex_digest(key);fmt.printf("\"%s\"",hex);delete(hex)}}
    fmt.print("],")
    fmt.print("\"journal_sha256\":[")
    if journal_mode {
        for i in 0..<int(p.count) {
            if i>0 {fmt.print(",")};size: c.size_t
            ptr:=gaia_dep_journal(handle,c.int(i),&size)
            if size==0 {fmt.print("null")} else {
                digest:=hash_bytes(ptr[:int(size)]);text:=hex_digest(digest)
                fmt.printf("\"%s\"",text);delete(text)
            }
        }
    }
    fmt.print("],")
    reported:=time.tick_now()
    fmt.printf("\"publication_ns\":%d,\"report_ns\":%d,",time.duration_nanoseconds(time.tick_diff(finished,published)),time.duration_nanoseconds(time.tick_diff(published,reported)))
    fmt.printf("\"memo_hits\":%d,\"validation_ns\":%d,\"memo_bytes\":%d,",gaia_dep_stat(dep,6),gaia_dep_stat(dep,7),gaia_dep_stat(dep,8))
    fmt.printf("\"view_builds\":%d,\"view_build_ns\":%d,\"validation_groups\":%d,",gaia_dep_stat(dep,3),gaia_dep_stat(dep,4),gaia_dep_stat(dep,5))
    fmt.printf("\"dependency_queries\":%d,\"dependency_negatives\":%d,\"dependency_invalidations\":%d}\n",gaia_dep_stat(dep,0),gaia_dep_stat(dep,1),gaia_dep_stat(dep,2))
    if status!=0 {os.exit(status)}
}

// Experimental local transport: one length-framed argv request at a time.
// Request defers finish before accepting the next frame. Errors end the worker.
read_exact :: proc(data: []u8, eof_ok: bool=false) -> bool {
    offset:=0
    for offset<len(data) {
        remaining:=len(data)-offset
        n:=posix.read(0,raw_data(data[offset:]),c.size_t(remaining))
        if n==0 && offset==0 && eof_ok {return false}
        if n<=0 {os.exit(3)};offset+=int(n)
    }
    return true
}
main :: proc() {
    if len(os.args)!=2 || os.args[1]!="--serve" {request(os.args);return}
    for {
        header: [8]u8;if !read_exact(header[:],true) {break}
        size:=read_integer(header[:],0,8);if size<4 || size>4*1024*1024 {os.exit(3)}
        body:=make([]u8,int(size));read_exact(body)
        count:=int(read_integer(body,0,4));if count!=17 && count!=3 && count!=5 {os.exit(3)}
        args:=make([]string,count);offset:=4
        for &arg in args {
            n:=int(read_integer(body,offset,4));offset+=4
            if n>65536 || offset>len(body)-n {os.exit(3)}
            arg=string(body[offset:offset+n]);if strings.contains(arg,"\x00") {os.exit(3)};offset+=n
        }
        if offset!=len(body) {os.exit(3)}
        // The standalone launcher runs in the output directory. Re-enter that
        // directory each request: the caller may have replaced its inode.
        if count==17 {
            cwd:=strings.clone_to_cstring(args[6])
            if posix.chdir(cwd)!=nil {os.exit(3)};delete(cwd)
        } else if !((count==3 && args[1]=="shared-reset") || (count==5 && args[1]=="shared-prime")) {os.exit(3)}
        request(args);delete(args);delete(body)
        // Acknowledgement follows request defers, including pool/VFS teardown.
        fmt.println("GAIA-DONE")
    }
}

Digest :: [32]u8
hash_bytes :: proc(data: []u8) -> Digest {
    h: sha2.Context_256;sha2.init_256(&h);sha2.update(&h,data);out: Digest;sha2.final(&h,out[:]);return out
}
hash_u64 :: proc(h: ^sha2.Context_256,n: u64) {
    b: [8]u8;for i in 0..<8 {b[i]=u8(n>>u64(i*8))};sha2.update(h,b[:])
}
hash_string :: proc(h: ^sha2.Context_256,s: string) {hash_u64(h,u64(len(s)));sha2.update(h,transmute([]u8)s)}
read_integer :: proc(data: []u8,offset,n: int) -> u64 {
    if offset<0 || n<0 || n>8 || offset>len(data)-n {fmt.eprintln("invalid cache input framing");os.exit(3)}
    out: u64;for i in 0..<n {out|=u64(data[offset+i])<<u64(8*i)};return out
}
hex_digest :: proc(digest: Digest) -> string {
    out:=make([]u8,64);chars:="0123456789abcdef"
    for b,i in digest {out[2*i]=chars[b>>4];out[2*i+1]=chars[b&15]};return string(out)
}
Admission :: struct {masks: []u64, keys: []Digest}
cache_admit :: proc(blob,plan: []u8,mask_path: string,count: int,cwd,context_id,mode: string,blake3: bool=false) -> Admission {
    if len(context_id)!=64 {fmt.eprintln("expected execution-context SHA-256");os.exit(3)}
    for b in transmute([]u8)context_id {if !(b>='0' && b<='9') && !(b>='a' && b<='f') {os.exit(3)}}
    n:=int(read_integer(blob,8,8));if n<1 || n>100000 {os.exit(3)}
    mf,err:=os.open(mask_path);if err!=nil {os.exit(3)}
    msize,e:=os.file_size(mf);if e!=nil || msize>4*1024*1024 {os.close(mf);os.exit(3)}
    body,me:=os.read_entire_file(mf,context.allocator);os.close(mf);if me!=nil {os.exit(3)};defer delete(body)
    fields:=strings.fields(string(body));defer delete(fields)
    if len(fields)!=n+1 || fields[0]!="GAIACV1" {fmt.eprintln("invalid compiler input views");os.exit(3)}
    a:=Admission{masks=make([]u64,n),keys=make([]Digest,count)}
    all_bits:=~u64(0);if count<64 {all_bits=(u64(1)<<u64(count))-1}
    for i in 0..<n {v,ok:=strconv.parse_uint(fields[i+1],10);if !ok || (u64(v)&~all_bits)!=0 {os.exit(3)};a.masks[i]=u64(v)}
    leaves:=make([]Digest,n);defer delete(leaves);offset:=16
    shared_input:=string(blob[:8])=="GAIACIN4"
    if shared_input && (mode!="journal" || !blake3) {os.exit(3)}
    if !shared_input {
    // The compiler has already authenticated/validated the immutable collection.
    // Per-file hashes form framed Merkle leaves; scoped roots hash only metadata.
    for i in 0..<n {
        name_len:=int(read_integer(blob,offset,4));size:=int(read_integer(blob,offset+4,8));offset+=12
        name:=string(blob[offset:offset+name_len]);offset+=name_len+1
        if mode!="off" && mode!="journal" {
            payload:=hash_bytes(blob[offset:offset+size]);h: sha2.Context_256;sha2.init_256(&h)
            hash_string(&h,"GAIA-INPUT-LEAF-1");hash_string(&h,name);hash_u64(&h,u64(size));sha2.update(&h,payload[:]);sha2.final(&h,leaves[i][:])
        }
        offset+=size+1
    }
    if offset!=len(blob) {os.exit(3)}
    }
    full: Digest
    if mode!="off" && mode!="journal" {
        h: sha2.Context_256;sha2.init_256(&h);hash_string(&h,"GAIA-FULL-INPUT-1");hash_u64(&h,u64(n))
        for &leaf in leaves {sha2.update(&h,leaf[:])};sha2.final(&h,full[:])
    }
    // Bind each key to exact framed argv, visible namespace, logical cwd and
    // caller-admitted immutable toolchain/execution-context identity.
    offset=16
    for job in 0..<count {
        begin:=offset;argc:=int(read_integer(plan,offset,4));offset+=4;date_guard:=false
        for _ in 0..<argc {
            size:=int(read_integer(plan,offset,4));offset+=4;arg:=string(plan[offset:offset+size]);offset+=size
            if arg=="-Werror=date-time" {date_guard=true}
            if strings.has_prefix(arg,"@") {fmt.eprintln("response files are outside this cache fixture contract");os.exit(3)}
        }
        if !date_guard {fmt.eprintln("cache fixture requires date-time macro guard");os.exit(3)}
        if mode=="off" {continue}
        if mode=="journal" {
            h: sha2.Context_256;sha2.init_256(&h);hash_string(&h,"GAIA-DEPENDENCY-ACTION-BLAKE3-1" if blake3 else "GAIA-DEPENDENCY-ACTION-1")
            hash_string(&h,cwd);hash_string(&h,context_id);hash_u64(&h,u64(offset-begin));sha2.update(&h,plan[begin:offset])
            sha2.final(&h,a.keys[job][:]);continue
        }
        view: sha2.Context_256;sha2.init_256(&view);hash_string(&view,"GAIA-VISIBLE-INPUTS-1")
        selected: u64;for mask in a.masks {if mask&(u64(1)<<u64(job))!=0 {selected+=1}}
        hash_u64(&view,selected)
        for mask,i in a.masks {if mask&(u64(1)<<u64(job))!=0 {sha2.update(&view,leaves[i][:])}}
        root: Digest;sha2.final(&view,root[:]);h: sha2.Context_256;sha2.init_256(&h)
        hash_string(&h,"GAIA-OBJECT-CACHE-1");hash_string(&h,mode);hash_string(&h,cwd);hash_string(&h,context_id)
        hash_u64(&h,u64(offset-begin));sha2.update(&h,plan[begin:offset]);sha2.update(&h,root[:])
        if mode=="whole" {sha2.update(&h,full[:])};sha2.final(&h,a.keys[job][:])
    }
    if offset!=len(plan) {os.exit(3)}
    return a
}
cache_path :: proc(root: string,key: Digest) -> string {
    hex:=hex_digest(key);defer delete(hex);return fmt.aprintf("%s/%s.gco",root,hex)
}
cache_load :: proc(handle: rawptr,index: int,key: Digest,root: string) -> (hit,corrupt: bool) {
    path:=cache_path(root,key);defer delete(path);file,err:=os.open(path)
    if err!=nil {return false,false};defer os.close(file)
    size,e:=os.file_size(file);if e!=nil || size<81 || size>64*1024*1024+80 {return false,true}
    data,re:=os.read_entire_file(file,context.allocator);if re!=nil {return false,true};defer delete(data)
    if len(data)<81 || string(data[:8])!="GAIACO01" || read_integer(data,72,8)!=u64(len(data)-80) {return false,true}
    stored: Digest;copy(stored[:],data[8:40]);if stored!=key {return false,true}
    copy(stored[:],data[40:72]);if hash_bytes(data[80:])!=stored {return false,true}
    if gaia_cache_import(handle,c.int(index),raw_data(data[80:]),c.size_t(len(data)-80))!=0 {return false,true}
    return true,false
}
cache_store :: proc(handle: rawptr,index: int,key: Digest,root: string) -> bool {
    size: c.size_t;ptr:=gaia_cache_object(handle,c.int(index),&size)
    if size==0 || size>64*1024*1024 {return false}
    data:=make([]u8,80+int(size));defer delete(data);copy(data[:8],"GAIACO01");entry_key:=key;copy(data[8:40],entry_key[:])
    payload:=ptr[:int(size)];sum:=hash_bytes(payload);copy(data[40:72],sum[:])
    for i in 0..<8 {data[72+i]=u8(u64(size)>>u64(i*8))};copy(data[80:],payload)
    path:=cache_path(root,key);defer delete(path);tmp:=fmt.aprintf("%s.tmp.%d",path,posix.getpid());defer delete(tmp)
    file,err:=os.open(tmp,{.Write,.Create,.Excl},{.Read_User,.Write_User});if err!=nil {return false}
    okay:=true;offset:=0
    for offset<len(data) {n,e:=os.write(file,data[offset:]);if e!=nil || n<=0 {okay=false;break};offset+=n}
    if os.close(file)!=nil {okay=false}
    if okay {okay=os.rename(tmp,path)==nil}
    if !okay {os.remove(tmp)}
    return okay
}

// One atomic record binds the candidate action, journal and object together.
// The filename is a candidate index, not a claim that argv alone identifies output.
dependency_path :: proc(root: string,key: Digest,slot: int) -> string {
    hex:=hex_digest(key);defer delete(hex)
    if slot==0 {return fmt.aprintf("%s/%s.gdo",root,hex)}
    return fmt.aprintf("%s/%s.%d.gdo",root,hex,slot)
}
dependency_load :: proc(handle: rawptr,index: int,key: Digest,root: string,slot: int=0) -> (hit,corrupt: bool) {
    path:=dependency_path(root,key,slot);defer delete(path)
    file,err:=os.open(path);if err!=nil {return false,false};defer os.close(file)
    size,e:=os.file_size(file);if e!=nil || size<101 || size>80*1024*1024+88 {return false,true}
    data,re:=os.read_entire_file(file,context.allocator);if re!=nil {return false,true};defer delete(data)
    if len(data)<101 || string(data[:8])!="GAIADC01" {return false,true}
    stored: Digest;copy(stored[:],data[8:40]);if stored!=key {return false,true}
    journal:=read_integer(data,72,8);object:=read_integer(data,80,8)
    if journal<12 || journal>16*1024*1024 || object==0 || object>64*1024*1024 || journal+object!=u64(len(data)-88) {return false,true}
    h: sha2.Context_256;sha2.init_256(&h);sha2.update(&h,data[8:40]);sha2.update(&h,data[72:]);sum: Digest;sha2.final(&h,sum[:])
    copy(stored[:],data[40:72]);if sum!=stored {return false,true}
    valid:=gaia_dep_validate(handle,c.int(index),raw_data(data[88:]),c.size_t(journal))
    if valid<0 {return false,true};if valid==0 {return false,false}
    if gaia_cache_import(handle,c.int(index),raw_data(data[88+int(journal):]),c.size_t(object))!=0 {return false,true}
    return true,false
}
dependency_store :: proc(handle: rawptr,index: int,key: Digest,root: string,history: bool=false) -> bool {
    js,bs: c.size_t;journal:=gaia_dep_journal(handle,c.int(index),&js);object:=gaia_cache_object(handle,c.int(index),&bs)
    if js<12 || js>16*1024*1024 || bs==0 || bs>64*1024*1024 {return false}
    data:=make([]u8,88+int(js)+int(bs));defer delete(data);copy(data[:8],"GAIADC01");k:=key;copy(data[8:40],k[:])
    for i in 0..<8 {data[72+i]=u8(u64(js)>>u64(i*8));data[80+i]=u8(u64(bs)>>u64(i*8))}
    copy(data[88:88+int(js)],journal[:int(js)]);copy(data[88+int(js):],object[:int(bs)])
    h: sha2.Context_256;sha2.init_256(&h);sha2.update(&h,data[8:40]);sha2.update(&h,data[72:]);sum: Digest;sha2.final(&h,sum[:]);copy(data[40:72],sum[:])
    hex:=hex_digest(key);defer delete(hex);path:=fmt.aprintf("%s/%s.gdo",root,hex);defer delete(path)
    tmp:=fmt.aprintf("%s.tmp.%d",path,posix.getpid());defer delete(tmp)
    file,err:=os.open(tmp,{.Write,.Create,.Excl},{.Read_User,.Write_User});if err!=nil {return false}
    okay:=true;offset:=0
    for offset<len(data) {n,e:=os.write(file,data[offset:]);if e!=nil || n<=0 {okay=false;break};offset+=n}
    if os.close(file)!=nil {okay=false}
    if okay && history {
        // Rotation may lose cache candidates under concurrent writers; each
        // candidate is still an atomically published, self-validating record.
        // A crash/missing slot is a miss, never permission to trust stale bytes.
        for slot:=2;slot>=1;slot-=1 {
            old:=dependency_path(root,key,slot-1);next:=dependency_path(root,key,slot)
            os.rename(old,next);delete(old);delete(next)
        }
    }
    if okay {okay=os.rename(tmp,path)==nil};if !okay {os.remove(tmp)};return okay
}

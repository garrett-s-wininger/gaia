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
main :: proc() {
    if len(os.args)!=17 {fmt.eprintln("host memory|physical CLANG ROOT BUNDLE PIN OUT PLAN WORKERS internal|external|retry LINKER LINKPLAN direct off|whole|scoped CACHE VIEWS CONTEXT-ID");os.exit(2)}
    mode:=os.args[1];if mode!="memory" {os.exit(2)}
    count,ok:=strconv.parse_int(os.args[8]);if !ok || count<1 || count>16 {os.exit(2)}
    link_mode:=os.args[9];if link_mode!="internal" && link_mode!="external" && link_mode!="retry" {os.exit(2)}
    handoff:=os.args[12];handoff_id: c.int
    switch handoff {case "file": handoff_id=0;case "buffer-file": handoff_id=1;case "direct", "direct-export": handoff_id=2;case: os.exit(2)}
    if handoff_id==2 && link_mode=="external" {os.exit(2)}
    if handoff!="direct" || link_mode!="internal" {os.exit(2)}
    cache_mode:=os.args[13];if cache_mode!="off" && cache_mode!="whole" && cache_mode!="scoped" {os.exit(2)}
    paths:=[]string{os.args[2],os.args[6],os.args[5],os.args[4],os.args[7],os.args[10],os.args[11]}
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
    defer gaia_pool_close(handle)
    gaia_handoff_mode(handle,handoff_id)
    p:=Pool{handle=handle,count=i32(gaia_pool_count(handle))}
    if p.count<1 || p.count>64 {os.exit(3)}
    p.cwd=strings.clone_to_cstring(os.args[3]);defer delete(p.cwd)
    admission:=cache_admit(input.data,plan.data,os.args[15],int(p.count),os.args[3],os.args[16],cache_mode)
    defer {delete(admission.masks);delete(admission.keys)}
    p.masks=admission.masks;hits,corrupt,writes,write_errors: int
    if cache_mode!="off" {
        for key,i in admission.keys {
            found,bad:=cache_load(handle,i,key,os.args[14])
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
        for key,i in admission.keys {if !p.hits[i] {if cache_store(handle,i,key,os.args[14]) {writes+=1} else {write_errors+=1}}}
    }
    if len(string(messages))>0 {fmt.eprint(string(messages))}
    fmt.print("{")
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
    fmt.printf("\"cache_hits\":%d,\"cache_corrupt\":%d,\"cache_writes\":%d,\"cache_write_errors\":%d,\"compiler_executions\":%d,\"ready_objects\":%d,\"cache_keys\":[",hits,corrupt,writes,write_errors,sync.atomic_load(&p.executions),s.compiled)
    if cache_mode!="off" {for key,i in admission.keys {if i>0 {fmt.print(",")};hex:=hex_digest(key);fmt.printf("\"%s\"",hex);delete(hex)}}
    fmt.println("]}")
    if status!=0 {os.exit(status)}
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
cache_admit :: proc(blob,plan: []u8,mask_path: string,count: int,cwd,context_id,mode: string) -> Admission {
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
    // The compiler has already authenticated/validated the immutable collection.
    // Per-file hashes form framed Merkle leaves; scoped roots hash only metadata.
    leaves:=make([]Digest,n);defer delete(leaves);offset:=16
    for i in 0..<n {
        name_len:=int(read_integer(blob,offset,4));size:=int(read_integer(blob,offset+4,8));offset+=12
        name:=string(blob[offset:offset+name_len]);offset+=name_len+1
        if mode!="off" {
            payload:=hash_bytes(blob[offset:offset+size]);h: sha2.Context_256;sha2.init_256(&h)
            hash_string(&h,"GAIA-INPUT-LEAF-1");hash_string(&h,name);hash_u64(&h,u64(size));sha2.update(&h,payload[:]);sha2.final(&h,leaves[i][:])
        }
        offset+=size+1
    }
    if offset!=len(blob) {os.exit(3)}
    full: Digest
    if mode!="off" {
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

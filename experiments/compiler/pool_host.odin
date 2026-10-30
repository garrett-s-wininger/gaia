// Fixed-size Odin worker set draining a bounded, admitted job table.
package main
import "core:c"
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
Pool :: struct {handle: rawptr, next_job, failed, count: i32}
worker_main :: proc(t: ^thread.Thread) {
    p:=cast(^Pool)t.data
    worker:=gaia_worker_open(p.handle)
    if worker==nil {sync.atomic_store(&p.failed,1);return}
    defer gaia_worker_close(worker)
    for sync.atomic_load(&p.failed)==0 {
        job:=sync.atomic_add(&p.next_job,1)
        if job>=p.count {break}
        if gaia_worker_compile(worker,c.int(job))!=0 {sync.atomic_store(&p.failed,1);break}
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
    if len(os.args)!=12 {fmt.eprintln("host memory|physical CLANG ROOT BUNDLE PIN OUT PLAN WORKERS internal|external|retry LINKER LINKPLAN");os.exit(2)}
    mode:=os.args[1];if mode!="memory" && mode!="physical" {os.exit(2)}
    count,ok:=strconv.parse_int(os.args[8]);if !ok || count<1 || count>16 {os.exit(2)}
    link_mode:=os.args[9];if link_mode!="internal" && link_mode!="external" && link_mode!="retry" {os.exit(2)}
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
    p:=Pool{handle=handle,count=i32(gaia_pool_count(handle))}
    threads:=make([]^thread.Thread,min(count,int(p.count)));defer delete(threads)
    ready:=time.tick_now()
    for &t in threads {t=thread.create(worker_main);t.data=&p;thread.start(t)}
    for t in threads {thread.join(t);thread.destroy(t)}
    compiled:=time.tick_now();status:=int(sync.atomic_load(&p.failed));retry_result: c.int
    if status==0 && link_mode!="external" {
        if link_mode=="retry" {retry_result=gaia_pool_link(handle,1);if retry_result==0 {status=9}}
        if status==0 {status=int(gaia_pool_link(handle,0))}
    }
    finished:=time.tick_now();s: Stats;gaia_pool_stats(handle,&s)
    messages:=gaia_pool_messages(handle);if len(string(messages))>0 {fmt.eprint(string(messages))}
    fmt.print("{")
    fmt.printf("\"correct\":%v,\"workers\":%d,\"compiled\":%d,\"errors\":%d,\"warnings\":%d,"+
        "\"job_count\":%d,\"peak_active\":%d,\"link_calls\":%d,\"link_result\":%d,\"can_run_again\":%v,"+
        "\"retry_result\":%d,\"setup_ns\":%d,\"compile_wall_ns\":%d,\"link_ns\":%d,\"workload_ns\":%d,\"peak_rss_bytes\":%d,\"jobs\":[",
        status==0,count,s.compiled,s.errors,s.warnings,s.job_count,s.peak_active,s.link_calls,s.link_result,s.can_run_again!=0,
        retry_result,time.duration_nanoseconds(time.tick_diff(start,ready)),time.duration_nanoseconds(time.tick_diff(ready,compiled)),
        s.link_ns,time.duration_nanoseconds(time.tick_diff(start,finished)),peak_rss())
    for i in 0..<int(s.job_count) {
        if i>0 {fmt.print(",")}
        fmt.printf("[%d,%d]",gaia_pool_job_time(handle,c.int(i),0),gaia_pool_job_time(handle,c.int(i),1))
    }
    fmt.println("]}")
    if status!=0 {os.exit(status)}
}

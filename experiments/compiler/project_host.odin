// Generic request-plan runner. Input mappings outlive all compiler objects.
package main

import "core:c"
import "core:fmt"
import "core:os"
import "core:strings"
import "core:sys/posix"
import "core:time"

Stats :: struct {
    setup_ns, compile_ns, dispose_ns, input_files, input_bytes: u64,
    compiled, errors, warnings: u64,
}
foreign import shim "system:c"
foreign shim {
    gaia_compile_plan :: proc(memory: c.int, clang, root, output: cstring,
        data: [^]u8, size: c.size_t, pin: cstring,
        plan: [^]u8, plan_size: c.size_t, stats: ^Stats) -> c.int ---
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
main :: proc() {
    if len(os.args)!=8 {fmt.eprintln("host physical|memory CLANG ROOT BUNDLE PIN OUTPUT PLAN");os.exit(2)}
    mode:=os.args[1];if mode!="physical" && mode!="memory" {os.exit(2)}
    names: [6]cstring
    paths:=[]string{os.args[2],os.args[3],os.args[6],os.args[5],os.args[4],os.args[7]}
    for path,i in paths {names[i]=strings.clone_to_cstring(path)}
    defer {for name in names {delete(name)}}
    start:=time.tick_now();input: Mapping
    plan:=map_file(names[5],4*1024*1024)
    if mode=="memory" {input=map_file(names[4],64*1024*1024)}
    mapped:=time.tick_now();stats: Stats
    status:=gaia_compile_plan(c.int(mode=="memory"),names[0],names[1],names[2],
        raw_data(input.data),c.size_t(len(input.data)),names[3],
        raw_data(plan.data),c.size_t(len(plan.data)),&stats)
    if len(input.data)>0 {posix.munmap(raw_data(input.data),c.size_t(len(input.data)));posix.close(input.fd)}
    posix.munmap(raw_data(plan.data),c.size_t(len(plan.data)));posix.close(plan.fd)
    finished:=time.tick_now();fmt.print("{")
    fmt.printf("\"correct\":%v,\"compiled\":%d,\"errors\":%d,\"warnings\":%d,"+
        "\"input_files\":%d,\"input_bytes\":%d,\"map_ns\":%d,\"setup_ns\":%d,"+
        "\"compile_ns\":%d,\"dispose_ns\":%d,\"workload_ns\":%d}\n",
        status==0,stats.compiled,stats.errors,stats.warnings,stats.input_files,stats.input_bytes,
        time.duration_nanoseconds(time.tick_diff(start,mapped)),stats.setup_ns,stats.compile_ns,stats.dispose_ns,
        time.duration_nanoseconds(time.tick_diff(start,finished)))
    if status!=0 {os.exit(int(status))}
}

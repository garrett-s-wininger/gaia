// Linux MVP host. Clang's C++ API is isolated behind one C-compatible function.
package main

import "core:c"
import "core:fmt"
import "core:os"
import "core:strconv"
import "core:strings"
import "core:sys/posix"
import "core:time"

Stats :: struct {
    setup_ns, compile_ns, dispose_ns, input_files, input_bytes: u64,
    compiled, errors, warnings: u64,
}
foreign import shim "system:c"
foreign shim {
    gaia_compile :: proc(memory: c.int, clang, root, output: cstring, requests: c.int,
                         data: [^]u8, size: c.size_t, pin: cstring, stats: ^Stats) -> c.int ---
}
main :: proc() {
    if len(os.args)!=8 {fmt.eprintln("host physical|memory CLANG ROOT BUNDLE PIN OUTPUT REQUESTS");os.exit(2)}
    mode := os.args[1]
    if mode!="physical" && mode!="memory" {os.exit(2)}
    count, ok := strconv.parse_int(os.args[7]);if !ok {os.exit(2)}
    names: [5]cstring
    paths := []string{os.args[2],os.args[3],os.args[6],os.args[5],os.args[4]}
    for name,i in paths {
        names[i]=strings.clone_to_cstring(name)
    }
    defer {for name in names {delete(name)}}
    start := time.tick_now()
    data: []u8
    fd: posix.FD = -1
    if mode=="memory" {
        fd=posix.open(names[4],{.CLOEXEC})
        if fd<0 {os.exit(3)}
        info: posix.stat_t
        if posix.fstat(fd,&info)!=nil || info.st_size<16 || info.st_size>64*1024*1024 {os.exit(3)}
        ptr:=posix.mmap(nil,c.size_t(info.st_size),{.READ},{.PRIVATE},fd,0)
        if ptr==posix.MAP_FAILED {os.exit(3)}
        data=([^]u8)(ptr)[:int(info.st_size)]
    }
    mapped := time.tick_now()
    stats: Stats
    status:=gaia_compile(c.int(mode=="memory"),names[0],names[1],names[2],c.int(count),
                         raw_data(data),c.size_t(len(data)),names[3],&stats)
    if len(data)>0 {posix.munmap(raw_data(data),c.size_t(len(data)));posix.close(fd)}
    finished := time.tick_now()
    fmt.print("{")
    fmt.printf("\"correct\":%v,\"compiled\":%d,\"errors\":%d,\"warnings\":%d,"+
               "\"input_files\":%d,\"input_bytes\":%d,\"map_ns\":%d,"+
               "\"setup_ns\":%d,\"compile_ns\":%d,\"dispose_ns\":%d,\"workload_ns\":%d}\n",
               status==0,stats.compiled,stats.errors,stats.warnings,stats.input_files,stats.input_bytes,
               time.duration_nanoseconds(time.tick_diff(start,mapped)),stats.setup_ns,stats.compile_ns,stats.dispose_ns,
               time.duration_nanoseconds(time.tick_diff(start,finished)))
    if status!=0 {os.exit(int(status))}
}

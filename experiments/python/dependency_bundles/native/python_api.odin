// C ABI for the CPython shim. Unlike the CLI checks, input failures return errors.
package main

import "base:runtime"
import "core:c"
import "core:os"
import "core:slice"
import "core:strings"
import "core:sys/posix"
import "core:unicode/utf8"

Status :: enum i32 { Ok, IO, Index_Digest, Format, Bundle_Size, Bundle_Digest, Local_Identity, Changed, CRC, Row }
Handle :: struct { index: Index, bundle: Mapping, names, directories: [dynamic]u8 }

map_checked :: proc(path: string) -> (m: Mapping, status: Status) {
    name := strings.clone_to_cstring(path)
    defer delete(name)
    fd := posix.open(name,{.CLOEXEC})
    if fd < 0 { return {},.IO }
    info: posix.stat_t
    if posix.fstat(fd,&info) != nil || info.st_size <= 0 { posix.close(fd); return {},.IO }
    ptr := posix.mmap(nil,c.size_t(info.st_size),{.READ},{.PRIVATE},fd,0)
    if ptr == posix.MAP_FAILED { posix.close(fd); return {},.IO }
    return Mapping{fd,([^]u8)(ptr)[:int(info.st_size)],info},.Ok
}

destroy_handle :: proc(h: ^Handle) {
    if len(h.bundle.data)>0 { unmap(h.bundle) }
    if len(h.index.mapping.data)>0 { close_index(&h.index) }
    delete(h.names); delete(h.directories); free(h)
}

open_checked :: proc(index_path,pin,archive: string,local: bool) -> (handle: ^Handle,status: Status) {
    h := new(Handle)
    success := false
    defer if !success { destroy_handle(h) }
    mapping,err := map_checked(index_path)
    if err != .Ok { return nil,err }
    h.index.mapping=mapping
    data := mapping.data
    actual := hex(hash(data))
    defer delete(actual)
    if actual != pin { return nil,.Index_Digest }
    if len(data)<128 || string(data[:8])!="GAIAIDX\x00" || le(data,8,4)!=1 || le(data,12,4)!=0 { return nil,.Format }
    n,d,pool := le(data,104,8),le(data,112,8),le(data,120,8)
    if n>u64(len(data))/28 || d==0 || d>u64(len(data))/4 { return nil,.Format }
    cursor := 128+28*int(n)+4*int(d)
    if cursor>len(data) || pool!=u64(len(data)-cursor) { return nil,.Format }
    size,end := le(data,16,8),le(data,24,8)
    if size>0x7fffffffffffffff || end>size { return nil,.Format }
    h.index.count,h.index.archive_size,h.index.payload_end=int(n),int(size),int(end)
    h.index.directories=make([]string,int(d))
    h.index.name_starts=make([]int,int(n))
    seen := make(map[string]bool,int(d))
    defer delete(seen)
    for i in 0..<int(d) {
        length:=int(le(data,128+28*int(n)+4*i,4))
        if length>len(data)-cursor { return nil,.Format }
        name:=string(data[cursor:cursor+length])
        if !utf8.valid_string(name) || name in seen || strings.contains(name,"\x00") { return nil,.Format }
        seen[name]=true
        h.index.directories[i]=name
        append(&h.directories,name);append(&h.directories,0)
        cursor+=length
    }
    if h.index.directories[0]!="" { return nil,.Format }
    previous:u64
    for i in 0..<int(n) {
        p:=128+28*i
        start,length:=le(data,p,8),le(data,p+8,8)
        name_length:=int(le(data,p+24,4))
        directory:=le(data,p+20,4)
        if start>end || length>end-start || start<previous || directory>=d || name_length==0 || name_length>len(data)-cursor { return nil,.Format }
        name:=string(data[cursor:cursor+name_length])
        if !utf8.valid_string(name) || strings.contains(name,"\x00") { return nil,.Format }
        h.index.name_starts[i]=cursor
        append(&h.names,h.index.directories[directory]);append(&h.names,name);append(&h.names,0)
        cursor+=name_length
        previous=start+length
    }
    if cursor!=len(data) { return nil,.Format }
    bundle,bundle_err:=map_checked(archive)
    if bundle_err!=.Ok { return nil,bundle_err }
    h.bundle=bundle
    if len(bundle.data)!=int(size) { return nil,.Bundle_Size }
    if local {
        id:=identity(bundle.stat)
        for value,i in id { if value!=le(data,64+8*i,8) { return nil,.Local_Identity } }
    } else {
        digest:=hash(bundle.data)
        if !slice.equal(digest[:],data[32:64]) { return nil,.Bundle_Digest }
    }
    after:posix.stat_t
    if posix.fstat(bundle.fd,&after)!=nil || identity(after)!=identity(bundle.stat) { return nil,.Changed }
    success=true
    return h,.Ok
}

@(export)
gaia_open :: proc "c" (index_path,pin,archive:cstring,local:i32,out:^rawptr) -> i32 {
    context=runtime.default_context()
    h,status:=open_checked(string(index_path),string(pin),string(archive),local!=0)
    out^=h
    return i32(status)
}

@(export)
gaia_catalog :: proc "c" (handle:rawptr,names,directories:^[^]u8,names_len,dirs_len,count:^u64) {
    context=runtime.default_context()
    h:=(^Handle)(handle)
    names^=raw_data(h.names);directories^=raw_data(h.directories)
    names_len^=u64(len(h.names));dirs_len^=u64(len(h.directories));count^=u64(h.index.count)
}

@(export)
gaia_read :: proc "c" (handle:rawptr,row:u64,out:^[^]u8,length:^u64) -> i32 {
    context=runtime.default_context()
    h:=(^Handle)(handle)
    if row>=u64(h.index.count) { return i32(Status.Row) }
    e:=entry(&h.index,int(row))
    data:=h.bundle.data[e.start:e.start+e.length]
    if u32(crc32_z(0,raw_data(data),c.size_t(len(data))))!=e.crc { return i32(Status.CRC) }
    out^=raw_data(data);length^=u64(len(data))
    return 0
}

@(export)
gaia_close :: proc "c" (handle:rawptr) {
    context=runtime.default_context()
    destroy_handle((^Handle)(handle))
}

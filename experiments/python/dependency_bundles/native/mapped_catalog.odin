// Experimental v1 pointer-free lookup layout. Integer views require LE/64-bit.
package main

import "base:runtime"
import "core:c"
import "core:slice"
import "core:strings"
import "core:sys/posix"
import "core:time"
import "core:unicode/utf8"

mapped_ints :: proc(data: []u8,cursor:^int,n:int) -> []int {
    start:=cursor^;cursor^+=8*n
    return ([^]int)(raw_data(data[start:cursor^]))[:n]
}
mapped_domain :: proc(values: []int,limit:int,empty_required:bool=false) -> bool {
    empty:=false
    for v in values { if v<0 || v>limit { return false };if v==0 { empty=true } }
    return !empty_required || empty
}

mapped_open :: proc(index_path,pin,archive,lookup_path,lookup_pin:string,local:bool,budget:u64) -> (^Live_Handle,i32) {
    when ODIN_ARCH != .amd64 { return nil,i32(Status.Format) }
    h:=new(Live_Handle);success:=false
    defer if !success { live_destroy(h) }
    index,err:=map_checked(index_path)
    if err!=.Ok { return nil,i32(err) };h.base.index.mapping=index
    lookup,lookup_err:=map_checked(lookup_path)
    if lookup_err!=.Ok { return nil,i32(lookup_err) };h.lookup_mapping=lookup
    data,derived:=index.data,lookup.data
    begin:=time.tick_now()
    index_digest,derived_digest:=hash(data),hash(derived)
    index_hex,derived_hex:=hex(index_digest),hex(derived_digest)
    defer delete(index_hex);defer delete(derived_hex)
    if index_hex!=pin || derived_hex!=lookup_pin { return nil,i32(Status.Index_Digest) }
    h.integrity_seconds=time.duration_seconds(time.tick_since(begin))
    begin=time.tick_now()
    if len(data)<128 || string(data[:8])!="GAIAIDX\x00" || le(data,8,4)!=1 || le(data,12,4)!=0 { return nil,i32(Status.Format) }
    if len(derived)<256 || string(derived[:8])!="GAIACAT\x00" || le(derived,8,4)!=1 || le(derived,12,4)!=0 { return nil,i32(Status.Format) }
    if !slice.equal(derived[16:48],index_digest[:]) { return nil,i32(Status.Index_Digest) }
    for b in derived[120:256] { if b!=0 { return nil,i32(Status.Format) } }
    n,d,pool:=le(data,104,8),le(data,112,8),le(data,120,8)
    if n>u64(len(data))/28 || d==0 || d>u64(len(data))/4 { return nil,i32(Status.Format) }
    cursor:=128+28*int(n)+4*int(d)
    if cursor>len(data) || pool!=u64(len(data)-cursor) { return nil,i32(Status.Format) }
    size,end:=le(data,16,8),le(data,24,8)
    if size>0x7fffffffffffffff || end>size { return nil,i32(Status.Format) }
    slots,dirslots:=live_capacity(int(n)),live_capacity(int(d))
    body_size:=24*n+32*d+16*u64(slots)+8*u64(dirslots)
    payload_offset:=256+16*d
    module_total:=le(derived,64,8)
    if (le(derived,48,8)!=n || le(derived,56,8)!=d || module_total>n ||
        le(derived,72,8)!=u64(slots) || le(derived,80,8)!=u64(dirslots) ||
        le(derived,88,8)!=u64(len(derived)) || le(derived,96,8)!=256 ||
        le(derived,104,8)!=payload_offset || le(derived,112,8)!=body_size ||
        payload_offset>u64(len(derived)) || body_size!=u64(len(derived))-payload_offset) { return nil,i32(Status.Format) }
    if budget<16*d || budget>0x7fffffffffffffff { return nil,10 }
    ptr:=posix.mmap(nil,c.size_t(budget),{.READ,.WRITE},{.PRIVATE,.ANONYMOUS},-1,0)
    if ptr==posix.MAP_FAILED { return nil,i32(Status.IO) }
    h.arena=([^]u8)(ptr)[:int(budget)]
    region:=live_take(h,16*int(d));h.base.index.directories=([^]string)(raw_data(region))[:int(d)]
    h.base.index.count,h.base.index.archive_size,h.base.index.payload_end=int(n),int(size),int(end)
    h.module_total=int(module_total)
    table_cursor:=int(payload_offset)
    h.base.index.name_starts=mapped_ints(derived,&table_cursor,int(n))
    h.files=mapped_ints(derived,&table_cursor,slots);h.modules=mapped_ints(derived,&table_cursor,slots)
    h.dirs=mapped_ints(derived,&table_cursor,dirslots)
    h.file_heads=mapped_ints(derived,&table_cursor,int(d));h.module_heads=mapped_ints(derived,&table_cursor,int(d))
    h.file_counts=mapped_ints(derived,&table_cursor,int(d));h.module_counts=mapped_ints(derived,&table_cursor,int(d))
    h.file_next=mapped_ints(derived,&table_cursor,int(n));h.module_next=mapped_ints(derived,&table_cursor,int(n))
    if table_cursor!=len(derived) { return nil,i32(Status.Format) }
    if (!mapped_domain(h.files,int(n),true) || !mapped_domain(h.modules,int(n),true) || !mapped_domain(h.dirs,int(d),true) ||
        !mapped_domain(h.file_heads,int(n)) || !mapped_domain(h.module_heads,int(n)) ||
        !mapped_domain(h.file_counts,int(n)) || !mapped_domain(h.module_counts,int(n)) ||
        !mapped_domain(h.file_next,int(n)) || !mapped_domain(h.module_next,int(n))) { return nil,i32(Status.Format) }
    file_total,module_children:=0,0
    for v in h.file_counts { if v>int(n)-file_total { return nil,i32(Status.Format) };file_total+=v }
    for v in h.module_counts { if v>h.module_total-module_children { return nil,i32(Status.Format) };module_children+=v }
    if file_total!=int(n) || module_children>h.module_total { return nil,i32(Status.Format) }
    for i in 0..<int(d) {
        length:=int(le(data,128+28*int(n)+4*i,4))
        if length>len(data)-cursor || le(derived,256+16*i,8)!=u64(cursor) || le(derived,264+16*i,8)!=u64(length) { return nil,i32(Status.Format) }
        name:=string(data[cursor:cursor+length])
        if !utf8.valid_string(name) || strings.contains(name,"\x00") { return nil,i32(Status.Format) }
        h.base.index.directories[i]=name;cursor+=length
    }
    if h.base.index.directories[0]!="" { return nil,i32(Status.Format) }
    for name,i in h.base.index.directories { if live_dir(h,name)!=i { return nil,i32(Status.Format) } }
    previous:u64
    for i in 0..<int(n) {
        p:=128+28*i
        start,length:=le(data,p,8),le(data,p+8,8);name_length:=int(le(data,p+24,4));directory:=le(data,p+20,4)
        if start>end || length>end-start || start<previous || directory>=d || name_length==0 || name_length>len(data)-cursor || h.base.index.name_starts[i]!=cursor { return nil,i32(Status.Format) }
        name:=string(data[cursor:cursor+name_length])
        if !utf8.valid_string(name) || strings.contains(name,"\x00") { return nil,i32(Status.Format) }
        cursor+=name_length;previous=start+length
    }
    if cursor!=len(data) { return nil,i32(Status.Format) }
    h.validation_seconds=time.duration_seconds(time.tick_since(begin))
    bundle,bundle_err:=map_checked(archive)
    if bundle_err!=.Ok { return nil,i32(bundle_err) };h.base.bundle=bundle
    begin=time.tick_now()
    if len(bundle.data)!=int(size) { return nil,i32(Status.Bundle_Size) }
    if local {
        id:=identity(bundle.stat)
        for v,i in id { if v!=le(data,64+8*i,8) { return nil,i32(Status.Local_Identity) } }
    } else {
        digest:=hash(bundle.data)
        if !slice.equal(digest[:],data[32:64]) { return nil,i32(Status.Bundle_Digest) }
    }
    after:posix.stat_t
    if posix.fstat(bundle.fd,&after)!=nil || identity(after)!=identity(bundle.stat) { return nil,i32(Status.Changed) }
    h.integrity_seconds+=time.duration_seconds(time.tick_since(begin))
    success=true;return h,0
}

@(export)
gaia_mapped_open :: proc "c" (index,pin,archive,lookup,lookup_pin:cstring,local:i32,budget:u64,out:^rawptr) -> i32 {
    context=runtime.default_context();h,status:=mapped_open(string(index),string(pin),string(archive),string(lookup),string(lookup_pin),local!=0,budget)
    out^=h;return status
}

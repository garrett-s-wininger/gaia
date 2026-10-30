// Unified v1 envelope: embedded range index and mapped 64-bit/compact 32-bit tables.
package main

import "base:runtime"
import "core:c"
import "core:slice"
import "core:strings"
import "core:sys/posix"
import "core:time"
import "core:unicode/utf8"

unified_capacity :: proc(n:int) -> int {
    result:=1
    for result*3<n*4 { result*=2 }
    return result
}
unified_u32s :: proc(data:[]u8,cursor:^int,n:int) -> []u32 {
    start:=cursor^;cursor^+=4*n;return ([^]u32)(raw_data(data[start:cursor^]))[:n]
}
unified_open :: proc(path,pin,index_pin,archive:string,local:bool,budget:u64) -> (^Live_Handle,i32) {
    when ODIN_ARCH != .amd64 { return nil,i32(Status.Format) }
    h:=new(Live_Handle);success:=false
    defer if !success { live_destroy(h) }
    mapping,err:=map_checked(path)
    if err!=.Ok { return nil,i32(err) };h.lookup_mapping=mapping
    whole:=mapping.data;begin:=time.tick_now();actual:=hex(hash(whole));defer delete(actual)
    if actual!=pin { return nil,i32(Status.Index_Digest) }
    h.integrity_seconds=time.duration_seconds(time.tick_since(begin));begin=time.tick_now()
    if len(whole)<256 || string(whole[:8])!="GAIAUNI\x00" || le(whole,8,4)!=1 || le(whole,12,4)>1 { return nil,i32(Status.Format) }
    provenance:[32]u8;copy(provenance[:],whole[16:48]);source_pin:=hex(provenance);defer delete(source_pin)
    if source_pin!=index_pin { return nil,i32(Status.Index_Digest) }
    for b in whole[144:256] { if b!=0 { return nil,i32(Status.Format) } }
    size_total,index_offset,index_length:=le(whole,48,8),le(whole,56,8),le(whole,64,8)
    if size_total!=u64(len(whole)) || index_offset!=256 || index_length>u64(len(whole))-256 || index_length<128 { return nil,i32(Status.Format) }
    data:=whole[256:256+int(index_length)]
    h.embedded_index=true;h.base.index.mapping=Mapping{fd=-1,data=data}
    if string(data[:8])!="GAIAIDX\x00" || le(data,8,4)!=1 || le(data,12,4)!=0 { return nil,i32(Status.Format) }
    n,d,pool:=le(data,104,8),le(data,112,8),le(data,120,8)
    if n>u64(len(data))/28 || d==0 || d>u64(len(data))/4 { return nil,i32(Status.Format) }
    cursor:=128+28*int(n)+4*int(d)
    if cursor>len(data) || pool!=u64(len(data)-cursor) { return nil,i32(Status.Format) }
    size,end:=le(data,16,8),le(data,24,8)
    if size>0x7fffffffffffffff || end>size { return nil,i32(Status.Format) }
    small:=le(whole,12,4)==1;width:=8
    fc,mc,dc:=live_capacity(int(n)),live_capacity(int(n)),live_capacity(int(d))
    modules:=le(whole,88,8)
    if modules>n { return nil,i32(Status.Format) }
    if small {
        if n>=0x100000000 || d>=0x100000000 || index_length>=0x100000000 { return nil,i32(Status.Format) }
        width=4;fc,mc,dc=unified_capacity(int(n)),unified_capacity(int(modules)),unified_capacity(int(d))
    }
    dir_offset,table_offset,body_size:=le(whole,120,8),le(whole,128,8),le(whole,136,8)
    expected_dir:=(256+index_length+7)&~u64(7)
    expected_table:=(expected_dir+u64(2*width)*d+7)&~u64(7)
    expected_body:=u64(width)*(3*n+u64(fc)+u64(mc)+u64(dc)+4*d)
    if (le(whole,72,8)!=n || le(whole,80,8)!=d || le(whole,96,8)!=u64(fc) || le(whole,104,8)!=u64(mc) || le(whole,112,8)!=u64(dc) ||
        dir_offset!=expected_dir || table_offset!=expected_table || body_size!=expected_body || table_offset>u64(len(whole)) || body_size!=u64(len(whole))-table_offset) { return nil,i32(Status.Format) }
    for b in whole[256+int(index_length):int(dir_offset)] { if b!=0 { return nil,i32(Status.Format) } }
    for b in whole[int(dir_offset)+2*width*int(d):int(table_offset)] { if b!=0 { return nil,i32(Status.Format) } }
    if budget<16*d || budget>0x7fffffffffffffff { return nil,10 }
    ptr:=posix.mmap(nil,c.size_t(budget),{.READ,.WRITE},{.PRIVATE,.ANONYMOUS},-1,0)
    if ptr==posix.MAP_FAILED { return nil,i32(Status.IO) };h.arena=([^]u8)(ptr)[:int(budget)]
    region:=live_take(h,16*int(d));h.base.index.directories=([^]string)(raw_data(region))[:int(d)]
    h.base.index.count,h.base.index.archive_size,h.base.index.payload_end=int(n),int(size),int(end)
    h.module_total=int(modules);h.small=small;table_cursor:=int(table_offset)
    if small {
        h.base.index.name_starts32=unified_u32s(whole,&table_cursor,int(n))
        lengths:=[9]int{fc,mc,dc,int(d),int(d),int(d),int(d),int(n),int(n)}
        for length,i in lengths { h.small_tables[i]=unified_u32s(whole,&table_cursor,length) }
    } else {
        h.base.index.name_starts=mapped_ints(whole,&table_cursor,int(n))
        h.files=mapped_ints(whole,&table_cursor,fc);h.modules=mapped_ints(whole,&table_cursor,mc);h.dirs=mapped_ints(whole,&table_cursor,dc)
        h.file_heads=mapped_ints(whole,&table_cursor,int(d));h.module_heads=mapped_ints(whole,&table_cursor,int(d))
        h.file_counts=mapped_ints(whole,&table_cursor,int(d));h.module_counts=mapped_ints(whole,&table_cursor,int(d))
        h.file_next=mapped_ints(whole,&table_cursor,int(n));h.module_next=mapped_ints(whole,&table_cursor,int(n))
    }
    if table_cursor!=len(whole) { return nil,i32(Status.Format) }
    for kind in 0..<9 {
        limit:=int(n);if kind==2 { limit=int(d) };empty:=false
        for i in 0..<live_len(h,kind) {
            v:=live_value(h,kind,i);if v<0 || v>limit { return nil,i32(Status.Format) };if v==0 { empty=true }
        }
        if kind<3 && !empty { return nil,i32(Status.Format) }
    }
    file_total,module_children:=0,0
    for i in 0..<int(d) {
        f,m:=live_value(h,5,i),live_value(h,6,i)
        if f>int(n)-file_total || m>h.module_total-module_children { return nil,i32(Status.Format) }
        file_total+=f;module_children+=m
    }
    if file_total!=int(n) { return nil,i32(Status.Format) }
    for i in 0..<int(d) {
        length:=int(le(data,128+28*int(n)+4*i,4));record:=int(dir_offset)+2*width*i
        if length>len(data)-cursor || le(whole,record,width)!=u64(cursor) || le(whole,record+width,width)!=u64(length) { return nil,i32(Status.Format) }
        name:=string(data[cursor:cursor+length])
        if !utf8.valid_string(name) || strings.contains(name,"\x00") { return nil,i32(Status.Format) }
        h.base.index.directories[i]=name;cursor+=length
    }
    if h.base.index.directories[0]!="" { return nil,i32(Status.Format) }
    for name,i in h.base.index.directories { if live_dir(h,name)!=i { return nil,i32(Status.Format) } }
    previous:u64
    for i in 0..<int(n) {
        p:=128+28*i;start,length:=le(data,p,8),le(data,p+8,8);name_length:=int(le(data,p+24,4));directory:=le(data,p+20,4)
        name_start:int
        if small { name_start=int(h.base.index.name_starts32[i]) } else { name_start=h.base.index.name_starts[i] }
        if start>end || length>end-start || start<previous || directory>=d || name_length==0 || name_length>len(data)-cursor || name_start!=cursor { return nil,i32(Status.Format) }
        name:=string(data[cursor:cursor+name_length])
        if !utf8.valid_string(name) || strings.contains(name,"\x00") { return nil,i32(Status.Format) }
        cursor+=name_length;previous=start+length
    }
    if cursor!=len(data) { return nil,i32(Status.Format) }
    h.validation_seconds=time.duration_seconds(time.tick_since(begin))
    bundle,bundle_err:=map_checked(archive)
    if bundle_err!=.Ok { return nil,i32(bundle_err) };h.base.bundle=bundle;begin=time.tick_now()
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
    h.integrity_seconds+=time.duration_seconds(time.tick_since(begin));success=true;return h,0
}

@(export)
gaia_unified_open :: proc "c" (path,pin,index_pin,archive:cstring,local:i32,budget:u64,out:^rawptr) -> i32 {
    context=runtime.default_context();h,status:=unified_open(string(path),string(pin),string(index_pin),string(archive),local!=0,budget)
    out^=h;return status
}

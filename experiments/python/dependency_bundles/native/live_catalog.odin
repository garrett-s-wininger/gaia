// Native-only catalog. All variable-sized persistent metadata uses one mmap arena.
package main

import "base:runtime"
import "core:c"
import "core:slice"
import "core:strings"
import "core:sys/posix"
import "core:time"
import "core:unicode/utf8"

Live_Handle :: struct {
    base: Handle, // Prefix permits the unchanged gaia_read CRC/payload path.
    arena: []u8,
    used: int,
    files, modules, dirs: []int,
    file_heads, module_heads, file_counts, module_counts: []int,
    file_next, module_next: []int,
    module_total: int,
    lookup_mapping: Mapping,
    integrity_seconds, validation_seconds, construction_seconds: f64,
    embedded_index, small: bool,
    small_tables: [9][]u32,
}

live_take :: proc(h: ^Live_Handle, n: int) -> []u8 {
    start := (h.used+7)&~7
    if n<0 || start>len(h.arena) || n>len(h.arena)-start { return nil }
    h.used=start+n
    return h.arena[start:h.used]
}
live_ints :: proc(h: ^Live_Handle, n: int) -> []int {
    data:=live_take(h,8*n)
    if len(data)!=8*n { return nil }
    return ([^]int)(raw_data(data))[:n]
}
live_capacity :: proc(n: int) -> int {
    result:=1
    for result<2*n { result*=2 }
    return result
}
live_destroy :: proc(h: ^Live_Handle) {
    if len(h.base.bundle.data)>0 { unmap(h.base.bundle) }
    if len(h.base.index.mapping.data)>0 && !h.embedded_index { unmap(h.base.index.mapping) }
    if len(h.arena)>0 { posix.munmap(raw_data(h.arena),c.size_t(len(h.arena))) }
    if len(h.lookup_mapping.data)>0 { unmap(h.lookup_mapping) }
    free(h)
}
live_hash :: proc(s: string, module: bool = false) -> u64 {
    value:=u64(14695981039346656037)
    for i in 0..<len(s) {
        b:=s[i]
        if module && b=='.' { b='/' }
        value=(value~u64(b))*1099511628211
    }
    return value
}
live_table :: #force_inline proc(h:^Live_Handle,kind:int) -> []int {
    switch kind {
    case 0:return h.files
    case 1:return h.modules
    case 2:return h.dirs
    case 3:return h.file_heads
    case 4:return h.module_heads
    case 5:return h.file_counts
    case 6:return h.module_counts
    case 7:return h.file_next
    case 8:return h.module_next
    }
    return nil
}
live_len :: #force_inline proc(h:^Live_Handle,kind:int) -> int {
    if h.small { return len(h.small_tables[kind]) };return len(live_table(h,kind))
}
live_value :: #force_inline proc(h:^Live_Handle,kind,i:int) -> int {
    if h.small { return int(h.small_tables[kind][i]) };return live_table(h,kind)[i]
}
live_dir :: proc(h: ^Live_Handle, name: string) -> int {
    count:=live_len(h,2);slot:=int(live_hash(name)&u64(count-1))
    probes:=0
    for live_value(h,2,slot)!=0 {
        if probes>=count { return -1 };probes+=1
        i:=live_value(h,2,slot)-1
        if h.base.index.directories[i]==name { return i }
        slot=(slot+1)&(count-1)
    }
    return -1
}
// Canonical module names use slash separators, represented as a prefix of the
// original directory+basename fragments. No concatenated native strings.
live_length :: proc(h: ^Live_Handle, row: int, module: bool) -> (length: int, is_pkg: bool) {
    e:=entry(&h.base.index,row)
    length=len(h.base.index.directories[e.directory])+len(e.name)
    if !module { return length,false }
    if strings.has_suffix(e.name,".pyc") { length-=4 }
    else if strings.has_suffix(e.name,".py") { length-=3 }
    else { return -1,false }
    if (e.name=="__init__.py" || e.name=="__init__.pyc") && e.directory!=0 {
        length-=len("/__init__");is_pkg=true
    }
    return
}
live_parts :: #force_inline proc(h: ^Live_Handle,row:int) -> (string,string) {
    e:=entry(&h.base.index,row);return h.base.index.directories[e.directory],e.name
}
live_at :: #force_inline proc(dir,name:string,i:int,module:bool) -> u8 {
    b:u8
    if i<len(dir) { b=dir[i] } else { b=name[i-len(dir)] }
    if module && b=='.' { b='/' };return b
}
live_row_hash :: proc(h: ^Live_Handle, row: int, module: bool) -> u64 {
    length,_:=live_length(h,row,module);value:=u64(14695981039346656037)
    dir,name:=live_parts(h,row)
    for i in 0..<length {
        b:=live_at(dir,name,i,module)
        value=(value~u64(b))*1099511628211
    }
    return value
}
live_equal :: proc(h: ^Live_Handle, row: int, name: string, module: bool) -> bool {
    length,_:=live_length(h,row,module)
    if length!=len(name) { return false }
    dir,base:=live_parts(h,row)
    for i in 0..<length {
        b:=name[i]
        if module && b=='.' { b='/' }
        a:=live_at(dir,base,i,module)
        if a!=b { return false }
    }
    return true
}
live_find :: proc(h: ^Live_Handle, name: string, module: bool) -> int {
    kind:=0;if module { kind=1 };count:=live_len(h,kind)
    slot:=int(live_hash(name,module)&u64(count-1))
    probes:=0
    for live_value(h,kind,slot)!=0 {
        if probes>=count { return -1 };probes+=1
        row:=live_value(h,kind,slot)-1
        if live_equal(h,row,name,module) { return row }
        slot=(slot+1)&(count-1)
    }
    return -1
}
live_insert :: proc(h: ^Live_Handle, row: int, module: bool) -> bool {
    slots:=h.files
    if module { slots=h.modules }
    slot:=int(live_row_hash(h,row,module)&u64(len(slots)-1))
    dir,name:=live_parts(h,row)
    for slots[slot]!=0 {
        other:=slots[slot]-1;a,_:=live_length(h,row,module);b,_:=live_length(h,other,module)
        equal:=a==b
        if equal { other_dir,other_name:=live_parts(h,other);for i in 0..<a {
            x,y:=live_at(dir,name,i,module),live_at(other_dir,other_name,i,module)
            if x!=y { equal=false;break }
        } }
        if equal { return false }
        slot=(slot+1)&(len(slots)-1)
    }
    slots[slot]=row+1
    return true
}
live_parent :: proc(h: ^Live_Handle, row: int) -> int {
    length,_:=live_length(h,row,true);cut:=-1
    dir,name:=live_parts(h,row)
    for i in 0..<length { b:=live_at(dir,name,i,true);if b=='/' { cut=i } }
    if cut<0 { return 0 }
    value:=u64(14695981039346656037)
    for i in 0..<cut { b:=live_at(dir,name,i,true);value=(value~u64(b))*1099511628211 }
    slot:=int(value&u64(len(h.modules)-1))
    for h.modules[slot]!=0 {
        other:=h.modules[slot]-1;other_len,pkg:=live_length(h,other,true);equal:=other_len==cut
        if equal { other_dir,other_name:=live_parts(h,other);for i in 0..<cut {
            a,b:=live_at(dir,name,i,true),live_at(other_dir,other_name,i,true)
            if a!=b { equal=false;break }
        } }
        if equal { if pkg { return entry(&h.base.index,other).directory };return -1 }
        slot=(slot+1)&(len(h.modules)-1)
    }
    return -1
}

live_open :: proc(index_path,pin,archive: string, local: bool, budget: u64) -> (^Live_Handle,i32) {
    h:=new(Live_Handle);success:=false
    defer if !success { live_destroy(h) }
    mapping,status:=map_checked(index_path)
    if status!=.Ok { return nil,i32(status) }
    h.base.index.mapping=mapping;data:=mapping.data
    integrity_begin:=time.tick_now()
    actual:=hex(hash(data));defer delete(actual)
    if actual!=pin { return nil,i32(Status.Index_Digest) }
    h.integrity_seconds+=time.duration_seconds(time.tick_since(integrity_begin))
    validation_begin:=time.tick_now()
    if len(data)<128 || string(data[:8])!="GAIAIDX\x00" || le(data,8,4)!=1 || le(data,12,4)!=0 { return nil,i32(Status.Format) }
    n,d,pool:=le(data,104,8),le(data,112,8),le(data,120,8)
    if n>u64(len(data))/28 || d==0 || d>u64(len(data))/4 { return nil,i32(Status.Format) }
    cursor:=128+28*int(n)+4*int(d)
    if cursor>len(data) || pool!=u64(len(data)-cursor) { return nil,i32(Status.Format) }
    size,end:=le(data,16,8),le(data,24,8)
    if size>0x7fffffffffffffff || end>size { return nil,i32(Status.Format) }
    slots,dirslots:=live_capacity(int(n)),live_capacity(int(d))
    required:=24*n+48*d+16*u64(slots)+8*u64(dirslots)
    if required>budget || budget>0x7fffffffffffffff || budget==0 { return nil,10 }
    ptr:=posix.mmap(nil,c.size_t(budget),{.READ,.WRITE},{.PRIVATE,.ANONYMOUS},-1,0)
    if ptr==posix.MAP_FAILED { return nil,i32(Status.IO) }
    h.arena=([^]u8)(ptr)[:int(budget)]
    h.base.index.count,h.base.index.archive_size,h.base.index.payload_end=int(n),int(size),int(end)
    region:=live_take(h,16*int(d));h.base.index.directories=([^]string)(raw_data(region))[:int(d)]
    h.base.index.name_starts=live_ints(h,int(n))
    h.files=live_ints(h,slots);h.modules=live_ints(h,slots);h.dirs=live_ints(h,dirslots)
    h.file_heads=live_ints(h,int(d));h.module_heads=live_ints(h,int(d))
    h.file_counts=live_ints(h,int(d));h.module_counts=live_ints(h,int(d))
    h.file_next=live_ints(h,int(n));h.module_next=live_ints(h,int(n))
    for i in 0..<int(d) {
        length:=int(le(data,128+28*int(n)+4*i,4))
        if length>len(data)-cursor { return nil,i32(Status.Format) }
        name:=string(data[cursor:cursor+length])
        if !utf8.valid_string(name) || strings.contains(name,"\x00") { return nil,i32(Status.Format) }
        slot:=int(live_hash(name)&u64(dirslots-1))
        for h.dirs[slot]!=0 {
            if h.base.index.directories[h.dirs[slot]-1]==name { return nil,i32(Status.Format) }
            slot=(slot+1)&(dirslots-1)
        }
        h.base.index.directories[i]=name;h.dirs[slot]=i+1;cursor+=length
    }
    if h.base.index.directories[0]!="" { return nil,i32(Status.Format) }
    previous:u64
    for i in 0..<int(n) {
        p:=128+28*i
        start,length:=le(data,p,8),le(data,p+8,8);name_length:=int(le(data,p+24,4));directory:=le(data,p+20,4)
        if start>end || length>end-start || start<previous || directory>=d || name_length==0 || name_length>len(data)-cursor { return nil,i32(Status.Format) }
        name:=string(data[cursor:cursor+name_length])
        if !utf8.valid_string(name) || strings.contains(name,"\x00") { return nil,i32(Status.Format) }
        h.base.index.name_starts[i]=cursor;cursor+=name_length;previous=start+length
    }
    if cursor!=len(data) { return nil,i32(Status.Format) }
    h.validation_seconds=time.duration_seconds(time.tick_since(validation_begin))
    construction_begin:=time.tick_now()
    for i in 0..<int(n) {
        if !live_insert(h,i,false) { return nil,i32(Status.Format) }
        length,_:=live_length(h,i,true)
        if length>=0 {
            if !live_insert(h,i,true) { return nil,11 }
            h.module_total+=1
        }
    }
    for i in 0..<int(n) {
        e:=entry(&h.base.index,i);directory:=e.directory
        h.file_next[i]=h.file_heads[directory];h.file_heads[directory]=i+1;h.file_counts[directory]+=1
        length,_:=live_length(h,i,true)
        if length<0 { continue }
        if e.directory==0 && (e.name=="__init__.py" || e.name=="__init__.pyc") { continue }
        directory=live_parent(h,i)
        if directory<0 { continue }
        h.module_next[i]=h.module_heads[directory];h.module_heads[directory]=i+1;h.module_counts[directory]+=1
    }
    bundle,err:=map_checked(archive)
    if err!=.Ok { return nil,i32(err) }
    h.base.bundle=bundle
    h.construction_seconds=time.duration_seconds(time.tick_since(construction_begin))
    integrity_begin=time.tick_now()
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
    h.integrity_seconds+=time.duration_seconds(time.tick_since(integrity_begin))
    success=true;return h,0
}

@(export)
gaia_live_open :: proc "c" (index,pin,archive:cstring,local:i32,budget:u64,out:^rawptr) -> i32 {
    context=runtime.default_context();h,status:=live_open(string(index),string(pin),string(archive),local!=0,budget);out^=h;return status
}
@(export)
gaia_live_close :: proc "c" (handle:rawptr) { context=runtime.default_context();live_destroy((^Live_Handle)(handle)) }
@(export)
gaia_live_lookup :: proc "c" (handle:rawptr,name:cstring,kind:i32) -> i64 {
    context=runtime.default_context();h:=(^Live_Handle)(handle)
    if kind==2 { return i64(live_dir(h,string(name))) }
    return i64(live_find(h,string(name),kind==1))
}
@(export)
gaia_live_name :: proc "c" (handle:rawptr,row:u64,dir,name:^[^]u8,dl,nl:^u64,is_pkg:^i32) -> i32 {
    context=runtime.default_context();h:=(^Live_Handle)(handle)
    if row>=u64(h.base.index.count) { return 9 }
    e:=entry(&h.base.index,int(row));d:=h.base.index.directories[e.directory]
    dir^=raw_data(d);name^=raw_data(e.name);dl^=u64(len(d));nl^=u64(len(e.name))
    _,p:=live_length(h,int(row),true);is_pkg^=0;if p { is_pkg^=1 };return 0
}
@(export)
gaia_live_stats :: proc "c" (handle:rawptr,out:^[6]u64) {
    context=runtime.default_context();h:=(^Live_Handle)(handle)
    out^={u64(h.base.index.count),u64(len(h.base.index.directories)),u64(h.module_total),u64(h.used),u64(len(h.arena)),u64(size_of(Live_Handle))}
}
@(export)
gaia_live_children :: proc "c" (handle:rawptr,directory:u64,kind:i32,head,count:^i64) -> i32 {
    context=runtime.default_context();h:=(^Live_Handle)(handle)
    if directory>=u64(live_len(h,3)) { return 9 }
    head^=i64(live_value(h,3,int(directory)))-1;count^=i64(live_value(h,5,int(directory)))
    if kind==1 { head^=i64(live_value(h,4,int(directory)))-1;count^=i64(live_value(h,6,int(directory))) }
    return 0
}
@(export)
gaia_live_next :: proc "c" (handle:rawptr,row:u64,kind:i32) -> i64 {
    context=runtime.default_context();h:=(^Live_Handle)(handle)
    if row>=u64(h.base.index.count) { return -1 }
    if kind==1 { return i64(live_value(h,8,int(row)))-1 };return i64(live_value(h,7,int(row)))-1
}
@(export)
gaia_live_dir_name :: proc "c" (handle:rawptr,directory:u64,out:^[^]u8,length:^u64) -> i32 {
    context=runtime.default_context();h:=(^Live_Handle)(handle)
    if directory>=u64(len(h.base.index.directories)) { return 9 }
    name:=h.base.index.directories[directory];out^=raw_data(name);length^=u64(len(name));return 0
}
@(export)
gaia_live_subdir :: proc "c" (handle:rawptr,parent,cursor:u64) -> i64 {
    context=runtime.default_context();h:=(^Live_Handle)(handle)
    if parent>=u64(len(h.base.index.directories)) { return -1 }
    prefix:=h.base.index.directories[parent]
    for i:=int(min(cursor,u64(len(h.base.index.directories))));i<len(h.base.index.directories);i+=1 {
        name:=h.base.index.directories[i]
        if len(name)>len(prefix) && strings.has_prefix(name,prefix) {
            rest:=name[len(prefix):]
            if !strings.contains(rest[:len(rest)-1],"/") { return i64(i) }
        }
    }
    return -1
}
@(export)
gaia_live_export :: proc "c" (handle:rawptr,out:^[^]u8,length:^u64) {
    context=runtime.default_context();h:=(^Live_Handle)(handle)
    skip:=16*len(h.base.index.directories)
    out^=raw_data(h.arena[skip:h.used]);length^=u64(h.used-skip)
}
@(export)
gaia_live_phases :: proc "c" (handle:rawptr,out:^[3]f64) {
    context=runtime.default_context();h:=(^Live_Handle)(handle)
    out^={h.integrity_seconds,h.validation_seconds,h.construction_seconds}
}

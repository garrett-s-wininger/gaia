// Linux-only bounded batch verifier. No retained state and no Odin allocator.
package conditions
import "core:c"
import "base:runtime"
import "core:sys/posix"
foreign import crypto "system:crypto"
foreign crypto {
    EVP_MD_CTX_new :: proc() -> rawptr ---
    EVP_MD_CTX_free :: proc(ctx: rawptr) ---
    EVP_sha256 :: proc() -> rawptr ---
    EVP_DigestInit_ex :: proc(ctx,md,engine: rawptr) -> c.int ---
    EVP_DigestUpdate :: proc(ctx,data: rawptr,size: c.size_t) -> c.int ---
    EVP_DigestFinal_ex :: proc(ctx: rawptr,out: ^[32]u8,size: ^c.uint) -> c.int ---
}
le :: proc(data: []u8, at: int) -> u64 {v:u64;for i in 0..<8 {v|=u64(data[at+i])<<u64(i*8)};return v}
put :: proc(data: []u8, at:int,value:u64) {for i in 0..<8 {data[at+i]=u8(value>>u64(i*8))}}
now :: proc() -> u64 {s:posix.timespec;posix.clock_gettime(.MONOTONIC,&s);return u64(s.tv_sec)*1_000_000_000+u64(s.tv_nsec)}
finish_hash :: proc(ctx:rawptr) -> ([32]u8,bool) {d:[32]u8;n:c.uint;ok:=EVP_DigestFinal_ex(ctx,&d,&n)==1 && n==32;return d,ok}
same :: proc(a,b:posix.stat_t) -> bool {return a.st_dev==b.st_dev && a.st_ino==b.st_ino && a.st_size==b.st_size && a.st_mtim==b.st_mtim && a.st_ctim==b.st_ctim && a.st_mode==b.st_mode}
// mode 0: stat records (32 bytes per index row), mode 1: complete GAIACQ01.
// Caller owns buffers, supplies their valid extents, and discards output on error.
@(export)
gaia_condition_verify :: proc "c"(input:[^]u8,input_size:u64,output:[^]u8,capacity:u64,mode:u32,metrics:[^]u64) -> c.int {
    context=runtime.default_context()
    started:=now();for i in 0..<7 {metrics[i]=0}
    if input==nil || output==nil || input_size<48 || input_size>8*1024*1024 || mode>1 {return 1}
    data:=input[:int(input_size)];if string(data[:8])!="GAIACQ01" {return 2}
    count:=le(data,8);if count>65536 {return 3}
    required:=count*32;if mode==1 {required=input_size};if capacity<required {return 4}
    out:=output[:int(required)]
    if mode==1 {copy(out,data)}
    ctx:=EVP_MD_CTX_new();if ctx==nil {return 5};defer EVP_MD_CTX_free(ctx)
    scratch:[65536]u8;name:[4097]u8;at:=16
    for row in 0..<int(count) {
        if at>len(data)-32-17 {return 6}
        kind:=data[at];jobs:=le(data,at+1);length:=le(data,at+9);at+=17
        if kind>3 || jobs==0 || length==0 || length>4096 || length>u64(len(data)-32-at) {return 7}
        path:=data[at:at+int(length)];at+=int(length)
        if path[0]!='/' || at>len(data)-32-64 {return 8}
        for b in path {if b==0 {return 9}}
        patch:=at;at+=64
        if kind!=1 {continue}
        size:=le(data,patch);if size>64*1024*1024 {return 10}
        copy(name[:],path);name[len(path)]=0;cstring_path:=cstring(raw_data(name[:]))
        before:posix.stat_t;if posix.stat(cstring_path,&before)!=nil || before.st_size<0 || u64(before.st_size)!=size {return 11}
        // Avoid blocking on FIFOs/devices; regular-file symlinks retain follow semantics.
        if (transmute(u32)before.st_mode&0o170000)!=0o100000 {return 12}
        fd:=posix.open(cstring_path,{.CLOEXEC,.NONBLOCK});if fd<0 {return 13}
        okay:=true
        if EVP_DigestInit_ex(ctx,EVP_sha256(),nil)!=1 {posix.close(fd);return 14}
        total:u64
        for {
            begin:=now();n:=posix.read(fd,raw_data(scratch[:]),len(scratch));metrics[2]+=now()-begin
            if n<0 {okay=false;break};if n==0 {break}
            total+=u64(n);if total>size {okay=false;break}
            begin=now();hashed:=EVP_DigestUpdate(ctx,raw_data(scratch[:]),c.size_t(n))==1;metrics[3]+=now()-begin
            if !hashed {okay=false;break}
        }
        after_fd:posix.stat_t;after_path:posix.stat_t
        stable:=posix.fstat(fd,&after_fd)==nil && posix.stat(cstring_path,&after_path)==nil && same(before,after_fd) && same(before,after_path)
        closed:=posix.close(fd)==nil
        digest,valid:=finish_hash(ctx)
        if !okay || !stable || !closed || !valid || total!=size {return 15}
        for b,i in digest {if b!=data[patch+32+i] {return 16}}
        begin:=now();target:=patch;if mode==0 {target=row*32}
        put(out,target,size);put(out,target+8,u64(before.st_mtim.tv_sec));put(out,target+16,u64(before.st_mtim.tv_nsec));put(out,target+24,u64(transmute(u32)before.st_mode))
        metrics[4]+=now()-begin;metrics[0]+=1;metrics[1]+=total
    }
    if at!=len(data)-32 {return 17}
    if mode==1 {
        begin:=now()
        if EVP_DigestInit_ex(ctx,EVP_sha256(),nil)!=1 || EVP_DigestUpdate(ctx,raw_data(out),c.size_t(len(out)-32))!=1 {return 18}
        digest,ok:=finish_hash(ctx);if !ok {return 19};copy(out[len(out)-32:],digest[:]);metrics[4]+=now()-begin
    }
    metrics[5]=now()-started;metrics[6]=required;return 0
}

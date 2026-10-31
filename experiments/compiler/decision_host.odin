// Lightweight Linux receipt validation; deliberately links no compiler libraries.
package main
import "core:c"
import "core:crypto/sha2"
import "core:fmt"
import vmem "core:mem/virtual"
import "core:os"
import "core:slice"
import "core:strings"
import "core:sys/posix"

Digest :: [32]u8
number :: proc(h: ^sha2.Context_256,n: u64) {
    b: [8]u8;for i in 0..<8 {b[i]=u8(n>>u64(8*i))};sha2.update(h,b[:])
}
hash :: proc(data: []u8) -> Digest {h: sha2.Context_256;sha2.init_256(&h);sha2.update(&h,data);d: Digest;sha2.final(&h,d[:]);return d}
hex :: proc(d: Digest) -> string {
    out:=make([]u8,64);chars:="0123456789abcdef"
    for b,i in d {out[2*i]=chars[b>>4];out[2*i+1]=chars[b&15]};return string(out)
}
read_file :: proc(path: string,limit: i64) -> ([]u8,bool) {
    f,e:=os.open(path);if e!=nil {return nil,false};defer os.close(f)
    n,err:=os.file_size(f);if err!=nil || n<0 || n>limit {return nil,false}
    data,re:=os.read_entire_file(f,context.allocator);return data,re==nil
}
paths :: proc(path: string) -> ([]string,bool) {
    data,ok:=read_file(path,4*1024*1024);if !ok {return nil,false}
    // Strings borrow data, retained for this short-lived process.
    lines:=strings.split_lines(string(data));if len(lines)<2 || lines[0]!="GAIA-WATCH-1" {return nil,false}
    out:=make([dynamic]string)
    for line in lines[1:] {
        if len(line)==0 {continue}
        if line[0]!='/' || strings.contains(line,"\x00") {return nil,false}
        append(&out,line)
    }
    if len(out)<1 || len(out)>100000 {return nil,false};return out[:],true
}
stat :: proc(path: string) -> (posix.stat_t,bool) {
    name:=strings.clone_to_cstring(path);defer delete(name);s: posix.stat_t
    e:=posix.stat(name,&s);return s,e==nil
}
stamp :: proc(names: []string) -> (Digest,bool) {
    h: sha2.Context_256;sha2.init_256(&h)
    for path in names {
        s,ok:=stat(path);if !ok {return {},false}
        number(&h,u64(len(path)));sha2.update(&h,transmute([]u8)path)
        number(&h,u64(s.st_size));number(&h,u64(s.st_mtim.tv_sec));number(&h,u64(s.st_mtim.tv_nsec))
        number(&h,u64(transmute(u32)s.st_mode))
    }
    d: Digest;sha2.final(&h,d[:]);return d,true
}
put :: proc(data: ^[dynamic]u8,n: u64) {for i in 0..<8 {append(data,u8(n>>u64(8*i)))}}
get :: proc(data: []u8,at: ^int) -> (u64,bool) {
    if at^<0 || at^>len(data)-8 {return 0,false}
    n: u64;for i in 0..<8 {n|=u64(data[at^+i])<<u64(8*i)};at^+=8;return n,true
}
atomic_write :: proc(path: string,data: []u8) -> bool {
    tmp:=fmt.aprintf("%s.tmp.%d",path,posix.getpid());defer delete(tmp)
    f,e:=os.open(tmp,{.Write,.Create,.Excl},{.Read_User,.Write_User});if e!=nil {return false}
    okay:=true;at:=0
    for at<len(data) {n,err:=os.write(f,data[at:]);if err!=nil || n<=0 {okay=false;break};at+=n}
    if os.close(f)!=nil {okay=false};if okay {okay=os.rename(tmp,path)==nil};if !okay {os.remove(tmp)};return okay
}
check :: proc(path,request: string,input: Digest,outputs: []string) -> bool {
    data,ok:=read_file(path,1024*1024);if !ok {return false};defer delete(data)
    if len(data)<144 || string(data[:8])!="GAIASK01" || string(data[8:72])!=request {return false}
    stored: Digest;copy(stored[:],data[72:104]);if stored!=input {return false}
    copy(stored[:],data[len(data)-32:]);if hash(data[:len(data)-32])!=stored {return false}
    body:=data[:len(data)-32];at:=104;n,valid:=get(body,&at);if !valid || n!=u64(len(outputs)) {return false}
    for name in outputs {
        length,o:=get(body,&at);if !o || length>4096 || length>u64(len(body)-at) {return false}
        if string(body[at:at+int(length)])!=name {return false};at+=int(length)
        size,a:=get(body,&at);sec,b:=get(body,&at);ns,c:=get(body,&at)
        if !a || !b || !c || at>len(body)-32 {return false}
        digest: Digest;copy(digest[:],body[at:at+32]);at+=32
        s,exists:=stat(name);if !exists {return false}
        if u64(s.st_size)!=size || u64(s.st_mtim.tv_sec)!=sec || u64(s.st_mtim.tv_nsec)!=ns {
            bytes,read:=read_file(name,64*1024*1024)
            if !read {return false};matches:=hash(bytes)==digest;delete(bytes);if !matches {return false}
        }
    }
    return at==len(body)
}
record :: proc(path,request: string,input: Digest,outputs: []string) -> bool {
    data:=make([dynamic]u8);defer delete(data)
    input_hash:=input
    append(&data,"GAIASK01");append(&data,request);append(&data,..input_hash[:]);put(&data,u64(len(outputs)))
    for name in outputs {
        before,ok:=stat(name);bytes,read:=read_file(name,64*1024*1024)
        if !ok || !read {return false}
        digest:=hash(bytes);delete(bytes);after,exists:=stat(name)
        if !exists || before.st_size!=after.st_size || before.st_mtim!=after.st_mtim {return false}
        put(&data,u64(len(name)));append(&data,..transmute([]u8)name)
        put(&data,u64(after.st_size));put(&data,u64(after.st_mtim.tv_sec));put(&data,u64(after.st_mtim.tv_nsec));append(&data,..digest[:])
    }
    digest:=hash(data[:]);append(&data,..digest[:]);return atomic_write(path,data[:])
}
decision_request :: proc(args: []string) {
    if len(args)>1 && strings.has_prefix(args[1],"selective-") {selective_main(args);return}
    if len(args)<6 || len(args)>7 {fmt.eprintln("decision check|record STATE REQUEST-SHA WATCHLIST OUTPUTLIST [EXPECTED-STAMP]");os.exit(2)}
    mode:=args[1];if mode!="check" && mode!="record" {os.exit(2)}
    request:=args[3];if len(request)!=64 {os.exit(2)}
    for b in request {if !(b>='0' && b<='9') && !(b>='a' && b<='f') {os.exit(2)}}
    inputs,okay:=paths(args[4]);outputs,valid:=paths(args[5]);if !okay || !valid || len(outputs)>64 {os.exit(2)}
    input,exists:=stamp(inputs);text:=hex(input);defer delete(text)
    if mode=="check" {
        hit:=exists && check(args[2],request,input,outputs)
        fmt.print("{");fmt.printf("\"hit\":%v,\"stamp\":\"%s\",\"inputs_present\":%v,\"stat_calls\":%d}\n",hit,text,exists,len(inputs));return
    }
    if len(args)!=7 {os.exit(2)}
    stable:=exists && args[6]==text
    saved:=stable && record(args[2],request,input,outputs)
    fmt.print("{");fmt.printf("\"recorded\":%v,\"inputs_unchanged\":%v}\n",saved,stable)
}

// The lightweight model is explicit regular files plus implicit directories,
// fixed virtual metadata, per-job visibility and canonical absolute paths.
// Physical host existence never decides a virtual negative lookup.
Node :: struct {file,dir: u64, declared_file,declared_dir: bool}
Child :: struct {name: string, file,dir: u64}
Namespace :: struct {nodes: map[string]Node, children: map[string][dynamic]Child, files: [dynamic]string}
Condition :: struct {kind: u8, jobs: u64, name: string, size,sec,ns,mode: u64, digest: Digest}
Conditions :: struct {items: []Condition, digest: Digest}
valid_virtual :: proc(name: string) -> bool {
    return len(name)>0 && len(name)<=4096 && name[0]=='/' &&
        (name=="/" || !strings.has_suffix(name,"/")) &&
        !strings.contains(name,"//") && !strings.contains(name,"/./") && !strings.contains(name,"/../") &&
        !strings.has_suffix(name,"/.") && !strings.has_suffix(name,"/..") &&
        !strings.contains(name,"\\") && !strings.contains(name,"\x00")
}
name_at :: proc(body: []u8,at: ^int) -> (string,bool) {
    length,ok:=get(body,at);if !ok || length>4096 || at^>len(body) || length>u64(len(body)-at^) {return "",false}
    name:=string(body[at^:at^+int(length)]);at^+=int(length);return name,valid_virtual(name)
}
read_namespace :: proc(path: string) -> (Namespace,bool) {
    data,ok:=read_file(path,4*1024*1024);if !ok || len(data)<16 || string(data[:8])!="GAIANS01" {return {},false}
    at:=8;count,valid:=get(data,&at);if !valid || count<1 || count>100000 {return {},false}
    out:=Namespace{nodes=make(map[string]Node),children=make(map[string][dynamic]Child)}
    out.nodes["/"]=Node{dir=~u64(0),declared_dir=true}
    for _ in 0..<int(count) {
        name,a:=name_at(data,&at);mask,b:=get(data,&at);if !a || !b || name=="/" {return {},false}
        node:=out.nodes[name];if node.declared_file {return {},false}
        node.file|=mask;node.declared_file=true;out.nodes[name]=node;append(&out.files,name)
        root:=out.nodes["/"];root.dir|=mask;root.declared_dir=true;out.nodes["/"]=root
        for i in 1..<len(name) {if name[i]=='/' {
            parent:=name[:i];n:=out.nodes[parent];n.dir|=mask;n.declared_dir=true;out.nodes[parent]=n
        }}
        if len(out.nodes)>200000 {return {},false}
    }
    if at!=len(data) {return {},false}
    for name,n in out.nodes {
        if n.declared_file && n.declared_dir {return {},false}
        if name!="/" {
            i:=strings.last_index(name,"/");parent:="/";if i>0 {parent=name[:i]}
            children:=out.children[parent];append(&children,Child{name,n.file,n.dir});out.children[parent]=children
        }
    }
    for _,&children in out.children {slice.sort_by(children[:],proc(a,b: Child) -> bool {return a.name<b.name})}
    return out,true
}
read_conditions :: proc(path: string) -> (Conditions,bool) {
    data,ok:=read_file(path,8*1024*1024);if !ok || len(data)<48 || string(data[:8])!="GAIACQ01" {return {},false}
    body:=data[:len(data)-32];digest: Digest;copy(digest[:],data[len(data)-32:])
    if hash(body)!=digest {return {},false}
    at:=8;count,valid:=get(body,&at);if !valid || count<1 || count>65536 {return {},false}
    out:=Conditions{items=make([]Condition,int(count)),digest=digest}
    for &item in out.items {
        if at>=len(body) {return {},false};item.kind=body[at];at+=1
        jobs,a:=get(body,&at);name,b:=name_at(body,&at)
        size,c:=get(body,&at);sec,d:=get(body,&at);ns,e:=get(body,&at);mode,f:=get(body,&at)
        if !a || !b || !c || !d || !e || !f || item.kind>3 || jobs==0 || size>64*1024*1024 || ns>=1000000000 || at>len(body)-32 {return {},false}
        item.jobs=jobs;item.name=name;item.size=size;item.sec=sec;item.ns=ns;item.mode=mode
        copy(item.digest[:],body[at:at+32]);at+=32
    }
    return out,at==len(body)
}
listing :: proc(ns: Namespace,name: string,bit: u64) -> Digest {
    h: sha2.Context_256;sha2.init_256(&h);sha2.update(&h,transmute([]u8)string("GAIA-LIST-1"))
    children:=ns.children[name];count: u64
    for child in children {if (child.file|child.dir)&bit!=0 {count+=1}}
    number(&h,count)
    for child in children {
        kind: u8;if child.file&bit!=0 {kind=1} else if child.dir&bit!=0 {kind=2} else {continue}
        number(&h,u64(len(child.name)));sha2.update(&h,transmute([]u8)child.name)
        sha2.update(&h,([]u8){kind})
    }
    digest: Digest;sha2.final(&h,digest[:]);return digest
}
match_conditions :: proc(ns: Namespace,index: Conditions) -> (bool,int,int) {
    stats,hashes: int
    for item in index.items {
        node:=ns.nodes[item.name]
        switch item.kind {
        case 0: if (node.file|node.dir)&item.jobs!=0 {return false,stats,hashes}
        case 1:
            if node.file&item.jobs!=item.jobs {return false,stats,hashes}
            s,exists:=stat(item.name);stats+=1;if !exists {return false,stats,hashes}
            if u64(s.st_size)!=item.size || u64(s.st_mtim.tv_sec)!=item.sec || u64(s.st_mtim.tv_nsec)!=item.ns || u64(transmute(u32)s.st_mode)!=item.mode {
                data,okay:=read_file(item.name,64*1024*1024);if !okay {return false,stats,hashes}
                same:=hash(data)==item.digest;delete(data);hashes+=1;if !same {return false,stats,hashes}
            }
        case 2: if node.dir&item.jobs!=item.jobs {return false,stats,hashes}
        case 3:
            if node.dir&item.jobs!=item.jobs {return false,stats,hashes}
            for job in 0..<64 {
                bit:=u64(1)<<u64(job);if item.jobs&bit!=0 && listing(ns,item.name,bit)!=item.digest {return false,stats,hashes}
            }
        }
    }
    return true,stats,hashes
}
selective_identity :: proc(index: Conditions,tools: Digest) -> Digest {
    h: sha2.Context_256;sha2.init_256(&h);i:=index.digest;t:=tools
    sha2.update(&h,i[:]);sha2.update(&h,t[:]);out: Digest;sha2.final(&h,out[:]);return out
}
selective_main :: proc(args: []string) {
    if len(args)!=8 && len(args)!=9 {os.exit(2)}
    mode:=args[1];history:=mode=="selective-history-check"
    if mode!="selective-check" && mode!="selective-record" && !history {os.exit(2)}
    request:=args[3];if len(request)!=64 {os.exit(2)}
    tools,okay:=paths(args[4]);outputs,valid:=paths(args[5]);ns,namespace_ok:=read_namespace(args[6])
    if !okay || !valid || !namespace_ok || len(outputs)>64 {os.exit(2)}
    index,index_ok:=read_conditions(args[7])
    before: Digest;before_present:=true
    if history {
        names:=make([dynamic]string);append(&names,..ns.files[:]);append(&names,..tools)
        before,before_present=stamp(names[:]);delete(names)
    }
    tool_stamp,tools_exist:=stamp(tools)
    matches:=false;stats,hashes: int
    if index_ok {matches,stats,hashes=match_conditions(ns,index)}
    identity:=selective_identity(index,tool_stamp)
    if mode=="selective-check" || history {
        hit:=index_ok && matches && tools_exist && check(args[2],request,identity,outputs)
        // Full preflight is needed only for a miss which will run the pipeline.
        full: Digest;present:=true
        if !hit || history {
            names:=make([dynamic]string);append(&names,..ns.files[:]);append(&names,..tools)
            full,present=stamp(names[:]);delete(names)
        }
        if history {hit=hit && before_present && present && before==full}
        text:=hex(full);defer delete(text)
        fmt.print("{");fmt.printf("\"hit\":%v,\"stamp\":\"%s\",\"inputs_present\":%v,\"positive_stats\":%d,\"content_hashes\":%d,\"conditions\":%d}\n",hit,text,present,stats,hashes,len(index.items));return
    }
    if len(args)!=9 {os.exit(2)}
    names:=make([dynamic]string);append(&names,..ns.files[:]);append(&names,..tools)
    full,present:=stamp(names[:]);text:=hex(full);defer delete(text)
    stable:=present && text==args[8]
    saved:=stable && tools_exist && index_ok && matches && record(args[2],request,identity,outputs)
    fmt.print("{");fmt.printf("\"recorded\":%v,\"inputs_unchanged\":%v,\"conditions_valid\":%v}\n",saved,stable,index_ok && matches)
}


// Optional serial checker. All request allocations live in a fixed reservation
// and are reset before acknowledgement; no namespace/condition state survives.
checker_read :: proc(data: []u8,eof_ok: bool=false) -> bool {
    at:=0
    for at<len(data) {
        remaining:=len(data)-at;n:=posix.read(0,raw_data(data[at:]),c.size_t(remaining))
        if n==0 && at==0 && eof_ok {return false}
        if n<=0 {os.exit(3)};at+=int(n)
    }
    return true
}
checker_u32 :: proc(data: []u8,at: ^int) -> int {
    if at^>len(data)-4 {os.exit(3)}
    n: u32;for i in 0..<4 {n|=u32(data[at^+i])<<u32(i*8)};at^+=4;return int(n)
}
checker_scoped :: proc(args: []string,arena: ^vmem.Arena) {
    previous:=context.allocator;temporary:=context.temp_allocator
    context.allocator=vmem.arena_allocator(arena);context.temp_allocator=context.allocator
    defer {context.allocator=previous;context.temp_allocator=temporary}
    decision_request(args)
}
main :: proc() {
    if len(os.args)!=2 || os.args[1]!="--serve" {decision_request(os.args);return}
    arena: vmem.Arena
    if vmem.arena_init_static(&arena,reserved=64*1024*1024,commit_size=64*1024)!=nil {os.exit(3)}
    defer vmem.arena_destroy(&arena)
    for {
        header: [8]u8;if !checker_read(header[:],true) {break}
        at:=0;size,okay:=get(header[:],&at);if !okay || size<4 || size>4*1024*1024 {os.exit(3)}
        body:=make([]u8,int(size));checker_read(body);at=0
        count:=checker_u32(body,&at);if count<2 || count>64 {os.exit(3)}
        args:=make([]string,count)
        for &arg in args {
            n:=checker_u32(body,&at);if n>65536 || at>len(body)-n {os.exit(3)}
            arg=string(body[at:at+n]);at+=n;if strings.contains(arg,"\x00") {os.exit(3)}
        }
        if at!=len(body) {os.exit(3)}
        checker_scoped(args,&arena);used:=arena.total_used
        vmem.arena_free_all(&arena);delete(args);delete(body)
        fmt.printf("GAIA-DONE %d %d\n",used,arena.total_reserved)
    }
}

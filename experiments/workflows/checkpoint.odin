// Experimental admitted-input checkpoint store, not the source-control MVP.
// Single caller, private repository, no automatic discovery or reclamation.
package main
import "core:crypto/sha2"
import "core:encoding/hex"
import "core:fmt"
import "core:os"
import "core:strings"
import "core:sys/posix"

fail :: proc(message: string) {fmt.eprintln(message);os.exit(3)}
digest :: proc(data: []u8) -> string {
    h: sha2.Context_256;sha2.init_256(&h);sha2.update(&h,data);out: [32]u8;sha2.final(&h,out[:])
    return string(hex.encode(out[:]))
}
path_join :: proc(a,b: string) -> string {return fmt.aprintf("%s/%s",a,b)}
flush_dir :: proc(path: string) {
    name:=strings.clone_to_cstring(path);defer delete(name)
    fd:=posix.open(name,{.DIRECTORY,.CLOEXEC});if fd<0 {fail("directory open failed")};defer posix.close(fd)
    if posix.fsync(fd)!=nil {fail("directory sync failed")}
}
durable_write :: proc(path: string,data: []u8) {
    file,e:=os.open(path,{.Write,.Create,.Excl});if e!=nil {fail("exclusive create failed")}
    offset:=0
    for offset<len(data) {n,err:=os.write(file,data[offset:]);if err!=nil || n<=0 {fail("write failed")};offset+=n}
    if os.sync(file)!=nil {fail("file sync failed")}
    if os.close(file)!=nil {fail("close failed")}
}
put :: proc(store,kind: string,data: []u8) -> string {
    // Domain separation is part of content identity, independent of filenames.
    typed:=make([dynamic]u8);defer delete(typed)
    append(&typed,..transmute([]u8)kind);append(&typed,0);append(&typed,..data)
    id:=digest(typed[:]);path:=path_join(store,id);defer delete(path)
    if os.is_file(path) {
        old,e:=os.read_entire_file(path,context.allocator);if e!=nil {fail("object read failed")};defer delete(old)
        observed:=digest(old);defer delete(observed)
        if observed!=id {fail("corrupt retained object")}
        return id
    }
    temporary:=path_join(store,"pending-object");defer delete(temporary)
    durable_write(temporary,typed[:])
    if os.rename(temporary,path)!=nil {fail("object rename failed")}
    return id
}
read_u64 :: proc(data: []u8,offset: ^int) -> u64 {
    if offset^>len(data)-8 {fail("truncated input")};n:u64
    for j in 0..<8 {n|=u64(data[offset^+j])<<u64(8*j)};offset^+=8;return n
}
append_u64 :: proc(data: ^[dynamic]u8,n:u64) {for j in 0..<8 {append(data,u8(n>>u64(8*j)))}}
take :: proc(data: []u8,offset:^int,n:u64) -> []u8 {
    if n>u64(len(data)-offset^) {fail("truncated field")};result:=data[offset^:offset^+int(n)];offset^+=int(n);return result
}
valid_name :: proc(name:string) -> bool {
    if name=="" || strings.has_prefix(name,"/") || strings.contains(name,"\x00") {return false}
    parts:=strings.split(name,"/");defer delete(parts)
    for part in parts {if part=="" || part=="." || part==".." {return false}}
    return true
}
valid_id :: proc(id:string) -> bool {
    if len(id)!=64 {return false}
    for b in transmute([]u8)id {if !(b>='0' && b<='9') && !(b>='a' && b<='f') {return false}}
    return true
}
main :: proc() {
    if len(os.args)<4 {fmt.eprintln("checkpoint capture STORE BUNDLE EXPECTED-HEAD FAILPOINT | read STORE SNAPSHOT PATH");os.exit(2)}
    mode:=os.args[1];store:=os.args[2]
    if mode=="read" {
        if len(os.args)!=5 || !valid_id(os.args[3]) {os.exit(2)}
        snapshot_path:=path_join(store,os.args[3]);defer delete(snapshot_path)
        data,e:=os.read_entire_file(snapshot_path,context.allocator);if e!=nil {fail("missing snapshot")};defer delete(data)
        observed:=digest(data);defer delete(observed);if observed!=os.args[3] {fail("corrupt snapshot")}
        if len(data)<9 || string(data[:9])!="snapshot\x00" {fail("wrong snapshot type")}
        offset:=9;count:=read_u64(data,&offset);found:[]u8
        for _ in 0..<count {
            n:=read_u64(data,&offset);name:=take(data,&offset,n);id:=take(data,&offset,64)
            _=take(data,&offset,1)
            if string(name)==os.args[4] {found=id}
        }
        if offset!=len(data) || len(found)!=64 {fail("missing entry or invalid snapshot")}
        target:=path_join(store,string(found));defer delete(target)
        content,err:=os.read_entire_file(target,context.allocator);if err!=nil {fail("missing content")};defer delete(content)
        actual:=digest(content);defer delete(actual)
        if actual!=string(found) || len(content)<8 || string(content[:8])!="content\x00" {fail("corrupt content")}
        written,write_err:=os.write(os.stdout,content[8:]);if write_err!=nil || written!=len(content)-8 {fail("output failed")}
        return
    }
    if mode!="capture" || len(os.args)!=6 {os.exit(2)}
    if os.args[4]!="empty" && !valid_id(os.args[4]) {os.exit(2)}
    // The private repository directory is prepared outside operation timings.
    // One writer is admitted by an exclusive intent; crash recovery is explicit.
    lock:=path_join(store,"writer-intent");defer delete(lock)
    durable_write(lock,transmute([]u8)os.args[4]);defer os.remove(lock)
    head_path:=path_join(store,"HEAD");defer delete(head_path)
    head,e:=os.read_entire_file(head_path,context.allocator);defer delete(head)
    cause,general:=e.(os.General_Error)
    missing:=general && cause==.Not_Exist
    if e!=nil && (!missing || os.args[4]!="empty") {fail("expected head unavailable")}
    if e==nil && string(head)!=os.args[4] {fail("expected head changed")}
    input,err:=os.read_entire_file(os.args[3],context.allocator);if err!=nil {fail("input read failed")};defer delete(input)
    offset:=0;count:=read_u64(input,&offset);snapshot:=make([dynamic]u8);defer delete(snapshot);append_u64(&snapshot,count)
    previous:=""
    for _ in 0..<count {
        n:=read_u64(input,&offset);name:=take(input,&offset,n);flags:=take(input,&offset,1)
        if !valid_name(string(name)) || string(name)<=previous || flags[0]>1 {fail("invalid or unsorted namespace")}
        previous=string(name);size:=read_u64(input,&offset);content:=take(input,&offset,size)
        id:=put(store,"content",content);defer delete(id)
        append_u64(&snapshot,n);append(&snapshot,..name);append(&snapshot,..transmute([]u8)id);append(&snapshot,flags[0])
    }
    if offset!=len(input) {fail("trailing input")}
    id:=put(store,"snapshot",snapshot[:]);defer delete(id);flush_dir(store)
    if os.args[5]=="before-root" {os.exit(75)}
    pending:=path_join(store,"pending-head");defer delete(pending)
    durable_write(pending,transmute([]u8)id)
    if os.rename(pending,head_path)!=nil {fail("root rename failed")};flush_dir(store)
    if os.args[5]=="after-root" {os.exit(76)}
    fmt.println(id)
}

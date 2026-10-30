// Apply explicit content/membership events to a previously admitted collection.
package main
import "core:crypto/sha2"
import "core:fmt"
import "core:os"
import "core:slice"
import "core:strconv"
import "core:strings"
import "core:time"
import "core:sys/posix"
Digest :: [32]u8
Record :: struct {name: string, body: []u8, mask: u64, active, owned: bool}
fail :: proc() {fmt.eprintln("invalid snapshot input");os.exit(3)}
number :: proc(data: []u8,offset,n: int) -> u64 {
    if offset<0 || n<0 || n>8 || offset>len(data)-n {fail()}
    x: u64;for i in 0..<n {x|=u64(data[offset+i])<<u64(8*i)};return x
}
put_number :: proc(data: []u8,offset: int,x: u64,n: int) {for i in 0..<n {data[offset+i]=u8(x>>u64(8*i))}}
hash :: proc(data: []u8) -> Digest {h: sha2.Context_256;sha2.init_256(&h);sha2.update(&h,data);d: Digest;sha2.final(&h,d[:]);return d}
hex :: proc(d: Digest) -> string {out:=make([]u8,64);chars:="0123456789abcdef";for b,i in d {out[2*i]=chars[b>>4];out[2*i+1]=chars[b&15]};return string(out)}
read :: proc(path: string,limit: i64) -> []u8 {
    f,e:=os.open(path);if e!=nil {fail()};defer os.close(f)
    size,se:=os.file_size(f);if se!=nil || size<0 || size>limit {fail()}
    data,de:=os.read_entire_file(f,context.allocator);if de!=nil {fail()};return data
}
valid_name :: proc(name: string) -> bool {
    return len(name)>1 && len(name)<=4096 && name[0]=='/' && !strings.has_suffix(name,"/") &&
        !strings.contains(name,"//") && !strings.contains(name,"/./") && !strings.contains(name,"/../") &&
        !strings.has_suffix(name,"/.") && !strings.has_suffix(name,"/..") && !strings.contains(name,"\\") && !strings.contains(name,"\x00")
}
framed :: proc(data: []u8,offset,n: int) -> []u8 {
    if n<0 || offset<0 || offset>len(data)-n-1 || data[offset+n]!=0 {fail()};return data[offset:offset+n]
}
publish :: proc(path: string,data: []u8) {
    tmp:=fmt.aprintf("%s.tmp.%d",path,posix.getpid());defer delete(tmp)
    f,e:=os.open(tmp,{.Write,.Create,.Excl},{.Read_User,.Write_User});if e!=nil {fail()}
    okay:=true;offset:=0
    for offset<len(data) {n,err:=os.write(f,data[offset:]);if err!=nil || n<=0 {okay=false;break};offset+=n}
    if os.close(f)!=nil {okay=false};if okay {okay=os.rename(tmp,path)==nil}
    if !okay {os.remove(tmp);fail()}
}
main :: proc() {
    start:=time.tick_now()
    if len(os.args)!=9 {fmt.eprintln("snapshot full|delta BASE VIEWS DELTA OUT OUTVIEWS EXPECTED-PIN|- JOBS");os.exit(2)}
    mode:=os.args[1];if mode!="full" && mode!="delta" {os.exit(2)}
    jobs,okay:=strconv.parse_int(os.args[8]);if !okay || jobs<1 || jobs>64 {fail()}
    bits:=~u64(0);if jobs<64 {bits=(u64(1)<<u64(jobs))-1}
    base:=read(os.args[2],64*1024*1024);defer delete(base)
    views:=read(os.args[3],4*1024*1024);defer delete(views)
    patch:=read(os.args[4],64*1024*1024);defer delete(patch)
    if len(base)<16 || string(base[:8])!="GAIACIN2" || len(patch)<80 || string(patch[:8])!="GAIADP01" {fail()}
    expected: Digest;copy(expected[:],patch[8:40]);if hash(base)!=expected {fail()}
    copy(expected[:],patch[40:72]);if hash(views)!=expected {fail()}
    n:=int(number(base,8,8));if n<1 || n>100000 {fail()}
    fields:=strings.fields(string(views));defer delete(fields)
    if len(fields)!=n+1 || fields[0]!="GAIACV1" {fail()}
    records:=make([dynamic]Record,0,n);defer {for r in records {if r.owned {delete(r.body)}};delete(records)}
    indices:=make(map[string]int);defer delete(indices);offset:=16
    for i in 0..<n {
        nl:=int(number(base,offset,4));bs:=number(base,offset+4,8);offset+=12
        if bs>64*1024*1024 {fail()};name:=string(framed(base,offset,nl));offset+=nl+1
        body:=framed(base,offset,int(bs));offset+=int(bs)+1
        if !valid_name(name) {fail()};if _,exists:=indices[name];exists {fail()}
        mask,ok:=strconv.parse_uint(fields[i+1],10);if !ok || u64(mask)&~bits!=0 {fail()}
        indices[name]=len(records);append(&records,Record{name,body,u64(mask),true,false})
    }
    if offset!=len(base) {fail()}
    ops:=number(patch,72,8);if ops>100000 {fail()};seen:=make(map[string]bool);defer delete(seen);offset=80
    for _ in 0..<int(ops) {
        nl:=int(number(patch,offset,4));op:=number(patch,offset+4,1);mask:=number(patch,offset+5,8);bs:=number(patch,offset+13,8);offset+=21
        if bs>64*1024*1024 || mask&~bits!=0 {fail()}
        name:=string(framed(patch,offset,nl));offset+=nl+1;body:=framed(patch,offset,int(bs));offset+=int(bs)+1
        if !valid_name(name) || seen[name] {fail()};seen[name]=true
        index,exists:=indices[name]
        switch op {
        case 1:
            if exists {records[index].body=body;records[index].mask=mask}
            else {indices[name]=len(records);append(&records,Record{name,body,mask,true,false})}
        case 2:
            if !exists || bs!=0 || mask!=0 {fail()};records[index].active=false
        case: fail()
        }
    }
    if offset!=len(patch) || len(records)>100000 {fail()}
    loose_reads,loose_bytes: u64
    if mode=="full" {
        for &r in records {if r.active {r.body=read(r.name,64*1024*1024);r.owned=true;loose_reads+=1;loose_bytes+=u64(len(r.body))}}
    }
    slice.sort_by(records[:],proc(a,b: Record) -> bool {return a.name<b.name})
    total:=16;count:=0;view_text:=make([dynamic]u8);defer delete(view_text);append(&view_text,..transmute([]u8)string("GAIACV1\n"))
    for r in records {if r.active {
        total+=12+len(r.name)+1+len(r.body)+1;count+=1
        if total>64*1024*1024 {fail()}
        line:=fmt.aprintf("%d\n",r.mask);append(&view_text,..transmute([]u8)line);delete(line)
    }}
    out:=make([]u8,total);defer delete(out);copy(out[:8],"GAIACIN2");put_number(out,8,u64(count),8);offset=16
    for r in records {if r.active {
        put_number(out,offset,u64(len(r.name)),4);put_number(out,offset+4,u64(len(r.body)),8);offset+=12
        copy(out[offset:],r.name);offset+=len(r.name)+1;copy(out[offset:],r.body);offset+=len(r.body)+1
    }}
    pin:=hex(hash(out));defer delete(pin);mpin:=hex(hash(view_text[:]));defer delete(mpin)
    // Validate the optional expected result before changing any output.
    if os.args[7]!="-" && os.args[7]!=pin {fail()}
    publish(os.args[5],out);publish(os.args[6],view_text[:])
    fmt.print("{");fmt.printf("\"correct\":true,\"pin\":\"%s\",\"view_pin\":\"%s\",\"files\":%d,\"bytes\":%d,\"changed\":%d,\"loose_reads\":%d,\"loose_bytes\":%d,\"native_ns\":%d}\n",pin,mpin,count,total,ops,loose_reads,loose_bytes,time.duration_nanoseconds(time.tick_diff(start,time.tick_now())))
}

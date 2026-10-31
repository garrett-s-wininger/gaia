// Declared scalar ABI only; no pointers or mutable objects survive in a module.
package main
import "core:dynlib"
import "core:fmt"
import "core:os"
import "core:strconv"
import "core:strings"

Module :: struct {
    library: dynlib.Library,
    apply: proc "c" (input:i64,state:^i64)->i64,
    version:i64,
}
load :: proc(path:string,expected:i64)->(m:Module,ok:bool) {
    library,loaded:=dynlib.load_library(path)
    if !loaded {return {},false}
    abi_ptr,abi_found:=dynlib.symbol_address(library,"gaia_abi")
    version_ptr,version_found:=dynlib.symbol_address(library,"gaia_version")
    apply_ptr,apply_found:=dynlib.symbol_address(library,"gaia_apply")
    if !abi_found || !version_found || !apply_found {dynlib.unload_library(library);return {},false}
    abi:=cast(proc "c" ()->i64)abi_ptr
    version:=cast(proc "c" ()->i64)version_ptr
    if abi()!=1 || version()!=expected {dynlib.unload_library(library);return {},false}
    return Module{library,cast(proc "c" (input:i64,state:^i64)->i64)apply_ptr,version()},true
}
respond :: proc(ok:bool,m:Module,state,result:i64) {
    fmt.print("{");fmt.printf("\"ok\":%t,\"version\":%d,\"state\":%d,\"result\":%d",ok,m.version,state,result);fmt.println("}")
}
main :: proc() {
    if len(os.args)!=4 {os.exit(2)}
    version,ok:=strconv.parse_i64(os.args[2]);if !ok {os.exit(2)}
    state,okay:=strconv.parse_i64(os.args[3]);if !okay {os.exit(2)}
    current,loaded:=load(os.args[1],version);if !loaded {os.exit(3)}
    defer dynlib.unload_library(current.library)
    line:=make([dynamic]u8);defer delete(line)
    buffer:[1]u8
    for {
        n,err:=os.read(os.stdin,buffer[:]);if err!=nil || n==0 {break}
        if buffer[0]!='\n' {if len(line)>=4096 {os.exit(2)};append(&line,buffer[0]);continue}
        words:=strings.fields(string(line[:]))
        if len(words)==1 && words[0]=="stop" {delete(words);break}
        if len(words)==2 && words[0]=="run" {
            value,valid:=strconv.parse_i64(words[1]);if !valid {respond(false,current,state,0)}
            else {result:=current.apply(value,&state);respond(true,current,state,result)}
        } else if len(words)==3 && words[0]=="load" {
            expected,valid:=strconv.parse_i64(words[2])
            if !valid {respond(false,current,state,0)}
            else {
                candidate,valid_load:=load(words[1],expected)
                if !valid_load {respond(false,current,state,0)}
                else {old:=current;current=candidate;dynlib.unload_library(old.library);respond(true,current,state,0)}
            }
        } else {respond(false,current,state,0)}
        delete(words);clear(&line)
    }
}

package catalogue
import "base:runtime"
import "core:unicode/utf8"
read32 :: proc(b:[]u8,at:int)->u64 {v:u64;for i in 0..<4 {v|=u64(b[at+i])<<u64(i*8)};return v}
read64 :: proc(b:[]u8,at:int)->u64 {v:u64;for i in 0..<8 {v|=u64(b[at+i])<<u64(i*8)};return v}
@(export)
gaia_catalogue_query :: proc "c"(input:[^]u8,size:u64,output:[^]u64)->i32 {
    context=runtime.default_context()
    if input==nil || output==nil || size<24 || size>16*1024*1024 {return 1}
    b:=input[:int(size)];if string(b[:8])!="GACAT001" || read32(b,8)!=1 || read32(b,20)!=56 {return 2}
    count:=read32(b,12);strings:=read32(b,16)
    if count>100000 || 24+count*56+strings!=size {return 3}
    for i in 0..<6 {output[i]=0}
    start:=24+int(count)*56
    for row in 0..<int(count) {
        at:=24+row*56;length:=read64(b,at+8);off:=read32(b,at+16);n:=read32(b,at+20)
        if off+n>strings || n==0 || length>64*1024*1024 || read64(b,at)>64*1024*1024-length {return 4}
        name:=b[start+int(off):start+int(off+n)]
        if !utf8.valid_string(string(name)) {return 5}
        output[0]+=1;output[1]+=length
        if len(name)>=4 && string(name[len(name)-4:])==".pyc" {output[2]+=1;output[3]+=length}
        if len(name)>=7 && string(name[:7])=="django/" {output[4]+=1;output[5]+=length}
    }
    return 0
}

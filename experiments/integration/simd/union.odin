package masks
import "base:intrinsics"
import "core:simd"

// Object-mode linking does not invoke Odin's @init procedures. Initialize
// explicitly before any worker threads, checking both CPU and OS register state.
feature_mask:u32=1
@(export)
gaia_init :: proc "c" () -> u32 {
 max_id,_,_,_:=intrinsics.x86_cpuid(0,0)
 feature_mask=1
 if max_id<1 {return feature_mask}
 _,_,ecx,_:=intrinsics.x86_cpuid(1,0)
 if ecx&(1<<26)==0 || ecx&(1<<27)==0 || ecx&(1<<28)==0 {return feature_mask}
 eax,_:=intrinsics.x86_xgetbv(0)
 if eax&6!=6 || max_id<7 {return feature_mask}
 _,ebx,_,_:=intrinsics.x86_cpuid(7,0)
 if ebx&(1<<5)!=0 {feature_mask|=2}
 if eax&0xe6==0xe6 && ebx&(1<<16)!=0 {feature_mask|=4}
 return feature_mask
}
@(export)
gaia_features :: proc "c" () -> u32 {return feature_mask}

portable :: proc "c" (rows:[^]u64,words:u64,ids:[^]u32,count:u32,#no_alias out:[^]u64) {
 for k in 0..<count {offset:=u64(ids[k])*words;for j in 0..<words {out[j]|=rows[offset+j]}}
}
tiled :: proc "c" (rows:[^]u64,words:u64,ids:[^]u32,count:u32,#no_alias out:[^]u64) {
 for j in 0..<words {v:u64;for k in 0..<count {v|=rows[u64(ids[k])*words+j]};out[j]=v}
}
@(enable_target_feature="avx2")
wide4 :: proc "c" (rows:[^]u64,words:u64,ids:[^]u32,count:u32,#no_alias out:[^]u64) {
 j:u64
 for ;j+4<=words;j+=4 {
  v:simd.u64x4
  for k in 0..<count {p:=cast(^simd.u64x4)(&rows[u64(ids[k])*words+j]);v=simd.bit_or(v,intrinsics.unaligned_load(p))}
  intrinsics.unaligned_store(cast(^simd.u64x4)(&out[j]),v)
 }
 for ;j<words;j+=1 {v:u64;for k in 0..<count {v|=rows[u64(ids[k])*words+j]};out[j]=v}
}
@(enable_target_feature="avx512f")
wide8 :: proc "c" (rows:[^]u64,words:u64,ids:[^]u32,count:u32,#no_alias out:[^]u64) {
 j:u64
 for ;j+8<=words;j+=8 {
  v:simd.u64x8
  for k in 0..<count {p:=cast(^simd.u64x8)(&rows[u64(ids[k])*words+j]);v=simd.bit_or(v,intrinsics.unaligned_load(p))}
  intrinsics.unaligned_store(cast(^simd.u64x8)(&out[j]),v)
 }
 for ;j<words;j+=1 {v:u64;for k in 0..<count {v|=rows[u64(ids[k])*words+j]};out[j]=v}
}
// No aliases between writable output and read-only inputs. Caller owns buffers.
@(export)
gaia_union :: proc "c" (mode:u32,rows:[^]u64,nrows:u32,words:u64,ids:[^]u32,count:u32,#no_alias out:[^]u64) -> i32 {
 if words==0 || words>16384 || nrows==0 || rows==nil || ids==nil || out==nil {return 1}
 if mode>3 {return 2}
 features:=gaia_features()
 if mode==2 && features&2==0 || mode==3 && features&4==0 {return 3}
 for k in 0..<count {if ids[k]>=nrows {return 4}}
 for j in 0..<words {out[j]=0}
 switch mode {
 case 0:portable(rows,words,ids,count,out)
 case 1:tiled(rows,words,ids,count,out)
 case 2:wide4(rows,words,ids,count,out)
 case 3:wide8(rows,words,ids,count,out)
 }
 return 0
}

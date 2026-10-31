// Deterministic bounded force-layout kernel. Logical geometry, not hardware.
package embedding
import "core:math"
@(export)
gaia_embed :: proc "c"(n:u32,dim:u32,iterations:u32,weights:[^]f64,positions:[^]f64) -> i32 {
    if n==0 || n>512 || (dim!=1 && dim!=3) || iterations>200 || weights==nil || positions==nil {return 1}
    for i in 0..<n*n {if math.is_nan(weights[i]) || math.is_inf(weights[i]) || weights[i]<0 || weights[i]>1 {return 2}}
    for i in 0..<n*dim {if math.is_nan(positions[i]) || math.is_inf(positions[i]) {return 3}}
    force:[1536]f64
    for iteration in 0..<iterations {
        for i in 0..<n*dim {force[i]=0}
        for i in 0..<n {
            for j in i+1..<n {
                distance:f64=.01
                for d in 0..<dim {delta:=positions[i*dim+d]-positions[j*dim+d];distance+=delta*delta}
                scale:=.002/distance-.05*weights[i*n+j]
                for d in 0..<dim {
                    delta:=positions[i*dim+d]-positions[j*dim+d];value:=scale*delta
                    force[i*dim+d]+=value;force[j*dim+d]-=value
                }
            }
        }
        rate:=.5/(1+f64(iteration)/20)
        for d in 0..<dim {
            total:f64
            for i in 0..<n {
                positions[i*dim+d]+=rate*math.clamp(force[i*dim+d],-1.0,1.0)
                total+=positions[i*dim+d]
            }
            center:=total/f64(n)
            for i in 0..<n {positions[i*dim+d]-=center}
        }
    }
    return 0
}

// Bounded borrowed-buffer kernel. Matrix row p names dependencies of parent p.
package frontier
@(export)
gaia_affected :: proc "c"(n:u32, adjacency:[^]u8, dirty:[^]u8, output:[^]u8) -> i32 {
    if n==0 || n>1024 || adjacency==nil || dirty==nil || output==nil {return 1}
    for i in 0..<int(n)*int(n) {if adjacency[i]>1 {return 2}}
    for i in 0..<int(n) {if dirty[i]>1 {return 3};output[i]=0}
    queue:[1024]u32;head,tail:u32
    for i in 0..<n {if dirty[i]!=0 {queue[tail]=i;tail+=1;output[i]=1}}
    for head<tail {
        child:=queue[head];head+=1
        for parent in 0..<n {
            if adjacency[parent*n+child]!=0 && output[parent]==0 {
                output[parent]=1;queue[tail]=parent;tail+=1
            }
        }
    }
    return 0
}

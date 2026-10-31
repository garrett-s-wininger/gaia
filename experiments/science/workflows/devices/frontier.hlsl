StructuredBuffer<uint2> edges : register(t0);
StructuredBuffer<uint> frontier : register(t1);
RWStructuredBuffer<uint> next_frontier : register(u0);
cbuffer Bounds : register(b0) { uint edge_count; uint node_count; };
[numthreads(64,1,1)]
void main(uint3 id : SV_DispatchThreadID) {
    if (id.x >= edge_count) return;
    uint2 e=edges[id.x];
    if(e.x<node_count && e.y<node_count && frontier[e.x])
        InterlockedOr(next_frontier[e.y],1);
}

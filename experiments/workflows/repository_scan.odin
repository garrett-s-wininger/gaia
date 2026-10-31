// Bounded fixed-pattern scan. No source-language interpretation or ignore policy.
package main
import "core:fmt"
import "core:os"
import "core:strings"
import "core:strconv"
import "core:time"

PATTERNS :: [6]string{"Copyright", "MIT License", "TODO", "FIXME", "SPDX-License-Identifier", "password"}
Node :: struct {next: [256]int, fail: int, matches: u64}

automaton :: proc() -> [dynamic]Node {
    nodes:=make([dynamic]Node);append(&nodes,Node{})
    for p,k in PATTERNS {
        state:=0
        for b in transmute([]u8)p {
            n:=nodes[state].next[b]
            if n==0 {n=len(nodes);nodes[state].next[b]=n;append(&nodes,Node{})}
            state=n
        }
        nodes[state].matches|=u64(1)<<u64(k)
    }
    queue:=make([dynamic]int);defer delete(queue)
    for b in 0..<256 {if n:=nodes[0].next[b];n!=0 {append(&queue,n)}}
    for head:=0;head<len(queue);head+=1 {
        s:=queue[head]
        for b in 0..<256 {
            child:=nodes[s].next[b]
            if child!=0 {
                nodes[child].fail=nodes[nodes[s].fail].next[b]
                nodes[child].matches|=nodes[nodes[child].fail].matches
                append(&queue,child)
            } else {nodes[s].next[b]=nodes[nodes[s].fail].next[b]}
        }
    }
    return nodes
}

main :: proc() {
    if len(os.args)!=4 {fmt.eprintln("scan MANIFEST fused|shared|single QUERY");os.exit(2)}
    mode:=os.args[2];query,ok:=strconv.parse_int(os.args[3]);if !ok || query<0 || query>=len(PATTERNS) {os.exit(2)}
    if mode!="fused" && mode!="shared" && mode!="single" {os.exit(2)}
    start:=time.tick_now()
    manifest,err:=os.read_entire_file(os.args[1],context.allocator);if err!=nil {fmt.eprintln(err);os.exit(3)};defer delete(manifest)
    paths:=strings.split_lines(string(manifest));defer delete(paths)
    counts: [6]u64;bytes,files: u64;patterns:=PATTERNS
    nodes: [dynamic]Node
    if mode=="fused" {nodes=automaton()};defer delete(nodes)
    for path in paths {
        if path=="" {continue}
        data,e:=os.read_entire_file(path,context.allocator);if e!=nil {fmt.eprintln(path,e);os.exit(3)}
        bytes+=u64(len(data));files+=1
        if mode=="fused" {
            state:=0
            for b in data {
                state=nodes[state].next[b];mask:=nodes[state].matches
                if mask!=0 {for k in 0..<len(PATTERNS) {if mask&(u64(1)<<u64(k))!=0 {counts[k]+=1}}}
            }
        } else if mode=="shared" {
            for p,k in PATTERNS {counts[k]+=u64(strings.count(string(data),p))}
        } else {counts[query]+=u64(strings.count(string(data),patterns[query]))}
        delete(data)
    }
    fmt.print("{");fmt.printf("\"files\":%d,\"bytes\":%d,\"body_ns\":%d,\"counts\":[",files,bytes,i64(time.tick_since(start)))
    for n,k in counts {if k>0 {fmt.print(",")};fmt.print(n)}
    fmt.println("]}")
}

// Three schedules/representations for the same least Boolean fixed point.
// Trusted, prevalidated research ABI: all buffers are caller-owned and disjoint.
package liveness

Input :: struct {
    blocks, values, words, reserved: u32,
    succ_offsets, successors, pred_offsets, predecessors: [^]u32,
    generate, kill: [^]u64,
    seed_offsets, seeds: [^]u32,
}

Scratch :: struct {
    output, alternate: [^]u64,
    queue: [^]u32,
    queued: [^]u8,
}

// Mode 0: queued block dataflow; mode 1: synchronous Boolean sweeps;
// mode 2: transpose the problem and propagate each value through predecessors.
// Return block visits (0/2) or complete sweeps (1), not a comparable work unit.
@(export)
gaia_liveness :: proc "c"(mode: u32, input: ^Input, scratch: ^Scratch) -> u64 {
    if input == nil || scratch == nil || mode > 2 { return max(u64) }
    n, words := int(input.blocks), int(input.words)
    if n == 0 || words == 0 { return 0 }
    total := n*words
    out := scratch.output
    for i in 0..<total { out[i] = 0 }
    work: u64

    if mode == 2 {
        // The per-value columns contain generator blocks, not resolved liveness.
        for value in 0..<int(input.values) {
            word, mask := value/64, u64(1)<<u32(value%64)
            top := 0
            for j in int(input.seed_offsets[value])..<int(input.seed_offsets[value+1]) {
                b := int(input.seeds[j])
                if out[b*words+word]&mask == 0 {
                    out[b*words+word] |= mask
                    scratch.queue[top] = u32(b); top += 1
                }
            }
            for top > 0 {
                top -= 1
                b := int(scratch.queue[top]); work += 1
                for j in int(input.pred_offsets[b])..<int(input.pred_offsets[b+1]) {
                    p := int(input.predecessors[j]); index := p*words+word
                    if (out[index]|input.kill[index])&mask == 0 {
                        out[index] |= mask
                        scratch.queue[top] = u32(p); top += 1
                    }
                }
            }
        }
        return work
    }

    for i in 0..<total { out[i] = input.generate[i] }
    if mode == 1 {
        next := scratch.alternate
        // Any contributing fact has a simple, kill-free path of < n edges.
        for sweep in 0..=n {
            changed := false
            for b in 0..<n {
                row := b*words
                for w in 0..<words { next[row+w] = 0 }
                for j in int(input.succ_offsets[b])..<int(input.succ_offsets[b+1]) {
                    source := int(input.successors[j])*words
                    for w in 0..<words { next[row+w] |= out[source+w] }
                }
                difference: u64
                for w in 0..<words {
                    index := row+w
                    next[index] = input.generate[index] | (next[index] &~ input.kill[index])
                    difference |= next[index] ~ out[index]
                }
                changed = changed || difference != 0
            }
            work += 1
            out, next = next, out
            if !changed {
                if out != scratch.output {
                    for i in 0..<total { scratch.output[i] = out[i] }
                }
                return work
            }
        }
        return max(u64)
    }

    // A ring queue holds each block at most once. Reverse layout is a useful
    // inexpensive initial order; no claim of optimal graph ordering is made.
    for i in 0..<n { scratch.queue[i] = u32(n-1-i); scratch.queued[i] = 1 }
    head, tail: u64 = 0, u64(n)
    row_buffer := scratch.alternate
    for head < tail {
        b := int(scratch.queue[head%u64(n)]); head += 1
        scratch.queued[b] = 0; work += 1
        for w in 0..<words { row_buffer[w] = 0 }
        for j in int(input.succ_offsets[b])..<int(input.succ_offsets[b+1]) {
            source := int(input.successors[j])*words
            for w in 0..<words { row_buffer[w] |= out[source+w] }
        }
        row := b*words
        difference: u64
        for w in 0..<words {
            index := row+w
            v := input.generate[index] | (row_buffer[w] &~ input.kill[index])
            difference |= v ~ out[index]; out[index] = v
        }
        if difference != 0 {
            for j in int(input.pred_offsets[b])..<int(input.pred_offsets[b+1]) {
                p := input.predecessors[j]
                if scratch.queued[p] == 0 {
                    scratch.queued[p] = 1
                    scratch.queue[tail%u64(n)] = p; tail += 1
                }
            }
        }
    }
    return work
}

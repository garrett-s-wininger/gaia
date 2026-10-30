// Linux experimental accessor. The sidecar remains producer-certified and pinned.
package main

import "core:c"
import "core:encoding/endian"
import "core:fmt"
import "core:slice"
import "core:os"
import "core:strings"
import "core:sys/posix"
import "core:time"
import "core:unicode/utf8"

foreign import z "system:z"
foreign import crypto "system:crypto"
foreign z {
    crc32_z :: proc(crc: c.ulong, buf: [^]u8, len: c.size_t) -> c.ulong ---
    zlibVersion :: proc() -> cstring ---
}
foreign crypto {
    SHA256 :: proc(data: [^]u8, len: c.size_t, out: ^[32]u8) -> rawptr ---
    OpenSSL_version :: proc(kind: c.int) -> cstring ---
}

check :: proc(ok: bool, message: string) {
    if !ok { fmt.eprintln(message); os.exit(1) }
}

le :: #force_inline proc(data: []u8, offset, width: int) -> u64 {
    check(offset >= 0 && width <= len(data)-offset, "truncated index/ZIP field")
    switch width {
    case 2: return u64(endian.unchecked_get_u16le(data[offset:]))
    case 4: return u64(endian.unchecked_get_u32le(data[offset:]))
    case 8: return endian.unchecked_get_u64le(data[offset:])
    }
    check(false,"invalid field width")
    return 0
}

hash :: proc(data: []u8) -> [32]u8 {
    digest: [32]u8
    SHA256(raw_data(data), c.size_t(len(data)), &digest)
    return digest
}

hex :: proc(digest: [32]u8) -> string {
    result := make([]u8, 64)
    digits := "0123456789abcdef"
    for b, i in digest { result[2*i] = digits[b>>4]; result[2*i+1] = digits[b&15] }
    return string(result)
}

Mapping :: struct { fd: posix.FD, data: []u8, stat: posix.stat_t }

map_file :: proc(path: string) -> Mapping {
    name := strings.clone_to_cstring(path)
    defer delete(name)
    fd := posix.open(name, {.CLOEXEC})
    check(fd >= 0, "cannot open mapping")
    info: posix.stat_t
    check(posix.fstat(fd, &info) == nil && info.st_size > 0, "cannot stat/nonempty map")
    ptr := posix.mmap(nil, c.size_t(info.st_size), {.READ}, {.PRIVATE}, fd, 0)
    check(ptr != posix.MAP_FAILED, "cannot mmap")
    return Mapping{fd, ([^]u8)(ptr)[:int(info.st_size)], info}
}

unmap :: proc(m: Mapping) { posix.munmap(raw_data(m.data), c.size_t(len(m.data))); posix.close(m.fd) }

identity :: proc(s: posix.stat_t) -> [5]u64 {
    return {u64(s.st_dev), u64(s.st_ino), u64(s.st_size),
            u64(s.st_mtim.tv_sec)*1_000_000_000 + u64(s.st_mtim.tv_nsec),
            u64(s.st_ctim.tv_sec)*1_000_000_000 + u64(s.st_ctim.tv_nsec)}
}

Entry :: struct { start, length: int, crc: u32, directory: int, name: string }
Index :: struct {
    mapping: Mapping,
    count, payload_end, archive_size: int,
    directories: []string,
    name_starts: []int,
    name_starts32: []u32,
}

entry :: #force_inline proc(index: ^Index, i: int) -> Entry {
    check(i >= 0 && i < index.count, "entry outside index")
    data := index.mapping.data
    p := 128 + 28*i
    name_start:int
    if len(index.name_starts32)>0 { name_start=int(index.name_starts32[i]) } else { name_start=index.name_starts[i] }
    return Entry{int(le(data,p,8)), int(le(data,p+8,8)), u32(le(data,p+16,4)),
                 int(le(data,p+20,4)), string(data[name_start:name_start+int(le(data,p+24,4))])}
}

load_index :: proc(path, pin: string) -> Index {
    index: Index
    index.mapping = map_file(path)
    data := index.mapping.data
    actual_pin := hex(hash(data))
    defer delete(actual_pin)
    check(actual_pin == pin, "index digest mismatch")
    check(len(data) >= 128 && string(data[:8]) == "GAIAIDX\x00", "invalid binary index header")
    check(le(data,8,4) == 1 && le(data,12,4) == 0, "unsupported index version/flags")
    n, d, pool := le(data,104,8), le(data,112,8), le(data,120,8)
    check(n <= u64(len(data))/28 && d > 0 && d <= u64(len(data))/4, "invalid table counts")
    pool_start := 128 + 28*int(n) + 4*int(d)
    check(pool_start <= len(data) && pool == u64(len(data)-pool_start), "invalid string pool size")
    size, end := le(data,16,8), le(data,24,8)
    check(size <= 0x7fffffffffffffff && end <= size, "invalid archive boundary")
    index.count, index.archive_size, index.payload_end = int(n), int(size), int(end)
    index.directories = make([]string, int(d))
    index.name_starts = make([]int, int(n))
    cursor := pool_start
    directories := make(map[string]bool, int(d))
    defer delete(directories)
    for i in 0..<int(d) {
        length := int(le(data,128+28*int(n)+4*i,4))
        check(length <= len(data)-cursor, "directory outside pool")
        name := string(data[cursor:cursor+length])
        check(utf8.valid_string(name) && !(name in directories), "invalid/duplicate directory")
        directories[name] = true
        index.directories[i] = name
        cursor += length
    }
    check(index.directories[0] == "", "missing root directory")
    previous_end := 0
    for i in 0..<int(n) {
        p := 128+28*i
        start, length := le(data,p,8), le(data,p+8,8)
        name_length := int(le(data,p+24,4))
        check(start <= end && length <= end-start && start >= u64(previous_end), "invalid payload range")
        check(le(data,p+20,4) < d && name_length > 0 && name_length <= len(data)-cursor, "invalid name/directory")
        check(utf8.valid_string(string(data[cursor:cursor+name_length])), "invalid UTF-8 basename")
        index.name_starts[i] = cursor
        cursor += name_length
        previous_end = int(start+length)
    }
    check(cursor == len(data), "unused string-pool bytes")
    return index
}

close_index :: proc(index: ^Index) {
    delete(index.directories); delete(index.name_starts); unmap(index.mapping)
}

verify_bundle :: proc(index: ^Index, bundle: Mapping, policy: string) {
    check(len(bundle.data) == index.archive_size, "bundle size mismatch")
    data := index.mapping.data
    if policy == "hash" {
        digest := hash(bundle.data)
        check(slice.equal(digest[:], data[32:64]), "bundle digest mismatch")
    } else {
        id := identity(bundle.stat)
        for value, i in id { check(value == le(data,64+8*i,8), "bundle changed since local admission") }
    }
}

full_name :: proc(index: ^Index, e: Entry) -> string {
    return strings.concatenate({index.directories[e.directory], e.name})
}

// Controlled stored ZIPs: central order must match physical/index order. The
// pinned sidecar already certifies namespace admission; compare every ZIP row.
rebuild_zip :: proc(index: ^Index, data: []u8) -> []Entry {
    eocd := -1
    if len(data) >= 22 {
        for p := len(data)-22; p >= max(0,len(data)-65557); p -= 1 {
            if le(data,p,4) == 0x06054b50 && p+22+int(le(data,p+20,2)) == len(data) { eocd = p; break }
        }
    }
    check(eocd >= 0, "ZIP end record missing")
    check(le(data,eocd+4,2) == 0 && le(data,eocd+6,2) == 0, "multipart ZIP unsupported")
    check(le(data,eocd+8,2) == u64(index.count) && le(data,eocd+10,2) == u64(index.count), "ZIP count mismatch")
    p := int(le(data,eocd+16,4))
    check(p == index.payload_end && le(data,eocd+12,4) == u64(eocd-p), "ZIP central bounds mismatch")
    rows := make([]Entry, index.count)
    previous_end := 0
    for i in 0..<index.count {
        check(p >= 0 && p <= eocd-46 && le(data,p,4) == 0x02014b50, "invalid central header")
        flags, method := le(data,p+8,2), le(data,p+10,2)
        crc, size, compressed := u32(le(data,p+16,4)), le(data,p+24,4), le(data,p+20,4)
        name_len, extra_len, comment_len := int(le(data,p+28,2)), int(le(data,p+30,2)), int(le(data,p+32,2))
        check(flags & ~u64(0x800) == 0 && method == 0 && size == compressed, "only plain stored ZIP supported")
        check(p+46+name_len+extra_len+comment_len <= eocd, "central entry outside directory")
        name := string(data[p+46:p+46+name_len])
        if flags & 0x800 == 0 { for b in name { check(b < 128, "non-ASCII CP437 ZIP unsupported") } }
        local := int(le(data,p+42,4))
        check(local >= previous_end && local <= index.payload_end-30 && le(data,local,4) == 0x04034b50, "invalid/overlapping local header")
        check(le(data,local+6,2) == flags && le(data,local+8,2) == method && le(data,local+14,4) == u64(crc) &&
              le(data,local+18,4) == size && le(data,local+22,4) == size, "local/central fields differ")
        local_name := int(le(data,local+26,2))
        start := local+30+local_name+int(le(data,local+28,2))
        check(start <= index.payload_end && size <= u64(index.payload_end-start), "local payload outside bundle")
        check(local_name == name_len && string(data[local+30:local+30+local_name]) == name, "local/central name mismatch")
        expected := entry(index,i)
        wanted := full_name(index,expected)
        check(name == wanted && start == expected.start && size == u64(expected.length) && crc == expected.crc, "ZIP/index association differs")
        delete(wanted)
        rows[i] = Entry{start,int(size),crc,expected.directory,expected.name}
        previous_end = start+int(size)
        p += 46+name_len+extra_len+comment_len
    }
    check(p == eocd, "unused central directory bytes")
    return rows
}

read_file :: proc(path: cstring, length: int) -> []u8 {
    fd := posix.open(path, {.CLOEXEC})
    check(fd >= 0, "cannot open requested file")
    defer posix.close(fd)
    info: posix.stat_t
    check(posix.fstat(fd,&info) == nil && info.st_size == posix.off_t(length), "file size mismatch")
    data := make([]u8, length)
    offset := 0
    for offset < length {
        n := posix.read(fd, raw_data(data[offset:]), c.size_t(length-offset))
        check(n > 0, "short/failed file read")
        offset += int(n)
    }
    return data
}

seconds :: proc(start: time.Tick) -> f64 { return f64(time.tick_since(start))/1e9 }

main :: proc() {
    args := os.args
    check(len(args) == 9, "usage: worker INDEX INDEX_SHA ARCHIVE DIRECTORY index|zip|directory hash|local bytes|view named|ordinal")
    mode, policy, representation, lookup := args[5],args[6],args[7],args[8]
    check(mode == "index" || mode == "zip" || mode == "directory", "invalid reader mode")
    check(policy == "hash" || policy == "local", "invalid bundle policy")
    check(representation == "bytes" || representation == "view", "invalid representation")
    check(lookup == "named" || lookup == "ordinal", "invalid lookup")
    check(mode != "directory" || representation == "bytes", "directory requires bytes mode")
    // Match prepared Python primitives; process wall includes this bootstrap.
    bootstrap := time.tick_now()
    _ = hash([]u8{0})
    _ = crc32_z(0,nil,0)
    bootstrap_seconds := seconds(bootstrap)
    setup := time.tick_now()
    index := load_index(args[1],args[2])
    defer close_index(&index)
    bundle: Mapping
    if mode != "directory" {
        bundle = map_file(args[3])
        verify_bundle(&index,bundle,policy)
    }
    defer if mode != "directory" { unmap(bundle) }
    rows: []Entry
    if mode == "zip" { rows = rebuild_zip(&index,bundle.data) }
    defer delete(rows)
    names: []string
    paths: []cstring
    if lookup == "named" || mode == "directory" { names = make([]string,index.count) }
    if mode == "directory" { paths = make([]cstring,index.count) }
    table := make(map[string]int)
    defer { for name in names { delete(name) }; for path in paths { delete(path) }; delete(names); delete(paths); delete(table) }
    payload_bytes: u64
    for i in 0..<index.count {
        e := entry(&index,i)
        payload_bytes += u64(e.length)
        if lookup == "named" || mode == "directory" {
            names[i] = full_name(&index,e)
            if lookup == "named" {
                check(!(names[i] in table), "duplicate entry name")
                table[names[i]] = i
            }
        }
        if mode == "directory" {
            path := strings.concatenate({args[4],"/",names[i]})
            paths[i] = strings.clone_to_cstring(path)
            delete(path)
        }
    }
    if mode != "directory" {
        after: posix.stat_t
        check(posix.fstat(bundle.fd,&after) == nil && identity(after) == identity(bundle.stat), "bundle changed during open")
    }
    setup_seconds := seconds(setup)
    checksum: u64
    times: [4]f64
    for pass in 0..<4 {
        started := time.tick_now()
        for request in 0..<index.count {
            i := request
            if lookup == "named" {
                found: bool
                i, found = table[names[request]]
                check(found, "named request missing")
            }
            e := entry(&index,i)
            if mode == "zip" { e = rows[i] }
            data: []u8
            owned := representation == "bytes"
            if mode == "directory" { data = read_file(paths[i],e.length) }
            else {
                data = bundle.data[e.start:e.start+e.length]
                if owned { data = slice.clone(data) }
            }
            check(u32(crc32_z(0,raw_data(data),c.size_t(len(data)))) == e.crc, "payload CRC mismatch")
            checksum += u64(len(data))
            if len(data) > 0 { checksum += u64(data[0])+u64(data[len(data)-1]) }
            if owned { delete(data) }
        }
        times[pass] = seconds(started)
    }
    // Full content validation outside access timing, independently checked by parent.
    hashes := make([]u8,32*index.count)
    defer delete(hashes)
    for i in 0..<index.count {
        e := entry(&index,i)
        data: []u8
        if mode == "directory" { data = read_file(paths[i],e.length) }
        else { data = bundle.data[e.start:e.start+e.length] }
        digest := hash(data)
        copy(hashes[i*32:(i+1)*32],digest[:])
        if mode == "directory" { delete(data) }
    }
    validation := hex(hash(hashes))
    defer delete(validation)
    fmt.print("{")
    fmt.printf("\"correct\":true,\"entries\":%d,\"payload_bytes\":%d,\"application_checksum\":%d,",index.count,payload_bytes,checksum)
    fmt.printf("\"index_seconds\":%.9f,\"first_pass_seconds\":%.9f,\"reused_pass_seconds\":%.9f,\"first_use_seconds\":%.9f,",setup_seconds,times[0],(times[1]+times[2]+times[3])/3,setup_seconds+times[0])
    fmt.printf("\"pass_times_seconds\":[%.9f,%.9f,%.9f,%.9f],\"bootstrap_seconds\":%.9f,\"validation_digest\":\"%s\",",times[0],times[1],times[2],times[3],bootstrap_seconds,validation)
    fmt.printf("\"zlib_version\":\"%s\",\"openssl_version\":\"%s\"}\n",zlibVersion(),OpenSSL_version(0))
}

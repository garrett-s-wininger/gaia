// Linux immutable segmented inputs. Included after InputView/project_bridge.
// The serial host owns cache policy; each Pool leases its own segment mappings.
#include <algorithm>
#include <map>
#include <memory>
#include <vector>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#ifndef F_GET_SEALS
#define F_GET_SEALS 1034
#endif

static constexpr uint64_t gaia_shared_limit=64ull*1024*1024;
struct GaiaSharedSegment {
    int fd=-1;const uint8_t *data=nullptr;size_t size=0;uint64_t touched=0;
    std::vector<InputView> inputs;
    ~GaiaSharedSegment() {if(data) munmap(const_cast<uint8_t *>(data),size);if(fd>=0) close(fd);}
};
struct GaiaSharedCollection {
    bool active=false;
    std::vector<std::shared_ptr<GaiaSharedSegment>> leases;
    std::array<uint64_t,7> stats{};
};
static std::map<std::string,std::shared_ptr<GaiaSharedSegment>> gaia_shared_cache;
static uint64_t gaia_shared_clock=0;
static uint64_t gaia_shared_cache_bytes() {
    uint64_t size=0;for(const auto &entry:gaia_shared_cache) size+=entry.second->size;return size;
}
static std::string gaia_shared_hex(const uint8_t *digest) {
    const char *digits="0123456789abcdef";std::string result;result.reserve(64);
    for(unsigned i=0;i<32;++i) {result+=digits[digest[i]>>4];result+=digits[digest[i]&15];}return result;
}
static bool gaia_shared_utf8(llvm::StringRef value) {
    for(size_t i=0;i<value.size();) {
        unsigned char c=value[i++];if(c==0) return false;if(c<0x80) continue;
        unsigned length;uint32_t code,minimum;
        if(c>=0xc2 && c<=0xdf) {length=1;code=c&0x1f;minimum=0x80;}
        else if(c>=0xe0 && c<=0xef) {length=2;code=c&0x0f;minimum=0x800;}
        else if(c>=0xf0 && c<=0xf4) {length=3;code=c&7;minimum=0x10000;}
        else return false;
        if(length>value.size()-i) return false;
        while(length--) {unsigned char b=value[i++];if((b&0xc0)!=0x80) return false;code=(code<<6)|(b&0x3f);}
        if(code<minimum || code>0x10ffff || (code>=0xd800 && code<=0xdfff)) return false;
    }
    return true;
}
static bool gaia_shared_name(llvm::StringRef name) {
    if(name.size()<2 || name.size()>4096 || name.front()!='/' || name.back()=='/' ||
       name.contains('\\') || name.contains("//") || name.contains("/../") || name.contains("/./") ||
       name.ends_with("/.") || name.ends_with("/..")) return false;
    return gaia_shared_utf8(name);
}
// Successful reset is 0. Malformed keep sets are rejected before any eviction.
// Removing cache ownership never invalidates outstanding Pool leases.
extern "C" int gaia_shared_cache_reset(const char *keep_newline_hexpins) {
    if(!keep_newline_hexpins) return 1;std::set<std::string> keep;size_t length=strnlen(keep_newline_hexpins,8*65+1);if(length>8*65) return 1;std::string text(keep_newline_hexpins,length);
    size_t start=0;
    while(start<text.size()) {
        size_t end=text.find('\n',start);if(end==std::string::npos) end=text.size();
        auto pin=text.substr(start,end-start);
        if(pin.size()!=64 || pin.find_first_not_of("0123456789abcdef")!=std::string::npos || !keep.insert(pin).second) return 1;
        start=end+1;
    }
    if(keep.size()>8) return 1;
    for(auto it=gaia_shared_cache.begin();it!=gaia_shared_cache.end();) {
        if(!keep.count(it->first)) it=gaia_shared_cache.erase(it);else ++it;
    }
    return 0;
}
static std::shared_ptr<GaiaSharedSegment> gaia_shared_admit(const std::string &path,uint64_t size,const std::string &hex) {
    auto segment=std::make_shared<GaiaSharedSegment>();
    segment->fd=open(path.c_str(),O_RDONLY|O_CLOEXEC);if(segment->fd<0) return {};
    struct stat info{};int seals=fcntl(segment->fd,F_GET_SEALS);
    if(seals<0 || (seals&15)!=15 || fstat(segment->fd,&info) || !S_ISREG(info.st_mode) || info.st_size<0 || uint64_t(info.st_size)!=size) return {};
    void *mapping=mmap(nullptr,size,PROT_READ,MAP_SHARED,segment->fd,0);if(mapping==MAP_FAILED) return {};
    segment->data=static_cast<const uint8_t *>(mapping);segment->size=size;
    llvm::vfs::InMemoryFileSystem validation;Stats stats{};
    if(!absolute_inputs(validation,segment->data,size,("blake3:"+hex).c_str(),stats)) return {};
    size_t offset=16;
    for(uint64_t i=0;i<stats.input_files;++i) {
        auto n=integer(segment->data+offset,4),bytes=integer(segment->data+offset+4,8);offset+=12;
        std::string name(reinterpret_cast<const char *>(segment->data+offset),n);offset+=n+1;
        if(!gaia_shared_name(name)) return {};
        llvm::StringRef body(reinterpret_cast<const char *>(segment->data+offset),bytes);offset+=bytes+1;
        auto digest=gaia_query_digest(llvm::ArrayRef<uint8_t>(reinterpret_cast<const uint8_t *>(body.data()),body.size()));
        segment->inputs.push_back({std::move(name),body,digest,true});
    }
    return segment;
}
static bool gaia_shared_inputs(const uint8_t *data,size_t size,const char *pin,
    std::vector<InputView> &inputs,GaiaSharedCollection &collection,uint64_t &input_bytes) {
    if(!gaia_blake3_requested || !pin || size<32 || size>4*1024*1024 || memcmp(data,"GAIACIN4",8)) return false;
    auto manifest_digest=gaia_query_digest(llvm::ArrayRef<uint8_t>(data,size));
    if("blake3:"+gaia_shared_hex(manifest_digest.data())!=pin) return false;
    uint64_t count=integer(data+8,8),segments=integer(data+16,8);
    if(count>100000 || !segments || segments>8) return false;
    struct Request {std::string path,hex;uint64_t size;};std::vector<Request> requests;
    std::set<std::string> pins;size_t offset=24;uint64_t serialized=0;
    for(uint64_t i=0;i<segments;++i) {
        if(size-offset<4) return false;auto n=integer(data+offset,4);offset+=4;
        if(!n || n>4096 || n>size-offset || size-offset-n<40) return false;
        std::string path(reinterpret_cast<const char *>(data+offset),n);offset+=n;
        if(path[0]!='/' || !gaia_shared_utf8(path)) return false;
        auto bytes=integer(data+offset,8);offset+=8;auto hex=gaia_shared_hex(data+offset);offset+=32;
        if(bytes<16 || bytes>gaia_shared_limit-serialized || !pins.insert(hex).second) return false;
        serialized+=bytes;requests.push_back({std::move(path),std::move(hex),bytes});
    }
    if(size-offset<8) return false;auto removed=integer(data+offset,8);offset+=8;
    if(removed>100000 || removed>(size-offset)/5) return false;
    std::set<std::string> tombstones;
    for(uint64_t i=0;i<removed;++i) {
        if(size-offset<4) return false;auto n=integer(data+offset,4);offset+=4;
        if(n>size-offset) return false;std::string name(reinterpret_cast<const char *>(data+offset),n);offset+=n;
        if(!gaia_shared_name(name) || !tombstones.insert(name).second) return false;
    }
    if(offset!=size) return false;
    std::map<std::string,std::pair<InputView,bool>> final_inputs;
    collection.stats[6]=size;
    for(const auto &request:requests) {
        auto found=gaia_shared_cache.find(request.hex);bool reused=found!=gaia_shared_cache.end();std::shared_ptr<GaiaSharedSegment> segment;
        if(reused) {
            segment=found->second;if(segment->size!=request.size) return false;++collection.stats[0];
        } else {
            segment=gaia_shared_admit(request.path,request.size,request.hex);if(!segment) return false;
            // Evict old cache ownership before inserting. Leases retain mappings.
            while(gaia_shared_cache.size()>=8 || request.size>gaia_shared_limit-gaia_shared_cache_bytes()) {
                if(gaia_shared_cache.empty()) return false;
                auto victim=std::min_element(gaia_shared_cache.begin(),gaia_shared_cache.end(),[](const auto &a,const auto &b){return a.second->touched<b.second->touched;});
                gaia_shared_cache.erase(victim);
            }
            gaia_shared_cache.emplace(request.hex,segment);++collection.stats[1];collection.stats[2]+=request.size;
        }
        segment->touched=++gaia_shared_clock;collection.leases.push_back(segment);
        for(const auto &input:segment->inputs) final_inputs[input.name]={input,reused};
    }
    for(const auto &name:tombstones) final_inputs.erase(name);
    if(final_inputs.size()!=count) return false;
    llvm::vfs::InMemoryFileSystem validation;
    for(auto &entry:final_inputs) {
        const auto &input=entry.second.first;
        if(input.bytes.size()>gaia_shared_limit-input_bytes || !validation.addFile(input.name,0,llvm::MemoryBuffer::getMemBuffer(input.bytes,input.name,true))) return false;
        input_bytes+=input.bytes.size();inputs.push_back(input);collection.stats[5]+=entry.second.second;
    }
    collection.stats[3]=gaia_shared_cache_bytes();collection.stats[4]=gaia_shared_cache.size();collection.active=true;return true;
}

extern "C" int gaia_shared_cache_prime(const uint8_t *data,size_t size,const char *pin) {
    GaiaSharedCollection collection;std::vector<InputView> inputs;uint64_t bytes=0;
    return gaia_shared_inputs(data,size,pin,inputs,collection,bytes)?0:1;
}

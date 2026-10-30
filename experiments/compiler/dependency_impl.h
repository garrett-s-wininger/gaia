// LLVM-specific observation/replay boundary; cache policy/records remain Odin.
#include <llvm/Support/Path.h>
#include <map>
#include <array>

using DepDigest=std::array<uint8_t,32>;
struct DepRecord {uint8_t op=0,outcome=0;std::string path;DepDigest hash{};};
struct DepJournal {std::vector<DepRecord> records;std::string wire;bool reusable=true;};
struct DepState {
    Pool *pool;std::string cwd;bool enabled;
    std::vector<uint64_t> masks;
    std::vector<llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem>> views;
    std::vector<DepJournal> journals;
    std::unordered_map<std::string,DepDigest> contents;
    uint64_t replayed=0,negative_replayed=0,invalidated=0;
};
static DepState *dep_state=nullptr;
static void dep_number(std::string &out,uint64_t n,unsigned bytes=8) {
    for(unsigned i=0;i<bytes;++i) out.push_back(char(n>>(8*i)));
}
static void dep_text(std::string &out,llvm::StringRef s) {dep_number(out,s.size());out.append(s.data(),s.size());}
static void dep_error(std::string &out,std::error_code ec) {dep_text(out,ec.category().name());dep_number(out,ec.value());}
static std::string dep_path(llvm::vfs::FileSystem &fs,llvm::StringRef path) {
    llvm::SmallString<256> name(path);if(fs.makeAbsolute(name)) return {};
    llvm::sys::path::remove_dots(name,true);return name.str().str();
}
static void dep_status(std::string &out,const llvm::vfs::Status &s,llvm::vfs::FileSystem &fs) {
    // Provider contains only independent regular files and implicit directories,
    // no symlinks/hardlinks. Canonical path preserves identity/alias relations;
    // process-specific numeric InMemoryFS UniqueIDs must not be compared.
    dep_text(out,dep_path(fs,s.getName()));dep_number(out,uint64_t(s.getType()));
    dep_number(out,uint64_t(s.getPermissions()));dep_number(out,s.getSize());
    dep_number(out,uint64_t(s.getLastModificationTime().time_since_epoch().count()));
    dep_number(out,s.getUser());dep_number(out,s.getGroup());dep_number(out,s.ExposesExternalVFSPath);
}
static llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem> dep_view(int job) {
    auto &d=*dep_state;auto &view=d.views[job];
    if(!view) {
        auto *fs=new llvm::vfs::InMemoryFileSystem;view=fs;
        for(size_t i=0;i<d.pool->inputs.size();++i) if(d.masks[i]&(uint64_t(1)<<job)) {
            auto &in=d.pool->inputs[i];if(!fs->addFile(in.name,0,llvm::MemoryBuffer::getMemBuffer(in.bytes,in.name,true))) std::abort();
        }
    }
    if(view->setCurrentWorkingDirectory(d.cwd)) std::abort();return view;
}
// op: status, exists, open(text), open(binary), realpath, directory,
// locality, getcwd, setcwd. A result fingerprint covers observable metadata
// and opened contents. Queries against immutable views can be replayed safely.
static DepRecord dep_observe(llvm::vfs::FileSystem &fs,uint8_t op,llvm::StringRef path,bool &supported) {
    DepRecord r;r.op=op;r.path=path.str();std::string value;dep_number(value,op,1);
    auto error=[&](std::error_code ec) {r.outcome=ec?1:0;dep_error(value,ec);};
    if(op==1) {
        auto s=fs.status(path);if(!s) error(s.getError());else {error({});dep_status(value,*s,fs);}
    } else if(op==2) {bool exists=fs.exists(path);r.outcome=exists?0:1;dep_number(value,exists,1);
    } else if(op==3 || op==4) {
        auto f=op==3?fs.openFileForRead(path):fs.openFileForReadBinary(path);
        if(!f) error(f.getError());else {
            error({});auto s=(*f)->status();if(!s) {error(s.getError());supported=false;}else dep_status(value,*s,fs);
            auto name=dep_path(fs,path);auto found=dep_state->contents.find(name);
            if(found==dep_state->contents.end()) {supported=false;dep_text(value,"unsupported-open");}
            else value.append(reinterpret_cast<const char *>(found->second.data()),found->second.size());
            (*f)->close();
        }
    } else if(op==5) {
        llvm::SmallString<256> real;auto ec=fs.getRealPath(path,real);error(ec);dep_text(value,real);
    } else if(op==6) {
        std::error_code ec;auto it=fs.dir_begin(path,ec);error(ec);unsigned entries=0;
        for(;!ec && it!=llvm::vfs::directory_iterator();it.increment(ec)) {
            if(++entries>100000) {supported=false;break;}
            dep_text(value,it->path());dep_number(value,uint64_t(it->type()));
        }
        dep_number(value,entries);dep_error(value,ec);
    } else if(op==7) {
        bool local=false;auto ec=fs.isLocal(path,local);error(ec);if(!ec) dep_number(value,local,1);
    } else if(op==8) {
        auto cwd=fs.getCurrentWorkingDirectory();if(!cwd) error(cwd.getError());else {error({});dep_text(value,*cwd);}
    } else if(op==9) error(fs.setCurrentWorkingDirectory(path));
    else supported=false;
    r.hash=llvm::SHA256::hash(llvm::ArrayRef<uint8_t>(reinterpret_cast<const uint8_t *>(value.data()),value.size()));
    return r;
}
class DepFS : public llvm::vfs::ProxyFileSystem {
    DepJournal &journal;
    void record(uint8_t op,const llvm::Twine &path) {
        auto name=path.str();if(name.size()>4096 || journal.records.size()>=65536) {journal.reusable=false;return;}
        bool okay=true;auto r=dep_observe(getUnderlyingFS(),op,name,okay);
        journal.reusable&=okay;journal.records.push_back(std::move(r));
    }
public:
    DepFS(llvm::IntrusiveRefCntPtr<llvm::vfs::FileSystem> fs,DepJournal &j):ProxyFileSystem(std::move(fs)),journal(j) {}
    llvm::ErrorOr<llvm::vfs::Status> status(const llvm::Twine &p) override {record(1,p);return getUnderlyingFS().status(p);}
    bool exists(const llvm::Twine &p) override {record(2,p);return getUnderlyingFS().exists(p);}
    llvm::ErrorOr<std::unique_ptr<llvm::vfs::File>> openFileForRead(const llvm::Twine &p) override {record(3,p);return getUnderlyingFS().openFileForRead(p);}
    llvm::ErrorOr<std::unique_ptr<llvm::vfs::File>> openFileForReadBinary(const llvm::Twine &p) override {record(4,p);return getUnderlyingFS().openFileForReadBinary(p);}
    llvm::vfs::directory_iterator dir_begin(const llvm::Twine &p,std::error_code &ec) override {record(6,p);return getUnderlyingFS().dir_begin(p,ec);}
    std::error_code getRealPath(const llvm::Twine &p,llvm::SmallVectorImpl<char> &out) override {
        if(!out.empty()) journal.reusable=false;record(5,p);return getUnderlyingFS().getRealPath(p,out);
    }
    std::error_code isLocal(const llvm::Twine &p,bool &local) override {record(7,p);return getUnderlyingFS().isLocal(p,local);}
    llvm::ErrorOr<std::string> getCurrentWorkingDirectory() const override {
        const_cast<DepFS *>(this)->record(8,"");return getUnderlyingFS().getCurrentWorkingDirectory();
    }
    std::error_code setCurrentWorkingDirectory(const llvm::Twine &p) override {
        auto name=p.str();auto ec=getUnderlyingFS().setCurrentWorkingDirectory(p);
        if(name.size()>4096 || journal.records.size()>=65536) journal.reusable=false;
        else {
            DepRecord r;r.op=9;r.path=name;r.outcome=ec?1:0;std::string value;dep_number(value,9,1);dep_error(value,ec);
            r.hash=llvm::SHA256::hash(llvm::ArrayRef<uint8_t>(reinterpret_cast<const uint8_t *>(value.data()),value.size()));
            journal.records.push_back(std::move(r));
        }
        return ec;
    }
protected:
    void visitChildFileSystems(VisitCallbackTy callback) override {
        // A visitor could retain an uninstrumented underlying filesystem.
        journal.reusable=false;ProxyFileSystem::visitChildFileSystems(callback);
    }
};
extern "C" void *gaia_dep_open(void *handle,const uint64_t *masks,size_t count,const char *cwd,int enabled) {
    auto *pool=static_cast<Pool *>(handle);if(dep_state || !pool->memory || count!=pool->inputs.size()) return nullptr;
    auto d=std::make_unique<DepState>();d->pool=pool;d->cwd=cwd;d->enabled=enabled;
    d->masks.assign(masks,masks+count);d->views.resize(pool->commands.size());d->journals.resize(pool->commands.size());
    if(enabled) for(const auto &in:pool->inputs)
        d->contents.emplace(in.name,llvm::SHA256::hash(llvm::ArrayRef<uint8_t>(reinterpret_cast<const uint8_t *>(in.bytes.data()),in.bytes.size())));
    dep_state=d.release();return dep_state;
}
static int gaia_dep_execute(Worker *worker,int index) {
    if(!dep_state || dep_state->pool!=worker->pool) return 7;
    auto view=dep_view(index);
    if(dep_state->enabled) worker->fs=new DepFS(view,dep_state->journals[index]);else worker->fs=view;
    return gaia_worker_compile(worker,index);
}
extern "C" const uint8_t *gaia_dep_journal(void *,int index,size_t *size) {
    auto &j=dep_state->journals[index];*size=0;
    if(!j.reusable || j.records.empty()) return nullptr;
    j.wire="GAIAJR01";dep_number(j.wire,j.records.size(),4);
    for(const auto &r:j.records) {
        dep_number(j.wire,r.op,1);dep_number(j.wire,r.outcome,1);dep_number(j.wire,r.path.size(),4);
        j.wire+=r.path;j.wire.append(reinterpret_cast<const char *>(r.hash.data()),r.hash.size());
    }
    if(j.wire.size()>16*1024*1024) return nullptr;
    *size=j.wire.size();return reinterpret_cast<const uint8_t *>(j.wire.data());
}
extern "C" int gaia_dep_validate(void *,int index,const uint8_t *data,size_t size) {
    if(size<12 || size>16*1024*1024 || memcmp(data,"GAIAJR01",8)) return -1;
    auto count=integer(data+8,4);if(!count || count>65536) return -1;
    auto fs=dep_view(index);size_t offset=12;
    // Validate the entire framing first, before applying state-changing queries.
    for(uint64_t i=0;i<count;++i) {
        if(size-offset<38) return -1;auto op=data[offset],outcome=data[offset+1];auto n=integer(data+offset+2,4);offset+=6;
        if(op<1 || op>9 || outcome>1 || n>4096 || n>size-offset || size-offset-n<32) return -1;
        if(memchr(data+offset,0,n)) return -1;offset+=n+32;
    }
    if(offset!=size) return -1;offset=12;
    for(uint64_t i=0;i<count;++i) {
        auto op=data[offset],outcome=data[offset+1];auto n=integer(data+offset+2,4);offset+=6;
        llvm::StringRef path(reinterpret_cast<const char *>(data+offset),n);offset+=n;
        bool supported=true;auto current=dep_observe(*fs,op,path,supported);
        ++dep_state->replayed;dep_state->negative_replayed+=outcome!=0;
        if(!supported || current.outcome!=outcome || memcmp(current.hash.data(),data+offset,32)) {++dep_state->invalidated;return 0;}
        offset+=32;
    }
    return 1;
}
extern "C" uint64_t gaia_dep_stat(void *,int field) {
    if(field==0) return dep_state->replayed;if(field==1) return dep_state->negative_replayed;
    if(field==2) return dep_state->invalidated;return 0;
}
extern "C" void gaia_dep_close(void *handle) {if(handle!=dep_state) std::abort();delete dep_state;dep_state=nullptr;}

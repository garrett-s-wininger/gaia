// Included after State. Linux-only, single-thread-at-fork research adapter.
#include <cerrno>
#include <cstdio>

static std::string json_text(llvm::json::Object value){return llvm::formatv("{0}",llvm::json::Value(std::move(value))).str();}
static void single_thread_at_fork(){
 size_t count=0;for(auto&entry:std::filesystem::directory_iterator("/proc/self/task")){(void)entry;++count;}
 if(count!=1)throw std::runtime_error("forked pass research requires a single-threaded parent");
}
// Deliberately narrow request language. Unknown switches, forwarding options
// and response files cannot silently introduce child-owned side products.
static void require_object_only(const std::vector<std::string>&command){
 size_t inputs=0;bool compile=false;
 auto reject=[](){throw std::runtime_error("forked pass prototype supports object-only requests; option outside admitted subset");};
 for(size_t i=1;i<command.size();++i){const auto&a=command[i];
  if(a=="-c"){compile=true;continue;}
  if(a=="-o"||a=="-I"||a=="-isystem"||a=="-iquote"||a=="-idirafter"||a=="-D"||a=="-U"||a=="-include"||a=="-x"||a=="-std"||a=="--target"){if(++i==command.size())reject();continue;}
  if(a=="--no-default-config"||a=="-nostdinc"||a=="-nostdinc++"||a=="-Qunused-arguments"||a=="-Wa,--noexecstack"||a=="-fPIC"||a=="-fpic"||a=="-fPIE"||a=="-fpie"||a=="-fno-strict-aliasing"||a=="-fno-omit-frame-pointer"||a=="-pthread"||a=="-pedantic"||a=="-pedantic-errors"||a=="-g"||a=="-g0"||a=="-g1"||a=="-g2"||a=="-g3")continue;
  if(a.size()>2&&a.rfind("-W",0)==0&&a.rfind("-Wa,",0)!=0&&a.rfind("-Wl,",0)!=0&&a.rfind("-Wp,",0)!=0)continue;
  if(a.rfind("-I",0)==0||a.rfind("-D",0)==0||a.rfind("-U",0)==0||a.rfind("-std=",0)==0||a.rfind("--target=",0)==0||a.rfind("-fvisibility=",0)==0||a.rfind("-fdebug-compilation-dir=",0)==0)continue;
  if(a=="-O0"||a=="-O1"||a=="-O2"||a=="-O3"||a=="-Os"||a=="-Oz"||a=="-Og"||a=="-Ofast")continue;
  if(a.empty()||a[0]=='-'||a[0]=='@')reject();
  auto ext=std::filesystem::path(a).extension().string();if(ext!=".c"&&ext!=".cc"&&ext!=".cpp"&&ext!=".cxx"&&ext!=".C")reject();++inputs;
 }
 if(!compile||inputs!=1)reject();
}
struct Child{
 pid_t pid=-1;int fd=-1,status=0;bool waited=false;rusage usage{};
 Child()=default;Child(const Child&)=delete;Child&operator=(const Child&)=delete;
 ~Child(){if(pid>0&&!waited){::kill(pid,SIGTERM);while(::wait4(pid,&status,0,&usage)<0&&errno==EINTR){};}if(fd>=0)::close(fd);}
 void start(std::function<std::string()> function,int errors=-1){
  single_thread_at_fork();int channel[2];if(::pipe2(channel,O_CLOEXEC))throw std::runtime_error("child pipe failed");
  // An immediate discard must not run an inherited LLVM cleanup handler in
  // the child before it has installed default termination dispositions.
  sigset_t blocked,previous;::sigemptyset(&blocked);for(int number:{SIGTERM,SIGINT,SIGHUP})::sigaddset(&blocked,number);
  if(::sigprocmask(SIG_BLOCK,&blocked,&previous)){::close(channel[0]);::close(channel[1]);throw std::runtime_error("child signal mask failed");}
  pid=::fork();
  if(pid<0){::sigprocmask(SIG_SETMASK,&previous,nullptr);::close(channel[0]);::close(channel[1]);throw std::runtime_error("fork failed");}
  if(pid==0){
   // Children own no user-visible outputs. Avoid inherited LLVM signal cleanup
   // acting on parent-owned files if speculation is discarded or crashes.
   for(int number:{SIGTERM,SIGINT,SIGHUP,SIGSEGV,SIGBUS,SIGILL,SIGABRT,SIGFPE})::signal(number,SIG_DFL);
   sigset_t child_mask=previous;for(int number:{SIGTERM,SIGINT,SIGHUP})::sigdelset(&child_mask,number);
   if(::sigprocmask(SIG_SETMASK,&child_mask,nullptr))::_exit(3);
   ::close(channel[0]);if(errors>=0&&::dup2(errors,STDERR_FILENO)<0)::_exit(3);
   std::string data;try{data=function();}catch(const std::exception&e){data=json_text(llvm::json::Object{{"ok",false},{"error",e.what()}});}
   size_t offset=0;while(offset<data.size()){auto n=::write(channel[1],data.data()+offset,data.size()-offset);if(n<0&&errno==EINTR)continue;if(n<=0)::_exit(3);offset+=(size_t)n;}
   ::close(channel[1]);::_exit(0);
  }
  if(::sigprocmask(SIG_SETMASK,&previous,nullptr)){::kill(pid,SIGKILL);::close(channel[0]);::close(channel[1]);throw std::runtime_error("parent signal mask restore failed");}
  ::close(channel[1]);fd=channel[0];
 }
 std::string finish(bool discard=false){
  if(pid<=0||waited)throw std::runtime_error("child lifetime");if(discard)::kill(pid,SIGTERM);
  std::string data;char block[1024];ssize_t n;
  // Drain before waiting: a writer must not block on pipe capacity while its
  // parent waits for exit. The destructor reaps the child if the bound fails.
  for(;;){n=::read(fd,block,sizeof(block));if(n<0&&errno==EINTR)continue;if(n<0)throw std::runtime_error("child read failed");if(n==0)break;data.append(block,(size_t)n);if(data.size()>16384)throw std::runtime_error("child record bound");}
  ::close(fd);fd=-1;
  pid_t result;do{result=::wait4(pid,&status,0,&usage);}while(result<0&&errno==EINTR);
  if(result!=pid)throw std::runtime_error("child wait failed");waited=true;return data;
 }
 bool success()const{return waited&&WIFEXITED(status)&&WEXITSTATUS(status)==0;}
 double cpu()const{return usage.ru_utime.tv_sec+usage.ru_utime.tv_usec/1e6+usage.ru_stime.tv_sec+usage.ru_stime.tv_usec/1e6;}
};

// Declare before Child instances so exception unwinding kills/reaps writers
// before removing their staging path. A unique file never aliases prior output.
struct StagingFile{
 std::string path;
 void create(const std::string&output){
  if(!path.empty())throw std::runtime_error("staging lifetime");
  std::string name=output+".speculative.XXXXXX";std::vector<char>buffer(name.begin(),name.end());buffer.push_back('\0');
  int fd=::mkstemp(buffer.data());if(fd<0)throw std::runtime_error("object staging failed");::close(fd);path=buffer.data();
 }
 ~StagingFile(){if(!path.empty()){std::error_code error;std::filesystem::remove(path,error);}}
};

struct FactResult{uint64_t first=0,second=0;std::string digest;};
static FactResult dominators(llvm::Module&module){
 uint64_t dom=0,loops=0;std::string facts;llvm::raw_string_ostream stream(facts);
 for(auto&function:module){if(function.isDeclaration())continue;llvm::DominatorTree tree(function);llvm::LoopInfo info(tree);
  std::map<const llvm::BasicBlock*,int64_t>ids;int64_t next=0;for(auto&block:function)ids[&block]=next++;
  stream<<function.getName().size()<<":"<<function.getName()<<";";
  for(auto&block:function){int64_t parent=-1,header=-1;unsigned level=0;if(auto*node=tree.getNode(&block)){level=node->getLevel()+1;dom+=level;if(node->getIDom()&&node->getIDom()->getBlock())parent=ids.at(node->getIDom()->getBlock());}
   auto depth=info.getLoopDepth(&block);loops+=depth;if(auto*loop=info.getLoopFor(&block))header=ids.at(loop->getHeader());
   stream<<ids.at(&block)<<","<<parent<<","<<level<<","<<depth<<","<<header<<";";}}
 stream.flush();return {dom,loops,hash(facts)};
}
static FactResult postdominators(llvm::Module&module){
 uint64_t result=0;std::string facts;llvm::raw_string_ostream stream(facts);
 for(auto&function:module){if(function.isDeclaration())continue;llvm::PostDominatorTree tree(function);std::map<const llvm::BasicBlock*,int64_t>ids;int64_t next=0;for(auto&block:function)ids[&block]=next++;
  stream<<function.getName().size()<<":"<<function.getName()<<";";
  for(auto&block:function){int64_t parent=-1;unsigned level=0;if(auto*node=tree.getNode(&block)){level=node->getLevel()+1;result+=level;if(node->getIDom()&&node->getIDom()->getBlock())parent=ids.at(node->getIDom()->getBlock());}stream<<ids.at(&block)<<","<<parent<<","<<level<<";";}}
 stream.flush();return {result,0,hash(facts)};
}
static std::string file_text(FILE*file){
 if(!file)return {};fflush(file);rewind(file);std::string data;char buffer[4096];size_t n;
 while((n=fread(buffer,1,sizeof(buffer),file))!=0){data.append(buffer,n);if(data.size()>1024*1024)throw std::runtime_error("diagnostic bound");}
 return data;
}

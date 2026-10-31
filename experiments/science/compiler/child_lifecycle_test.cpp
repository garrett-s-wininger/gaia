// Standalone regression harness; compile/link with the same SDK as pass_host.
#define main gaia_compiler_host_main
#include "pass_host.cpp"
#undef main

int main(int argc,char**argv){
 if(argc!=2)return 2;std::string mode=argv[1];
 if(mode=="large-success"){
  Child child;child.start([]{return std::string(12000,'x');});
  if(child.finish()!=std::string(12000,'x')||!child.success())return 3;
 }else if(mode=="over-bound"){
  bool rejected=false;{Child child;child.start([]{return std::string(100000,'x');});
   try{child.finish();}catch(const std::runtime_error&e){rejected=std::string(e.what())=="child record bound";}}
  if(!rejected)return 4;
 }else if(mode=="cancel"||mode=="cancel-blocked"){
  if(mode=="cancel-blocked"){sigset_t blocked;::sigemptyset(&blocked);::sigaddset(&blocked,SIGTERM);if(::sigprocmask(SIG_BLOCK,&blocked,nullptr))return 8;}
  for(int i=0;i<32;++i){Child child;child.start([]{for(;;)::pause();return std::string();});child.finish(true);
   if(!child.waited||!WIFSIGNALED(child.status)||WTERMSIG(child.status)!=SIGTERM)return 5;}
 }else return 6;
 int status=0;if(::waitpid(-1,&status,WNOHANG)!=-1||errno!=ECHILD)return 7;
 return 0;
}

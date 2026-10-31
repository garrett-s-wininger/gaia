// ODRHash is a lossy 32-bit candidate screen. Exact IR remains mandatory.
#include <clang/AST/ASTConsumer.h>
#include <clang/AST/ASTContext.h>
#include <clang/AST/DeclCXX.h>
#include <clang/AST/ODRHash.h>
#include <clang/Frontend/FrontendActions.h>
#include <clang/Tooling/CompilationDatabase.h>
#include <clang/Tooling/Tooling.h>
#include <openssl/sha.h>
#include <chrono>
#include <iostream>
#include <memory>
#include <string>
#include <stdexcept>
#include <vector>
using Clock=std::chrono::steady_clock;
struct State {
 SHA256_CTX sha;unsigned declarations=0;long long walk_ns=0;
 State(){SHA256_Init(&sha);token("GAIA-ODR-CANDIDATE-1");}
 void token(const std::string&s){uint64_t n=s.size();unsigned char b[8];for(unsigned i=0;i<8;i++)b[i]=(n>>(8*i))&255;SHA256_Update(&sha,b,8);SHA256_Update(&sha,s.data(),s.size());}
 void decl(clang::Decl*d){
  if(++declarations>1000000)throw std::runtime_error("declaration bound");
  token(d->getDeclKindName());if(auto*n=llvm::dyn_cast<clang::NamedDecl>(d))token(n->getQualifiedNameAsString());
  if(auto*n=llvm::dyn_cast<clang::NamespaceDecl>(d)){for(auto*child:n->decls())decl(child);return;}
  if(auto*n=llvm::dyn_cast<clang::LinkageSpecDecl>(d)){for(auto*child:n->decls())decl(child);return;}
  clang::ODRHash hash;
  if(auto*f=llvm::dyn_cast<clang::FunctionDecl>(d))hash.AddFunctionDecl(f,false);
  else if(auto*r=llvm::dyn_cast<clang::CXXRecordDecl>(d);r&&r->isCompleteDefinition())hash.AddCXXRecordDecl(r);
  else if(auto*r=llvm::dyn_cast<clang::RecordDecl>(d);r&&r->isCompleteDefinition())hash.AddRecordDecl(r);
  else if(auto*e=llvm::dyn_cast<clang::EnumDecl>(d);e&&e->isCompleteDefinition())hash.AddEnumDecl(e);
  else hash.AddSubDecl(d);
  token(std::to_string(hash.CalculateHash()));
 }
 std::string finish(){unsigned char bytes[32];SHA256_Final(bytes,&sha);std::string s;const char*h="0123456789abcdef";for(auto b:bytes){s+=h[b>>4];s+=h[b&15];}return s;}
};
struct Consumer:clang::ASTConsumer{
 State& state;explicit Consumer(State&s):state(s){}
 void HandleTranslationUnit(clang::ASTContext&ctx)override{auto start=Clock::now();for(auto*d:ctx.getTranslationUnitDecl()->decls())state.decl(d);state.walk_ns=std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-start).count();}
};
struct Action:clang::ASTFrontendAction{State& state;explicit Action(State&s):state(s){}std::unique_ptr<clang::ASTConsumer>CreateASTConsumer(clang::CompilerInstance&,llvm::StringRef)override{return std::make_unique<Consumer>(state);}};
struct Factory:clang::tooling::FrontendActionFactory{State& state;explicit Factory(State&s):state(s){}std::unique_ptr<clang::FrontendAction>create()override{return std::make_unique<Action>(state);}};
struct Database:clang::tooling::CompilationDatabase{
 clang::tooling::CompileCommand command;explicit Database(clang::tooling::CompileCommand c):command(std::move(c)){}
 std::vector<clang::tooling::CompileCommand>getCompileCommands(llvm::StringRef)const override{return {command};}
};
int main(int argc,char**argv){
 // cwd source compiler [original compiler flags, without source/-c/-o]
 if(argc<4)return 2;std::vector<std::string> args;for(int i=3;i<argc;i++)args.emplace_back(argv[i]);args.emplace_back(argv[2]);
 Database db(clang::tooling::CompileCommand(argv[1],argv[2],args,""));State state;Factory factory(state);clang::tooling::ClangTool tool(db,{argv[2]});
 auto start=Clock::now();int result=tool.run(&factory);auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-start).count();if(result)return result;
 std::cout<<"{\"sha256\":\""<<state.finish()<<"\",\"direct_declarations\":"<<state.declarations<<",\"ast_ids\":0,\"ast_raw_bytes\":0,\"ast_canonical_bytes\":0,\"direct_odr_candidate\":true,\"frontend_ns\":"<<ns<<",\"walk_ns\":"<<state.walk_ns<<"}\n";
}

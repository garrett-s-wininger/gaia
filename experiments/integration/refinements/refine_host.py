"""Generate a reviewable opt-in continuation of the frozen workspace adapter."""
import argparse,hashlib,json
from pathlib import Path

def generate(source):
 s=source
 def replace(old,new):
  nonlocal s
  if s.count(old)!=1:raise ValueError('upstream shape changed: '+old[:80])
  s=s.replace(old,new)
 replace('#include <clang/Lex/PPCallbacks.h>','#include <clang/Lex/PPCallbacks.h>\n#include <clang/Lex/Lexer.h>\n#include <clang/Lex/MacroInfo.h>\n#include <clang/Lex/MacroArgs.h>')
 replace('mutable std::map<std::pair<std::string,std::string>,std::string> descriptions;','mutable std::map<std::pair<std::string,std::string>,std::string> descriptions;\n std::map<std::string,std::string> content_ids;')
 replace('auto exact=source->find(path);if(exact!=source->end()){auto key=std::make_pair(kind,path);auto cached=descriptions.find(key);if(cached!=descriptions.end())return cached->second;auto value="file:"+hash(*exact->second);descriptions[key]=value;return value;}', 'auto exact=source->find(path);if(exact!=source->end())return content_ids.at(path);')
 replace('struct ObservedEntry{std::string object;std::vector<Observation>observations;std::map<std::string,std::string>sideproducts;std::vector<std::string>facts;std::string target,space;};', '''struct FactSummary{std::string digest;int64_t count=0;std::vector<std::string>matches;};
struct LexicalNames{std::set<std::string>names;bool safe=true;std::vector<std::string>paste_alphabets;std::string reason;};
struct Projection{std::string key,profile;std::map<std::string,std::string>definitions;bool supported=false;};
struct ObservedEntry{std::string object;std::vector<Observation>observations;std::map<std::string,std::string>sideproducts;std::vector<std::string>facts;std::string target,space;FactSummary summary;LexicalNames lexical;std::map<std::string,std::string>definitions;uint64_t id=0,tick=0,bytes=0;};''')
 replace('Watch watch;std::map<std::string,ObservedEntry>observed;', '''Watch watch;std::map<std::string,std::vector<ObservedEntry>>observed;
 std::map<std::string,LexicalNames>lexical_cache;LexicalNames lexical;Projection projection;std::string family;
 std::map<std::string,uint64_t>published;uint64_t serial=0,tick=0;FactSummary facts_info;bool emit_facts=false;
 uint64_t history_budget=128*1024*1024;''')
 a=s.index('static void collect(State&s');b=s.index('struct VolatileMacros:',a)
 s=s[:a]+r'''static FactSummary summarize(const std::vector<std::string>&facts){
 std::string canonical;FactSummary info;info.count=facts.size();
 for(const auto&f:facts){canonical+=std::to_string(f.size())+":"+f;if(f.find("gaia_")!=std::string::npos)info.matches.push_back(f);}info.digest=hash(canonical);return info;
}
static llvm::json::Object fact_record(const FactSummary&info){llvm::json::Array matches;for(const auto&m:info.matches)matches.push_back(m);return llvm::json::Object{{"sha256",info.digest},{"symbols",info.count},{"matches",std::move(matches)}};}
static void publish_facts(State&s){if(s.emit_facts){llvm::json::Object event{{"event","frontend_facts"},{"frontend_ok",true},{"generation",(int64_t)s.generation},{"target",s.target},{"facts",fact_record(s.facts_info)}};std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(event))).str()<<std::endl;}}
static std::string encode(const std::vector<std::string>&parts){std::string out;for(const auto&p:parts)out+=std::to_string(p.size())+":"+p;return out;}
static bool identifier(const std::string&v){if(v.empty()||!((v[0]>='A'&&v[0]<='Z')||(v[0]>='a'&&v[0]<='z')))return false;for(auto c:v)if(!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_'))return false;return true;}
static Projection project(const std::vector<std::string>&command,const std::string&cwd,const std::string&family,bool analysis){
 Projection result;std::vector<std::string>base{family,cwd,analysis?"analysis":"build"},profile=base,full=base;std::set<std::string>seen;bool supported=true;
 const std::set<std::string>flags={"-c","-MMD","-MD","-g","-g0","-g1","-g2","-Wall","-Wextra","-Wno-deprecated","-Wno-missing-field-initializers","-Wno-unused-parameter","-Werror=date-time","-fno-rtti","-fno-exceptions","-pipe","-fdiagnostics-color","-fvisibility=hidden","-O0","-O1","-O2","-O3","-Os","-Oz","-Og","-w"};
 for(size_t i=0;i<command.size();++i){const auto&arg=command[i];
  if(arg=="-o"&&i+1<command.size()){++i;continue;}
  full.push_back(arg);
  if((arg=="-D"||arg=="-U")&&i+1<command.size()){
   auto value=command[++i];full.push_back(value);std::string joined=arg+value;auto eq=value.find('=');auto name=value.substr(0,eq);if(!seen.insert(name.substr(0,name.find('('))).second)supported=false;
   auto body=eq==std::string::npos?"1":value.substr(eq+1);bool numeric=!body.empty();for(auto c:body)if(c<'0'||c>'9')numeric=false;
   if(arg=="-D"&&identifier(name)&&numeric){result.definitions[name]=body;continue;}base.push_back(joined);profile.push_back(joined);continue;
  }
  if(arg.rfind("-D",0)==0||arg.rfind("-U",0)==0){auto value=arg.substr(2);auto eq=value.find('=');auto name=value.substr(0,eq);if(!seen.insert(name.substr(0,name.find('('))).second)supported=false;auto body=eq==std::string::npos?"1":value.substr(eq+1);bool numeric=!body.empty();for(auto c:body)if(c<'0'||c>'9')numeric=false;
   if(arg.rfind("-D",0)==0&&identifier(name)&&numeric){result.definitions[name]=body;continue;}base.push_back(arg);profile.push_back(arg);continue;}
  base.push_back(arg);
  if((arg=="-MF"||arg=="-MT")&&i+1<command.size()){base.push_back(command[++i]);full.push_back(command[i]);continue;}
  if((arg=="-I"||arg=="-isystem"||arg=="-include")&&i+1<command.size()){base.push_back(command[++i]);full.push_back(command[i]);profile.push_back(arg);profile.push_back(command[i]);continue;}
  bool input=arg.size()>2&&(arg.substr(arg.size()-2)==".c"||(arg.size()>3&&arg.substr(arg.size()-3)==".cc")||(arg.size()>4&&arg.substr(arg.size()-4)==".cpp"));
  if(i!=0&&!input&&!flags.count(arg)&&arg.rfind("-I",0)!=0&&arg.rfind("-std=",0)!=0)supported=false;
  if(!input&&arg!="-c")profile.push_back(arg);
 }
 result.supported=supported;result.key=hash(encode(supported?base:full));result.profile=hash(encode(profile));if(!supported)result.definitions.clear();return result;
}
static bool compatible(const ObservedEntry&e,const Projection&p){
 if(e.definitions==p.definitions)return true;if(!e.lexical.safe)return false;
 std::set<std::string>changed;for(const auto&v:e.definitions){auto it=p.definitions.find(v.first);if(it==p.definitions.end()||it->second!=v.second)changed.insert(v.first);}for(const auto&v:p.definitions){auto it=e.definitions.find(v.first);if(it==e.definitions.end()||it->second!=v.second)changed.insert(v.first);}for(const auto&name:changed){if(e.lexical.names.count(name))return false;for(const auto&alphabet:e.lexical.paste_alphabets){bool possible=true;for(auto c:name)if(alphabet.find(c)==std::string::npos){possible=false;break;}if(possible)return false;}}return true;
}
static ObservedEntry* lookup(State&s,const Projection&p){auto found=s.observed.find(p.key);if(found==s.observed.end())return nullptr;for(auto it=found->second.rbegin();it!=found->second.rend();++it)if(compatible(*it,p)&&s.watch.valid(it->observations)){it->tick=++s.tick;return &*it;}return nullptr;}
static uint64_t payload(const ObservedEntry&e){uint64_t n=e.object.size()+e.summary.digest.size();for(const auto&v:e.facts)n+=v.size();for(const auto&v:e.summary.matches)n+=v.size();for(const auto&v:e.observations)n+=v.kind.size()+v.path.size()+v.value.size();for(const auto&v:e.sideproducts)n+=v.first.size()+v.second.size();for(const auto&v:e.lexical.names)n+=v.size();for(const auto&v:e.definitions)n+=v.first.size()+v.second.size();for(const auto&v:e.lexical.paste_alphabets)n+=v.size();return n;}
static void retain(State&s,ObservedEntry entry){entry.id=++s.serial;entry.tick=++s.tick;entry.bytes=payload(entry);if(entry.bytes>s.history_budget)return;auto&group=s.observed[s.projection.key];if(group.size()>=8){auto it=std::min_element(group.begin(),group.end(),[](const auto&a,const auto&b){return a.tick<b.tick;});group.erase(it);}group.push_back(std::move(entry));
 for(;;){uint64_t bytes=0,count=0,oldest=~uint64_t(0);std::string victim;size_t index=0;for(const auto&g:s.observed)for(size_t i=0;i<g.second.size();++i){bytes+=g.second[i].bytes;++count;if(g.second[i].tick<oldest){oldest=g.second[i].tick;victim=g.first;index=i;}}if(bytes<=s.history_budget&&count<=256)break;s.observed[victim].erase(s.observed[victim].begin()+index);}
}
static bool materialize(State&s,ObservedEntry&e,const std::string&output,bool analysis){auto key=output+(analysis?":analysis":":build");if(s.published[key]==e.id)return false;s.published[key]=0;if(!analysis)write(output,e.object);for(const auto&p:e.sideproducts)write(p.first,p.second);s.published[key]=e.id;return !analysis;}
static void collect(State&s,clang::ASTContext&ast){
 Symbols visitor(s,ast);visitor.TraverseDecl(ast.getTranslationUnitDecl());std::sort(s.facts.begin(),s.facts.end());s.facts.erase(std::unique(s.facts.begin(),s.facts.end()),s.facts.end());s.facts_info=summarize(s.facts);
 auto&sm=ast.getSourceManager();
 for(auto it=sm.fileinfo_begin();it!=sm.fileinfo_end();++it){auto buffer=it->second->getBufferIfLoaded();if(!buffer){s.lexical.safe=false;s.lexical.reason="unloaded-file";continue;}std::string name=std::filesystem::absolute(it->first.getName().str()).lexically_normal().string();auto id=s.watch.content_ids.find(name);auto key=s.projection.profile+(id==s.watch.content_ids.end()?"sdk:"+name:"source:"+id->second);auto cached=s.lexical_cache.find(key);
  if(cached==s.lexical_cache.end()){LexicalNames names;auto body=buffer->getBuffer();clang::Lexer lexer(clang::SourceLocation(),ast.getLangOpts(),body.begin(),body.begin(),body.end());clang::Token token;
   for(;;){lexer.LexFromRawLexer(token);if(token.is(clang::tok::eof))break;if(token.isAnyIdentifier()){auto spelling=token.is(clang::tok::raw_identifier)?token.getRawIdentifier().str():token.getIdentifierInfo()->getName().str();if(token.needsCleaning()||token.hasUCN()){names.safe=false;names.reason="unclean-identifier";}for(auto c:spelling)if((unsigned char)c>=128){names.safe=false;names.reason="non-ascii-identifier";}names.names.insert(spelling);}}
   if(s.lexical_cache.size()>4096)s.lexical_cache.clear();cached=s.lexical_cache.emplace(key,std::move(names)).first;
  }
  s.lexical.safe=s.lexical.safe&&cached->second.safe;if(!cached->second.safe)s.lexical.reason=cached->second.reason;s.lexical.names.insert(cached->second.names.begin(),cached->second.names.end());
 }
}
''' +s[b:]
 # Expanded aliases contribute names even when their replacement identifier was undefined.
 replace('State&s;VolatileMacros(State&state):s(state){}', '''State&s;clang::Preprocessor&pp;VolatileMacros(State&state,clang::Preprocessor&p):s(state),pp(p){}
 std::set<std::string>defined_names;
 void MacroDefined(const clang::Token&t,const clang::MacroDirective*directive)override{auto*id=t.getIdentifierInfo();if(!id)return;auto name=id->getName().str();auto*info=directive->getMacroInfo();auto loc=info->getDefinitionLoc();auto&sm=pp.getSourceManager();if(sm.isWrittenInBuiltinFile(loc)||(sm.isWrittenInCommandLineFile(loc)&&!s.projection.definitions.count(name))||!defined_names.insert(name).second)s.lexical.names.insert(name);}
 void note(const clang::Token&t){if(auto*id=t.getIdentifierInfo())s.lexical.names.insert(id->getName().str());}
 void Defined(const clang::Token&t,const clang::MacroDefinition&,clang::SourceRange)override{note(t);}
 void Ifdef(clang::SourceLocation,const clang::Token&t,const clang::MacroDefinition&)override{note(t);}
 void Ifndef(clang::SourceLocation,const clang::Token&t,const clang::MacroDefinition&)override{note(t);}''')
 replace('void MacroExpands(const clang::Token&token,const clang::MacroDefinition&,clang::SourceRange,const clang::MacroArgs*)override{', '''void MacroExpands(const clang::Token&token,const clang::MacroDefinition&definition,clang::SourceRange,const clang::MacroArgs*arguments)override{
  note(token);if(auto*info=definition.getMacroInfo()){
   bool pasted=false;for(const auto&t:info->tokens()){note(t);if(t.is(clang::tok::hashhash))pasted=true;}
   if(pasted){std::set<char>letters;auto add=[&](const clang::Token&t){if(t.needsCleaning()||t.hasUCN()){s.lexical.safe=false;s.lexical.reason="unclean-paste";}auto text=clang::Lexer::getSpelling(t,pp.getSourceManager(),pp.getLangOpts());for(auto c:text){if((unsigned char)c>=128){s.lexical.safe=false;s.lexical.reason="non-ascii-paste";}letters.insert(c);}};
    for(const auto&t:info->tokens())add(t);if(arguments)for(unsigned i=0;i<arguments->getNumMacroArguments();++i)for(auto*t=arguments->getUnexpArgument(i);t->isNot(clang::tok::eof);++t)add(*t);
    s.lexical.paste_alphabets.push_back(std::string(letters.begin(),letters.end()));
   }
  }''')
 replace('std::make_unique<VolatileMacros>(s)', 'std::make_unique<VolatileMacros>(s,ci.getPreprocessor())')
 replace('ci.getPreprocessor().addPPCallbacks(', 'if(ci.getCodeGenOpts().MacroDebugInfo||!ci.getCodeGenOpts().DwarfDebugFlags.empty()||!ci.getCodeGenOpts().RecordCommandLine.empty()||ci.getCodeGenOpts().getEmbedBitcode()!=clang::CodeGenOptions::Embed_Off){s.lexical.safe=false;s.lexical.reason="recorded-command-or-macros";}ci.getPreprocessor().addPPCallbacks(')
 replace('collect(s,ast);\n  std::vector<std::string> names;', 'collect(s,ast);publish_facts(s);\n  std::vector<std::string> names;')
 replace('auto next=s.source_files;size_t total=0;', 'auto next=s.source_files;auto next_ids=s.watch.content_ids;size_t total=0;')
 replace('if(pair.second.getAsNull())next.erase(name);else{auto b=pair.second.getAsString();if(!b)throw std::runtime_error("source body");next[name]=std::make_shared<std::string>(b->str());}', 'if(pair.second.getAsNull()){next.erase(name);next_ids.erase(name);}else{auto b=pair.second.getAsString();if(!b)throw std::runtime_error("source body");auto old=next.find(name);if(old==next.end()||*old->second!=*b){next[name]=std::make_shared<std::string>(b->str());next_ids[name]="file:"+hash(*b);}}')
 replace('s.watch.descriptions.clear();s.filesystem=', 's.watch.descriptions.clear();s.watch.content_ids=std::move(next_ids);s.filesystem=')
 # Replace the scan endpoint; enhanced callers supply exact current commands.
 a=s.index('   if(auto*targets=obj->getArray("scan")){');b=s.index('   if(auto path=obj->getString("inspect"))',a)
 s=s[:a]+r'''   if(auto*targets=obj->getArray("scan")){
    auto expected=obj->getInteger("generation");auto space=obj->getString("context");if(!space||!expected||*expected!=(int64_t)s.generation)throw std::runtime_error("stale scan generation");
    auto*commands=obj->getObject("commands");auto family=obj->getString("family").value_or(*space);auto cwd=obj->getString("cwd").value_or(s.source_root);bool analysis=obj->getBoolean("analysis_only").value_or(false);
    llvm::json::Array dirty,restored,projected;llvm::json::Object facts;
    for(const auto&t:*targets){auto name=t.getAsString();if(!name)throw std::runtime_error("scan target");ObservedEntry*found=nullptr;std::string output;Projection projection;
     if(commands){auto*args=commands->getArray(*name);if(!args)throw std::runtime_error("missing scan command");std::vector<std::string>cmd;for(const auto&a:*args){auto value=a.getAsString();if(!value)throw std::runtime_error("scan command value");cmd.push_back(value->str());}for(size_t i=0;i+1<cmd.size();++i)if(cmd[i]=="-o")output=cmd[i+1];if(output.empty())throw std::runtime_error("scan output");projection=project(cmd,cwd.str(),family.str(),analysis);found=lookup(s,projection);}
     else{for(auto&group:s.observed)for(auto it=group.second.rbegin();it!=group.second.rend();++it)if(it->target==*name&&it->space==*space&&s.watch.valid(it->observations)){found=&*it;break;}}
     if(!found)dirty.push_back(name->str());else{if(commands){if(found->definitions!=projection.definitions)projected.push_back(name->str());if(materialize(s,*found,output,analysis))restored.push_back(name->str());}facts[name->str()]=fact_record(found->summary);}
    }
    llvm::json::Object response{{"ok",true},{"generation",(int64_t)s.generation},{"dirty",std::move(dirty)},{"restored",std::move(restored)},{"projected",std::move(projected)},{"facts",std::move(facts)},{"seconds",seconds(start)}};std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;continue;
   }
''' +s[b:]
 replace('s.facts.clear();s.target=', 's.facts.clear();s.facts_info=summarize(s.facts);s.lexical=LexicalNames{};s.emit_facts=obj->getBoolean("emit_facts").value_or(false);s.family=obj->getString("family").value_or(*ctx).str();s.target=')
 replace('s.context+=(s.analysis_only?"analysis:":"build:")+hash(command_key);', 's.context+=(s.analysis_only?"analysis:":"build:")+hash(command_key);s.projection=project(command,cwd->str(),s.family,s.analysis_only);')
 a=s.index('    auto cached=s.observed.find(s.context);');b=s.index('\n   }\n   std::filesystem::current_path',a)
 s=s[:a]+r'''    auto*cached=lookup(s,s.projection);
    if(cached){s.facts_info=cached->summary;publish_facts(s);s.published.erase(s.output+(s.analysis_only?":analysis":":build"));materialize(s,*cached,s.output,s.analysis_only);
     llvm::json::Object response{{"ok",true},{"facts",fact_record(cached->summary)},{"validation_hit",true},{"hit",false},{"generation",(int64_t)s.generation},{"observation_count",(int64_t)cached->observations.size()},{"seconds",seconds(start)}};std::cout<<llvm::formatv("{0}",llvm::json::Value(std::move(response))).str()<<std::endl;continue;
    }''' +s[b:]
 replace('ObservedEntry entry{s.analysis_only?"":read(s.output),s.watch.records,{},s.facts,s.target,s.space};', 'ObservedEntry entry{s.analysis_only?"":read(s.output),s.watch.records,{},s.facts,s.target,s.space,s.facts_info,s.lexical,s.projection.definitions};')
 replace('if(s.observed.size()>=256)s.observed.clear();s.observed[s.context]=std::move(entry);', 'retain(s,std::move(entry));if(auto*stored=lookup(s,s.projection))s.published[s.output+(s.analysis_only?":analysis":":build")]=stored->id;')
 replace('}else if(observed_mode)s.observed.erase(s.context);', '}')
 replace('{"facts",fact_record(s.facts)}', '{"facts",fact_record(s.facts_info)}')
 # Diagnostic responses expose the conservative projection decision for auditing.
 replace('{"observation_count",(int64_t)s.watch.records.size()}', '{"projection_reason",s.lexical.reason},{"paste_count",(int64_t)s.lexical.paste_alphabets.size()},{"projection_safe",s.lexical.safe},{"projection_supported",s.projection.supported},{"identifier_count",(int64_t)s.lexical.names.size()},{"observation_count",(int64_t)s.watch.records.size()}')
 return s

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();original=a.source.read_text();generated=generate(original);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(generated);print(json.dumps({'source_sha256':hashlib.sha256(original.encode()).hexdigest(),'generated_sha256':hashlib.sha256(generated.encode()).hexdigest()}))
if __name__=='__main__':main()

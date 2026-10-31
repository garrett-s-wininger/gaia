// Diagnostic AST candidate identity, never the complete object-cache proof.
#include <llvm/Support/JSON.h>
#include <llvm/Support/raw_ostream.h>
#include <openssl/sha.h>
#include <algorithm>
#include <cctype>
#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <unordered_map>
#include <vector>

using Clock=std::chrono::steady_clock;
struct Fingerprint {
    SHA256_CTX context{};
    std::unordered_map<std::string,size_t> identities;
    size_t nodes=0,encoded=0;
    Fingerprint(){SHA256_Init(&context);}
    void token(char type,llvm::StringRef body={}){
        SHA256_Update(&context,&type,1);uint64_t size=body.size();
        unsigned char length[8];for(unsigned i=0;i<8;i++)length[i]=(size>>(i*8))&255;
        SHA256_Update(&context,length,8);if(!body.empty())SHA256_Update(&context,body.data(),body.size());encoded+=9+body.size();
    }
    static bool identity(llvm::StringRef key){return key=="id"||key=="previousDecl"||key=="parentDeclContextId"||key=="typeAliasDeclId"||key=="referencedMemberDecl"||key=="canonicalDecl";}
    void walk(const llvm::json::Value& value,llvm::StringRef key={}){
        if(auto object=value.getAsObject()){
            nodes++;token('{');std::vector<llvm::StringRef> names;
            for(auto& field:*object)if(field.first!="loc"&&field.first!="range")names.push_back(field.first);
            std::sort(names.begin(),names.end());
            for(auto name:names){token('k',name);walk(*object->get(name),name);}token('}');
        }else if(auto array=value.getAsArray()){
            token('[');for(auto& item:*array)walk(item);token(']');
        }else if(auto text=value.getAsString()){
            bool pointer=identity(key)&&text->starts_with("0x")&&text->size()>2;
            for(size_t i=2;pointer&&i<text->size();i++)pointer=std::isxdigit(static_cast<unsigned char>((*text)[i]));
            if(pointer){
                if(*text=="0x0")token('p',"null");
                else {auto inserted=identities.emplace(text->str(),identities.size());token('p',std::to_string(inserted.first->second));}
            }else token('s',*text);
        }else{
            std::string rendered;llvm::raw_string_ostream out(rendered);out<<value;token('v',out.str());
        }
    }
    std::string finish(){unsigned char digest[32];SHA256_Final(digest,&context);std::string result;const char* hex="0123456789abcdef";for(auto byte:digest){result+=hex[byte>>4];result+=hex[byte&15];}return result;}
};
int main(int argc,char**argv){
    if(argc!=2)return 2;
    auto begin=Clock::now();std::ifstream input(argv[1],std::ios::binary|std::ios::ate);
    if(!input||input.tellg()<0||input.tellg()>128*1024*1024)return 3;
    size_t size=input.tellg();input.seekg(0);std::string body(size,'\0');if(!input.read(body.data(),size))return 4;
    auto value=llvm::json::parse(body);if(!value){llvm::consumeError(value.takeError());return 5;}
    auto parsed=Clock::now();Fingerprint fingerprint;fingerprint.token('D',"GAIA-AST-CANDIDATE-1");fingerprint.walk(*value);auto digest=fingerprint.finish();auto done=Clock::now();
    auto ns=[](auto duration){return std::chrono::duration_cast<std::chrono::nanoseconds>(duration).count();};
    std::cout<<"{\"sha256\":\""<<digest<<"\",\"ast_raw_bytes\":"<<size<<",\"ast_nodes\":"<<fingerprint.nodes<<",\"ast_ids\":"<<fingerprint.identities.size()<<",\"ast_canonical_bytes\":"<<fingerprint.encoded<<",\"parse_ns\":"<<ns(parsed-begin)<<",\"walk_ns\":"<<ns(done-parsed)<<"}\n";
}

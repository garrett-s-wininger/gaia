"""Generate a private Clang-host variant; preserve the exact SHA-256 contract."""
import argparse,hashlib,json
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();s=a.source.read_text();start=s.index('static std::string hash(llvm::StringRef s)');end=s.index('\nstatic std::string read(',start)
 old=s[start:end];assert old.count('LLVM')==0 and 'llvm::SHA256::hash' in old
 new='''static std::string hash(llvm::StringRef s){
 unsigned char b[32];SHA256_CTX context;
 if(SHA256_Init(&context)!=1||SHA256_Update(&context,s.data(),s.size())!=1||SHA256_Final(b,&context)!=1)throw std::runtime_error("SHA-256 failed");
 const char*h="0123456789abcdef";std::string r;for(auto c:b){r+=h[c>>4];r+=h[c&15];}return r;
}'''
 generated='#define OPENSSL_SUPPRESS_DEPRECATED\n#include <openssl/sha.h>\n'+s[:start]+new+s[end:];a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(generated);print(json.dumps({'source_sha256':hashlib.sha256(s.encode()).hexdigest(),'generated_sha256':hashlib.sha256(generated.encode()).hexdigest()}))
if __name__=='__main__':main()

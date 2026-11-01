#include <dlfcn.h>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <vector>
#include <algorithm>
#include <numeric>
#include <random>
#include <stdexcept>
using U=uint64_t;
using Kernel=int(*)(uint32_t,const U*,uint32_t,U,const uint32_t*,uint32_t,U*);
using Clock=std::chrono::steady_clock;
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("library fixture repetitions blocks");void*lib=dlopen(argv[1],RTLD_NOW);if(!lib)throw std::runtime_error(dlerror());
 auto init=(uint32_t(*)())dlsym(lib,"gaia_init");if(!init)throw std::runtime_error("initialization symbol");init();
 auto kernel=(Kernel)dlsym(lib,"gaia_union");auto features=(uint32_t(*)())dlsym(lib,"gaia_features");if(!kernel||!features)throw std::runtime_error("symbols");
 std::ifstream in(argv[2],std::ios::binary);uint32_t h[4];in.read((char*)h,16);auto rows=h[0],words=h[1],queries=h[2],changed=h[3];
 if(!in||!rows||rows>65536||!words||words>1024||!queries||queries>1024||changed>rows)throw std::runtime_error("dimensions");
 std::vector<U> matrix((U)rows*words);std::vector<uint32_t> ids((U)queries*changed);in.read((char*)matrix.data(),matrix.size()*8);in.read((char*)ids.data(),ids.size()*4);if(!in||in.peek()!=EOF)throw std::runtime_error("fixture");for(auto id:ids)if(id>=rows)throw std::runtime_error("index");
 auto prep=Clock::now();std::vector<uint32_t> offsets(rows+1),targets;
 for(uint32_t i=0;i<rows;++i){for(uint32_t j=0;j<words;++j){U bits=matrix[(U)i*words+j];while(bits){auto b=__builtin_ctzll(bits);targets.push_back(j*64+b);bits&=bits-1;}}offsets[i+1]=targets.size();}
 auto prep_ns=std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-prep).count();
 std::vector<U> output(words),oracle(words);auto run=[&](int mode,uint32_t q){const auto*p=ids.data()+(U)q*changed;if(mode==4){std::fill(output.begin(),output.end(),0);for(uint32_t i=0;i<changed;++i)for(auto j=offsets[p[i]];j<offsets[p[i]+1];++j){auto t=targets[j];output[t/64]|=U(1)<<(t%64);}}else if(kernel(mode,matrix.data(),rows,words,p,changed,output.data()))throw std::runtime_error("kernel rejection");};
 std::vector<int>modes={0,1,4};if(features()&2)modes.push_back(2);if(features()&4)modes.push_back(3);
 for(uint32_t q=0;q<queries;++q){std::fill(oracle.begin(),oracle.end(),0);for(uint32_t i=0;i<changed;++i)for(uint32_t j=0;j<words;++j)oracle[j]|=matrix[(U)ids[(U)q*changed+i]*words+j];for(auto mode:modes){run(mode,q);if(output!=oracle)throw std::runtime_error("oracle mismatch");}}
 auto repetitions=std::stoul(argv[3]),blocks=std::stoul(argv[4]);if(!repetitions||repetitions>10000000||!blocks||blocks>50)throw std::runtime_error("repetitions");std::mt19937 random(1729);volatile U sink=0;
 std::cout<<"{\"features\":"<<features()<<",\"rows\":"<<rows<<",\"words\":"<<words<<",\"queries\":"<<queries<<",\"changed\":"<<changed<<",\"matrix_bytes\":"<<matrix.size()*8<<",\"csr_bytes\":"<<(targets.size()+offsets.size())*4<<",\"csr_prepare_ns\":"<<prep_ns<<",\"validated_queries_per_mode\":"<<queries<<",\"observations\":[";bool first=true;
 for(unsigned block=0;block<blocks;++block){std::shuffle(modes.begin(),modes.end(),random);for(auto mode:modes){auto begin=Clock::now();for(unsigned r=0;r<repetitions;++r){run(mode,r%queries);sink^=output[r%words];}auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-begin).count();if(!first)std::cout<<',';first=false;std::cout<<"{\"block\":"<<block<<",\"mode\":"<<mode<<",\"ns\":"<<ns<<",\"operations\":"<<repetitions<<"}";}}
 std::cout<<"],\"sink\":"<<sink<<"}\n";dlclose(lib);return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}

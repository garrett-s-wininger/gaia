// Narrow D3D12 API experiment; native CPU controls live beside the API calls.
#include <wsl/winadapter.h>
#include <directx/d3d12.h>
#include <directx/dxcore.h>
#include <dlfcn.h>
#include <chrono>
#include <thread>
#include <vector>
#include <fstream>
#include <iostream>
#include <cstring>
#include <stdexcept>
#include <algorithm>
using Clock=std::chrono::steady_clock;
double ms(Clock::time_point t){return std::chrono::duration<double,std::milli>(Clock::now()-t).count();}
void check(HRESULT h,const char*s){if(FAILED(h)){std::cerr<<s<<" HRESULT 0x"<<std::hex<<uint32_t(h)<<std::endl;throw std::runtime_error(s);}}
template<class T> struct Ptr {T*p=nullptr;~Ptr(){if(p)p->Release();} T*operator->(){return p;} operator T*(){return p;} };
struct Edge{uint32_t a,b;};
int main(int argc,char**argv){try{
 if(argc!=5)throw std::runtime_error("dispatch shader.dxil graph.bin repetitions frontier_stride");
 auto begin=Clock::now();
 std::ifstream f(argv[2],std::ios::binary);uint32_t n,m;f.read((char*)&n,4);f.read((char*)&m,4);if(!f||!n||!m)throw std::runtime_error("graph header");
 std::vector<Edge>edges(m);f.read((char*)edges.data(),m*sizeof(Edge));if(!f)throw std::runtime_error("graph truncated");
 std::vector<uint32_t>front(n),expected(n),observed(n),zero(n);for(uint32_t i=0;i<n;i++)front[i]=(i%std::stoul(argv[4])==0);for(auto e:edges){if(e.a>=n||e.b>=n)throw std::runtime_error("edge bounds");if(front[e.a])expected[e.b]=1;}
 auto csr_start=Clock::now();std::vector<uint32_t> offsets(n+1),adj(m);for(auto e:edges)offsets[e.a+1]++;for(uint32_t i=1;i<=n;i++)offsets[i]+=offsets[i-1];auto cursor=offsets;for(auto e:edges)adj[cursor[e.a]++]=e.b;double csr_build_ms=ms(csr_start);
 std::ifstream sf(argv[1],std::ios::binary);std::vector<char>shader((std::istreambuf_iterator<char>(sf)),{});if(shader.empty())throw std::runtime_error("shader empty");
 void* core=dlopen("/usr/lib/wsl/lib/libdxcore.so",RTLD_NOW|RTLD_GLOBAL);void* lib=dlopen("/usr/lib/wsl/lib/libd3d12.so",RTLD_NOW);if(!core||!lib)throw std::runtime_error(dlerror());
 auto factoryfn=(HRESULT(*)(REFIID,void**))dlsym(core,"DXCoreCreateAdapterFactory");auto devfn=(HRESULT(*)(IUnknown*,D3D_FEATURE_LEVEL,REFIID,void**))dlsym(lib,"D3D12CreateDevice");auto serialize=(HRESULT(*)(const D3D12_ROOT_SIGNATURE_DESC*,D3D_ROOT_SIGNATURE_VERSION,ID3DBlob**,ID3DBlob**))dlsym(lib,"D3D12SerializeRootSignature");
 Ptr<IDXCoreAdapterFactory>factory;check(factoryfn(IID_IDXCoreAdapterFactory,(void**)&factory.p),"factory");Ptr<IDXCoreAdapterList>adapters;GUID attr=DXCORE_ADAPTER_ATTRIBUTE_D3D12_CORE_COMPUTE;check(factory->CreateAdapterList(1,&attr,IID_IDXCoreAdapterList,(void**)&adapters.p),"adapters");if(!adapters->GetAdapterCount())throw std::runtime_error("no adapter");
 Ptr<IDXCoreAdapter>adapter;check(adapters->GetAdapter(0,IID_IDXCoreAdapter,(void**)&adapter.p),"adapter");size_t len;check(adapter->GetPropertySize(DXCoreAdapterProperty::DriverDescription,&len),"description size");std::vector<char>name(len);check(adapter->GetProperty(DXCoreAdapterProperty::DriverDescription,len,name.data()),"description");
 Ptr<ID3D12Device>dev;check(devfn(adapter,D3D_FEATURE_LEVEL_11_0,IID_ID3D12Device,(void**)&dev.p),"device");
 Ptr<ID3D12CommandQueue>queue;D3D12_COMMAND_QUEUE_DESC q{};q.Type=D3D12_COMMAND_LIST_TYPE_COMPUTE;check(dev->CreateCommandQueue(&q,IID_ID3D12CommandQueue,(void**)&queue.p),"queue");
 Ptr<ID3D12CommandAllocator>allocator;check(dev->CreateCommandAllocator(q.Type,IID_ID3D12CommandAllocator,(void**)&allocator.p),"allocator");Ptr<ID3D12GraphicsCommandList>list;check(dev->CreateCommandList(0,q.Type,allocator,nullptr,IID_ID3D12GraphicsCommandList,(void**)&list.p),"command list");check(list->Close(),"initial close");
 Ptr<ID3D12Fence>fence;check(dev->CreateFence(0,D3D12_FENCE_FLAG_NONE,IID_ID3D12Fence,(void**)&fence.p),"fence");
 D3D12_ROOT_PARAMETER params[4]{};params[0].ParameterType=D3D12_ROOT_PARAMETER_TYPE_32BIT_CONSTANTS;params[0].Constants={0,0,2};params[1].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV;params[1].Descriptor={0,0};params[2].ParameterType=D3D12_ROOT_PARAMETER_TYPE_SRV;params[2].Descriptor={1,0};params[3].ParameterType=D3D12_ROOT_PARAMETER_TYPE_UAV;params[3].Descriptor={0,0};D3D12_ROOT_SIGNATURE_DESC rs{};rs.NumParameters=4;rs.pParameters=params;Ptr<ID3DBlob>blob,error;check(serialize(&rs,D3D_ROOT_SIGNATURE_VERSION_1,&blob.p,&error.p),"serialize signature");Ptr<ID3D12RootSignature>root;check(dev->CreateRootSignature(0,blob->GetBufferPointer(),blob->GetBufferSize(),IID_ID3D12RootSignature,(void**)&root.p),"signature");
 D3D12_COMPUTE_PIPELINE_STATE_DESC ps{};ps.pRootSignature=root;ps.CS={shader.data(),shader.size()};Ptr<ID3D12PipelineState>pipeline;auto pt=Clock::now();check(dev->CreateComputePipelineState(&ps,IID_ID3D12PipelineState,(void**)&pipeline.p),"pipeline");double pipeline_ms=ms(pt);
 auto buffer=[&](uint64_t bytes,D3D12_HEAP_TYPE ht,D3D12_RESOURCE_STATES state,D3D12_RESOURCE_FLAGS flags,ID3D12Resource**out){D3D12_HEAP_PROPERTIES heap{};heap.Type=ht;D3D12_RESOURCE_DESC d{};d.Dimension=D3D12_RESOURCE_DIMENSION_BUFFER;d.Width=bytes;d.Height=1;d.DepthOrArraySize=1;d.MipLevels=1;d.SampleDesc.Count=1;d.Layout=D3D12_TEXTURE_LAYOUT_ROW_MAJOR;d.Flags=flags;check(dev->CreateCommittedResource(&heap,D3D12_HEAP_FLAG_NONE,&d,state,nullptr,IID_ID3D12Resource,(void**)out),"buffer");};
 auto upload_begin=Clock::now();Ptr<ID3D12Resource>eb,fb,zb,out,read;
 buffer(m*8,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,D3D12_RESOURCE_FLAG_NONE,&eb.p);buffer(n*4,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,D3D12_RESOURCE_FLAG_NONE,&fb.p);buffer(n*4,D3D12_HEAP_TYPE_UPLOAD,D3D12_RESOURCE_STATE_GENERIC_READ,D3D12_RESOURCE_FLAG_NONE,&zb.p);buffer(n*4,D3D12_HEAP_TYPE_DEFAULT,D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_FLAG_ALLOW_UNORDERED_ACCESS,&out.p);buffer(n*4,D3D12_HEAP_TYPE_READBACK,D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_FLAG_NONE,&read.p);
 auto fill=[&](ID3D12Resource*r,const void*data,size_t sz){void*p;D3D12_RANGE range{0,0};check(r->Map(0,&range,&p),"map upload");memcpy(p,data,sz);r->Unmap(0,nullptr);};fill(eb,edges.data(),m*8);fill(fb,front.data(),n*4);fill(zb,zero.data(),n*4);double upload_ms=ms(upload_begin);double init_ms=ms(begin);
 std::cout<<"{\"device\":\""<<name.data()<<"\",\"nodes\":"<<n<<",\"edges\":"<<m<<",\"init_ms\":"<<init_ms<<",\"pipeline_ms\":"<<pipeline_ms<<",\"upload_allocate_ms\":"<<upload_ms<<",\"csr_build_ms\":"<<csr_build_ms<<",\"samples\":[";
 uint64_t ticket=0;int repetitions=std::stoi(argv[3]);for(int rep=0;rep<repetitions;rep++){
 auto full=Clock::now();auto cpu=Clock::now();std::fill(observed.begin(),observed.end(),0);for(auto e:edges)if(front[e.a])observed[e.b]=1;double cpu_ms=ms(cpu);if(observed!=expected)throw std::runtime_error("CPU oracle");
 auto sparse=Clock::now();std::fill(observed.begin(),observed.end(),0);for(uint32_t i=0;i<n;i++)if(front[i])for(uint32_t j=offsets[i];j<offsets[i+1];j++)observed[adj[j]]=1;double csr_ms=ms(sparse);if(observed!=expected)throw std::runtime_error("CSR oracle");
 auto gpu=Clock::now();check(allocator->Reset(),"allocator reset");check(list->Reset(allocator,pipeline),"list reset");list->CopyBufferRegion(out,0,zb,0,n*4);
 auto barrier=[&](D3D12_RESOURCE_STATES a,D3D12_RESOURCE_STATES b){D3D12_RESOURCE_BARRIER x{};x.Type=D3D12_RESOURCE_BARRIER_TYPE_TRANSITION;x.Transition={out,0,a,b};list->ResourceBarrier(1,&x);};barrier(D3D12_RESOURCE_STATE_COPY_DEST,D3D12_RESOURCE_STATE_UNORDERED_ACCESS);list->SetComputeRootSignature(root);uint32_t bounds[2]={m,n};list->SetComputeRoot32BitConstants(0,2,bounds,0);list->SetComputeRootShaderResourceView(1,eb->GetGPUVirtualAddress());list->SetComputeRootShaderResourceView(2,fb->GetGPUVirtualAddress());list->SetComputeRootUnorderedAccessView(3,out->GetGPUVirtualAddress());
 // Flatten dispatch beyond the x dimension limit by advancing root SRV and edge count.
 for(uint32_t base=0;base<m;){uint32_t count=std::min<uint32_t>(m-base,65535*64);bounds[0]=count;list->SetComputeRoot32BitConstants(0,2,bounds,0);list->SetComputeRootShaderResourceView(1,eb->GetGPUVirtualAddress()+uint64_t(base)*8);list->Dispatch((count+63)/64,1,1);base+=count;}
 barrier(D3D12_RESOURCE_STATE_UNORDERED_ACCESS,D3D12_RESOURCE_STATE_COPY_SOURCE);list->CopyBufferRegion(read,0,out,0,n*4);barrier(D3D12_RESOURCE_STATE_COPY_SOURCE,D3D12_RESOURCE_STATE_COPY_DEST);check(list->Close(),"close");ID3D12CommandList* commands[]={list};queue->ExecuteCommandLists(1,commands);check(queue->Signal(fence,++ticket),"signal");double submit_ms=ms(gpu);auto sync=Clock::now();while(fence->GetCompletedValue()<ticket){if(ms(sync)>30000)throw std::runtime_error("GPU fence timeout");std::this_thread::yield();}double sync_ms=ms(sync);
 auto rt=Clock::now();void*p;D3D12_RANGE range{0,n*4ull};check(read->Map(0,&range,&p),"map readback");bool equal=!memcmp(p,expected.data(),n*4);D3D12_RANGE written{0,0};read->Unmap(0,&written);double read_ms=ms(rt);if(!equal)throw std::runtime_error("GPU oracle mismatch");double gpu_ms=ms(gpu);
 if(rep)std::cout<<",";std::cout<<"{\"cpu_ms\":"<<cpu_ms<<",\"csr_ms\":"<<csr_ms<<",\"record_submit_ms\":"<<submit_ms<<",\"sync_ms\":"<<sync_ms<<",\"read_validate_ms\":"<<read_ms<<",\"gpu_full_ms\":"<<gpu_ms<<",\"equal\":true}";
 }std::cout<<"]}"<<std::endl;return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<std::endl;return 1;}}

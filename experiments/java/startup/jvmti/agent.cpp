// Bounded diagnostic JVMTI adapter. No bytecode transformation or MethodEntry.
#include <jvmti.h>
#include <jni.h>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>
#include <algorithm>

namespace {
jvmtiEnv* ti=nullptr;
std::string output,mode;
int interval_ms=4,depth=24;
bool want_classes=false,want_cpu=false,want_alloc=false;
std::atomic<bool> stopping=false,live=false;
std::atomic<uint64_t> early_alloc_events=0;
std::mutex guard;
auto begin=std::chrono::steady_clock::now();
uint64_t now(){return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-begin).count();}
struct Aggregate{uint64_t count=0,weight=0;};
struct ClassEvent{std::string name;uint64_t loaded=0,prepared=0;};
struct ThreadData{jlong previous=-1;};
std::vector<ThreadData*> thread_records;
std::unordered_map<std::string,ClassEvent> classes;
std::unordered_map<std::string,Aggregate> cpu,allocations;
std::unordered_map<int,uint64_t> errors;
uint64_t class_loads=0,class_prepares=0,cpu_passes=0,cpu_dropped=0,alloc_events=0,alloc_dropped=0,cpu_unavailable=0,callback_ns=0,sampler_ns=0;
jvmtiCapabilities granted{};
jvmtiTimerInfo cpu_timer{};
std::string quote(const std::string&s){std::string r="\"";const char*h="0123456789abcdef";for(unsigned char c:s){if(c=='"'||c=='\\'){r+='\\';r+=c;}else if(c<32){r+="\\u00";r+=h[c>>4];r+=h[c&15];}else r+=c;}return r+'"';}
void note(jvmtiError e){if(e!=JVMTI_ERROR_NONE){std::lock_guard<std::mutex> lock(guard);errors[e]++;}}
void free_ti(void*p){if(p)ti->Deallocate(static_cast<unsigned char*>(p));}
std::string signature(jclass klass){char*text=nullptr;jvmtiError e=ti->GetClassSignature(klass,&text,nullptr);if(e!=JVMTI_ERROR_NONE){note(e);return "?";}std::string r=text?text:"?";free_ti(text);if(r.size()>512)r.resize(512);return r;}
bool framework(const std::string&s){return s.rfind("Lgroovy/",0)==0||s.rfind("Lorg/codehaus/groovy/",0)==0||s.rfind("Lorg/apache/groovy/",0)==0||s.rfind("Lpicocli/",0)==0;}
std::string symbol(JNIEnv*env,jmethodID method){char*name=nullptr,*desc=nullptr;jclass klass=nullptr;
 jvmtiError e=ti->GetMethodDeclaringClass(method,&klass);if(e!=JVMTI_ERROR_NONE){note(e);return "?";}
 std::string sig=signature(klass);env->DeleteLocalRef(klass);
 e=ti->GetMethodName(method,&name,&desc,nullptr);if(e!=JVMTI_ERROR_NONE){note(e);return sig+"#?";}
 std::string r=sig+"#"+(name?name:"?")+(desc?desc:"");free_ti(name);free_ti(desc);if(r.size()>512)r.resize(512);return r;
}
std::string stack(JNIEnv*env,jvmtiFrameInfo*frames,int count){std::vector<std::string> names;bool hit=false;for(int i=0;i<count;i++){names.push_back(symbol(env,frames[i].method));hit|=framework(names.back());}
 if(!hit)return {};std::string r;for(auto&s:names){if(r.size()+s.size()>4096)break;if(!r.empty())r+='\n';r+=s;}return r;
}
void JNICALL class_load(jvmtiEnv*,JNIEnv*,jthread,jclass klass){auto t=now();std::string sig=signature(klass);std::lock_guard<std::mutex>lock(guard);class_loads++;if(framework(sig)&&classes.size()<4096){auto&v=classes[sig];v.name=sig;v.loaded=t;}callback_ns+=now()-t;}
void JNICALL class_prepare(jvmtiEnv*,JNIEnv*,jthread,jclass klass){auto t=now();std::string sig=signature(klass);std::lock_guard<std::mutex>lock(guard);class_prepares++;if(framework(sig)&&classes.size()<4096){auto&v=classes[sig];v.name=sig;v.prepared=t;}callback_ns+=now()-t;}
void JNICALL allocation(jvmtiEnv*,JNIEnv*env,jthread thread,jobject,jclass klass,jlong size){if(!live.load()){early_alloc_events++;return;}if(stopping.load())return;auto t=now();jvmtiFrameInfo frames[24];jint count=0;jvmtiError e=ti->GetStackTrace(thread,0,std::min(depth,24),frames,&count);
 std::string trace=e==JVMTI_ERROR_NONE?stack(env,frames,count):"";if(e!=JVMTI_ERROR_NONE)note(e);
 std::string type=trace.empty()?"":signature(klass);
 std::lock_guard<std::mutex>lock(guard);alloc_events++;if(!trace.empty()){std::string key=type+'\n'+trace;if(allocations.size()<1024||allocations.count(key)){auto&v=allocations[key];v.count++;v.weight+=size;}else alloc_dropped++;}callback_ns+=now()-t;
}
void JNICALL sample(jvmtiEnv*,JNIEnv*env,void*){
 while(!stopping.load()){
  auto t=now();jvmtiStackInfo*info=nullptr;jint count=0;jvmtiError e=ti->GetAllStackTraces(depth,&info,&count);
  if(e!=JVMTI_ERROR_NONE){note(e);break;}
  for(int i=0;i<count&&!stopping.load();i++){
   if(info[i].frame_count==0)continue;
   jlong value=0;e=ti->GetThreadCpuTime(info[i].thread,&value);
   if(e!=JVMTI_ERROR_NONE){std::lock_guard<std::mutex>lock(guard);cpu_unavailable++;continue;}
   void*p=nullptr;ti->GetThreadLocalStorage(info[i].thread,&p);auto*record=static_cast<ThreadData*>(p);
   if(!record){std::lock_guard<std::mutex>lock(guard);if(thread_records.size()<256){record=new ThreadData;thread_records.push_back(record);ti->SetThreadLocalStorage(info[i].thread,record);}}
   jlong delta=record&&record->previous>=0?value-record->previous:0;if(record)record->previous=value;
   if(delta>0){std::string key=stack(env,info[i].frame_buffer,info[i].frame_count);if(!key.empty()){std::lock_guard<std::mutex>lock(guard);if(cpu.size()<1024||cpu.count(key)){auto&v=cpu[key];v.count++;v.weight+=delta;}else cpu_dropped++;}}
  }
  for(int i=0;i<count;i++)env->DeleteLocalRef(info[i].thread);
  free_ti(info);{std::lock_guard<std::mutex>lock(guard);cpu_passes++;sampler_ns+=now()-t;}
  std::this_thread::sleep_for(std::chrono::milliseconds(interval_ms));
 }
}
void JNICALL vm_init(jvmtiEnv*,JNIEnv*env,jthread){live=true;if(!want_cpu)return;note(ti->GetThreadCpuTimerInfo(&cpu_timer));jclass klass=env->FindClass("java/lang/Thread");jmethodID ctor=env->GetMethodID(klass,"<init>","()V");jthread thread=static_cast<jthread>(env->NewObject(klass,ctor));note(ti->RunAgentThread(thread,sample,nullptr,JVMTI_THREAD_MIN_PRIORITY));env->DeleteLocalRef(thread);env->DeleteLocalRef(klass);}
void write_aggregates(std::ofstream&out,const char*name,const std::unordered_map<std::string,Aggregate>&values){std::vector<std::pair<std::string,Aggregate>> rows(values.begin(),values.end());std::sort(rows.begin(),rows.end(),[](auto&a,auto&b){return a.second.weight>b.second.weight;});out<<','<<quote(name)<<":[";bool first=true;for(auto&row:rows){if(!first)out<<',';first=false;out<<"{\"stack\":"<<quote(row.first)<<",\"samples\":"<<row.second.count<<",\"weight\":"<<row.second.weight<<'}';}out<<']';}
void JNICALL death(jvmtiEnv*,JNIEnv*){stopping=true;live=false;std::lock_guard<std::mutex>lock(guard);std::ofstream out(output);out<<"{\"schema\":\"GAIA-JVMTI-1\",\"mode\":"<<quote(mode)<<",\"cpu_interval_ms\":"<<interval_ms<<",\"allocation_interval_bytes\":65536,\"max_depth\":"<<depth
 <<",\"capabilities\":{\"thread_cpu\":"<<(granted.can_get_thread_cpu_time?"true":"false")<<",\"sampled_allocation\":"<<(granted.can_generate_sampled_object_alloc_events?"true":"false")<<",\"method_entry\":"<<(granted.can_generate_method_entry_events?"true":"false")<<",\"class_hook\":"<<(granted.can_generate_all_class_hook_events?"true":"false")<<",\"retransform\":"<<(granted.can_retransform_classes?"true":"false")<<"},\"cpu_timer_kind\":"<<cpu_timer.kind
 <<",\"class_load_events\":"<<class_loads<<",\"class_prepare_events\":"<<class_prepares<<",\"cpu_passes\":"<<cpu_passes<<",\"cpu_dropped\":"<<cpu_dropped<<",\"cpu_unavailable_thread_observations\":"<<cpu_unavailable<<",\"early_allocation_events_skipped\":"<<early_alloc_events.load()<<",\"allocation_events\":"<<alloc_events<<",\"allocation_dropped\":"<<alloc_dropped<<",\"callback_ns\":"<<callback_ns<<",\"sampler_ns\":"<<sampler_ns;
 out<<",\"classes\":[";bool first=true;for(auto&row:classes){if(!first)out<<',';first=false;auto&v=row.second;out<<"{\"name\":"<<quote(v.name)<<",\"load_ns\":"<<v.loaded<<",\"prepare_ns\":"<<v.prepared<<'}';}out<<']';write_aggregates(out,"cpu_stacks",cpu);write_aggregates(out,"allocation_stacks",allocations);
 out<<",\"errors\":{";first=true;for(auto&row:errors){if(!first)out<<',';first=false;out<<quote(std::to_string(row.first))<<':'<<row.second;}out<<"}}\n";
}
}
extern "C" JNIEXPORT jint JNICALL Agent_OnLoad(JavaVM*vm,char*options,void*){
 if(vm->GetEnv(reinterpret_cast<void**>(&ti),JVMTI_VERSION_1_2)!=JNI_OK)return JNI_ERR;
 std::string args=options?options:"";auto colon=args.find(':');if(colon==std::string::npos)return JNI_ERR;mode=args.substr(0,colon);output=args.substr(colon+1);if(output.empty())return JNI_ERR;
 want_classes=mode=="classes"||mode=="cpu"||mode=="alloc";want_cpu=mode=="cpu";want_alloc=mode=="alloc";if(mode!="idle"&&!want_classes)return JNI_ERR;
 jvmtiCapabilities requested{};requested.can_get_thread_cpu_time=want_cpu;requested.can_generate_sampled_object_alloc_events=want_alloc;
 if(ti->AddCapabilities(&requested)!=JVMTI_ERROR_NONE)return JNI_ERR;if(ti->GetCapabilities(&granted)!=JVMTI_ERROR_NONE)return JNI_ERR;
 if(want_cpu&&!granted.can_get_thread_cpu_time)return JNI_ERR;
 if(want_alloc){if(!granted.can_generate_sampled_object_alloc_events)return JNI_ERR;if(ti->SetHeapSamplingInterval(65536)!=JVMTI_ERROR_NONE)return JNI_ERR;}
 jvmtiEventCallbacks callbacks{};callbacks.VMInit=vm_init;callbacks.VMDeath=death;callbacks.ClassLoad=class_load;callbacks.ClassPrepare=class_prepare;callbacks.SampledObjectAlloc=allocation;
 if(ti->SetEventCallbacks(&callbacks,sizeof(callbacks))!=JVMTI_ERROR_NONE)return JNI_ERR;
 for(auto event:{JVMTI_EVENT_VM_INIT,JVMTI_EVENT_VM_DEATH})if(ti->SetEventNotificationMode(JVMTI_ENABLE,event,nullptr)!=JVMTI_ERROR_NONE)return JNI_ERR;
 if(want_classes)for(auto event:{JVMTI_EVENT_CLASS_LOAD,JVMTI_EVENT_CLASS_PREPARE})if(ti->SetEventNotificationMode(JVMTI_ENABLE,event,nullptr)!=JVMTI_ERROR_NONE)return JNI_ERR;
 if(want_alloc&&ti->SetEventNotificationMode(JVMTI_ENABLE,JVMTI_EVENT_SAMPLED_OBJECT_ALLOC,nullptr)!=JVMTI_ERROR_NONE)return JNI_ERR;
 return JNI_OK;
}

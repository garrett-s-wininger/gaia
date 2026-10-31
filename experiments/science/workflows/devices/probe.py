import ctypes,json,pathlib,time
from d3d12_probe import GUID

def method(pointer,index,restype,*types):
 table=ctypes.cast(pointer,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
 return ctypes.CFUNCTYPE(restype,ctypes.c_void_p,*types)(table[index])
def release(pointer):
 if pointer:method(pointer,2,ctypes.c_uint32)(pointer)
def main():
 start=time.perf_counter_ns();result={'boundary':'approved-host-process','dxg_present':pathlib.Path('/dev/dxg').exists(),'source':'https://raw.githubusercontent.com/microsoft/DirectX-Headers/main/include/directx/dxcore_interface.h','lists':[]};factory=ctypes.c_void_p()
 try:
  core=ctypes.CDLL('/usr/lib/wsl/lib/libdxcore.so',mode=ctypes.RTLD_GLOBAL);lib=ctypes.CDLL('/usr/lib/wsl/lib/libd3d12.so');create=core.DXCoreCreateAdapterFactory;create.argtypes=[ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p)];create.restype=ctypes.c_int32
  hr=create(ctypes.byref(GUID('78ee5945-c36e-4b13-a669-005dd11c0f06')),ctypes.byref(factory));result['factory_hresult']=f'0x{hr&0xffffffff:08x}'
  if hr<0 or not factory:print(json.dumps(result));return
  device_create=lib.D3D12CreateDevice;device_create.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p)];device_create.restype=ctypes.c_int32
  attrs=[('generic-ml','b71b0d41-1088-422f-a27c-0250b7d3a988'),('npu-hardware-attribute','d46140c4-add7-451b-9e56-06fe8c3b58ed'),('compute-accelerator-hardware-attribute','e0b195da-58ef-4a22-90f1-1f28169cab8d'),('all',None),('d3d12-graphics','0c9ece4d-2f6e-4f01-8c96-e89e331b47b1'),('d3d12-core-compute','248e2800-a793-4724-abaa-23a6de1be090')]
  for name,attribute in attrs:
   adapters=ctypes.c_void_p();attr=GUID(attribute) if attribute else None
   hr=method(factory,3,ctypes.c_int32,ctypes.c_uint32,ctypes.POINTER(GUID),ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p))(factory,1 if attr else 0,ctypes.byref(attr) if attr else None,ctypes.byref(GUID('526c7776-40e9-459b-b711-f32ad76dfc28')),ctypes.byref(adapters));row={'filter':name,'hresult':f'0x{hr&0xffffffff:08x}','adapters':[]};result['lists'].append(row)
   try:
    if hr<0 or not adapters:continue
    count=method(adapters,4,ctypes.c_uint32)(adapters);row['count']=count
    for index in range(min(count,32)):
     adapter=ctypes.c_void_p();hr=method(adapters,3,ctypes.c_int32,ctypes.c_uint32,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p))(adapters,index,ctypes.byref(GUID('f0db4c7f-fe5a-42a2-bd62-f2a6cf6fc83e')),ctypes.byref(adapter));item={'index':index,'hresult':f'0x{hr&0xffffffff:08x}','device_attempts':[]};row['adapters'].append(item)
     try:
      if hr<0 or not adapter:continue
      size=ctypes.c_size_t();hr=method(adapter,7,ctypes.c_int32,ctypes.c_uint32,ctypes.POINTER(ctypes.c_size_t))(adapter,2,ctypes.byref(size))
      if hr>=0 and 0<size.value<1048576:
       buffer=ctypes.create_string_buffer(size.value);hr=method(adapter,6,ctypes.c_int32,ctypes.c_uint32,ctypes.c_size_t,ctypes.c_void_p)(adapter,2,size.value,buffer)
       if hr>=0:item['description']=buffer.value.decode('utf8','replace')
      hardware=ctypes.c_bool();hr=method(adapter,6,ctypes.c_int32,ctypes.c_uint32,ctypes.c_size_t,ctypes.c_void_p)(adapter,11,ctypes.sizeof(hardware),ctypes.byref(hardware));item['is_hardware']=hardware.value if hr>=0 else None
      for level in [0xb000,0x1000]:
       device=ctypes.c_void_p();hr=device_create(adapter,level,ctypes.byref(GUID('189819f1-1db6-4b57-be54-1821339b85f7')),ctypes.byref(device));entry={'feature_level':hex(level),'hresult':f'0x{hr&0xffffffff:08x}','device_nonnull':bool(device)};item['device_attempts'].append(entry)
       if hr>=0 and device:entry['nodes']=method(device,7,ctypes.c_uint32)(device)
       release(device)
     finally:release(adapter)
   finally:release(adapters)
 except Exception as error:result['error']=type(error).__name__+': '+str(error)
 finally:release(factory)
 result['elapsed_ns']=time.perf_counter_ns()-start;print(json.dumps(result),flush=True)
if __name__=='__main__':main()

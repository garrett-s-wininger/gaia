import ctypes,json,pathlib,uuid,time
class GUID(ctypes.Structure):
 _fields_=[('Data1',ctypes.c_uint32),('Data2',ctypes.c_uint16),('Data3',ctypes.c_uint16),('Data4',ctypes.c_uint8*8)]
 def __init__(self,value):
  super().__init__();ctypes.memmove(ctypes.byref(self),uuid.UUID(value).bytes_le,16)
def main():
 start=time.perf_counter_ns();result={'boundary':'approved-host-process','dxg_present':pathlib.Path('/dev/dxg').exists(),'signature_source':'https://raw.githubusercontent.com/microsoft/DirectX-Headers/main/include/directx/d3d12.idl','wsl_abi_source':'https://raw.githubusercontent.com/microsoft/DirectX-Headers/main/include/wsl/stubs/basetsd.h'}
 try:
  dxcore=ctypes.CDLL('/usr/lib/wsl/lib/libdxcore.so',mode=ctypes.RTLD_GLOBAL)
  lib=ctypes.CDLL('/usr/lib/wsl/lib/libd3d12.so')
  create=lib.D3D12CreateDevice;create.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p)];create.restype=ctypes.c_int32
  device=ctypes.c_void_p();iid=GUID('189819f1-1db6-4b57-be54-1821339b85f7');hr=create(None,0xb000,ctypes.byref(iid),ctypes.byref(device));result.update(hresult=hr,hresult_hex=f'0x{hr & 0xffffffff:08x}',device_nonnull=bool(device))
  if hr>=0 and device:
   vtable=ctypes.cast(device,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
   count=ctypes.CFUNCTYPE(ctypes.c_uint32,ctypes.c_void_p)(vtable[7]);result['nodes']=count(device)
   release=ctypes.CFUNCTYPE(ctypes.c_uint32,ctypes.c_void_p)(vtable[2]);result['remaining_refs_after_release']=release(device)
 except Exception as error:result['error']=type(error).__name__+': '+str(error)
 result['elapsed_ns']=time.perf_counter_ns()-start;print(json.dumps(result),flush=True)
if __name__=='__main__':main()

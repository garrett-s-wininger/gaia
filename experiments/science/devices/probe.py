"""Enumerate exposed compute APIs; a CPU Vulkan provider is not GPU evidence."""
import argparse
import ctypes as C
import ctypes.util
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess


class App(C.Structure):
    _fields_=[('type',C.c_uint32),('next',C.c_void_p),('name',C.c_char_p),('version',C.c_uint32),
              ('engine',C.c_char_p),('engine_version',C.c_uint32),('api',C.c_uint32)]


class InstanceInfo(C.Structure):
    _fields_=[('type',C.c_uint32),('next',C.c_void_p),('flags',C.c_uint32),('app',C.POINTER(App)),
              ('layers',C.c_uint32),('layer_names',C.c_void_p),('extensions',C.c_uint32),('extension_names',C.c_void_p)]


def vulkan():
    lib=C.CDLL(ctypes.util.find_library('vulkan') or 'libvulkan.so.1')
    create=lib.vkCreateInstance;create.argtypes=[C.POINTER(InstanceInfo),C.c_void_p,C.POINTER(C.c_void_p)];create.restype=C.c_int32
    enum=lib.vkEnumeratePhysicalDevices;enum.argtypes=[C.c_void_p,C.POINTER(C.c_uint32),C.POINTER(C.c_void_p)];enum.restype=C.c_int32
    props=lib.vkGetPhysicalDeviceProperties;props.argtypes=[C.c_void_p,C.c_void_p]
    destroy=lib.vkDestroyInstance;destroy.argtypes=[C.c_void_p,C.c_void_p]
    app=App(0,None,b'Gaia compute capability',1,b'Gaia',1,1<<22)
    info=InstanceInfo(1,None,0,C.pointer(app),0,None,0,None);handle=C.c_void_p()
    status=create(C.byref(info),None,C.byref(handle));result={'create_status':status,'devices':[]}
    if status:return result
    try:
        count=C.c_uint32();result['enumerate_status']=enum(handle,C.byref(count),None)
        if result['enumerate_status']:return result
        devices=(C.c_void_p*count.value)();status=enum(handle,C.byref(count),devices);result['enumerate_status']=status
        if status:return result
        for device in devices:
            # The fixed header is followed by implementation-independent limits.
            # A generously sized aligned allocation avoids binding that large tail.
            storage=(C.c_uint64*512)();props(device,C.byref(storage));body=bytes(storage)
            words=(C.c_uint32*5).from_buffer_copy(body[:20]);name=body[20:276].split(b'\0',1)[0].decode(errors='replace')
            kind={0:'other',1:'integrated_gpu',2:'discrete_gpu',3:'virtual_gpu',4:'cpu'}.get(words[4],'unknown')
            result['devices'].append({'name':name,'type':kind,'vendor_id':words[2],'device_id':words[3],
                                      'hardware_gpu_candidate':kind in {'integrated_gpu','discrete_gpu'}})
    finally:destroy(handle,None)
    return result


def opencl():
    lib=C.CDLL(ctypes.util.find_library('OpenCL') or 'libOpenCL.so.1')
    fn=lib.clGetPlatformIDs;fn.argtypes=[C.c_uint32,C.c_void_p,C.POINTER(C.c_uint32)];fn.restype=C.c_int32
    count=C.c_uint32();status=fn(0,None,C.byref(count))
    return {'platform_status':status,'platform_count':count.value,'scope':'Enumeration only; platform presence does not establish a working accelerator.'}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result={'schema_version':1,'platform':platform.platform(),'cpu_affinity':sorted(os.sched_getaffinity(0)),
            'device_paths':{n:Path(n).exists() for n in ['/dev/dxg','/dev/dri','/dev/kfd','/dev/accel','/sys/class/infiniband']},
            'scope':'Capabilities exposed to this process. Missing device nodes or API failure do not prove the host lacks hardware.'}
    for name,fn in [('vulkan',vulkan),('opencl',opencl)]:
        try:result[name]=fn()
        except Exception as error:result[name]={'error_type':type(error).__name__,'error':str(error)}
    result['hardware_gpu_exposed']=any(d['hardware_gpu_candidate'] for d in result.get('vulkan',{}).get('devices',[]))
    ffmpeg=shutil.which('ffmpeg')
    if ffmpeg:
        proc=subprocess.run([ffmpeg,'-hide_banner','-hwaccels'],capture_output=True,text=True)
        result['ffmpeg_compiled_interfaces']={'exit':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr,
            'scope':'Compiled API list, not working-device confirmation.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()

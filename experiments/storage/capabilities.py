"""Read-only mechanism inventory; optional user-mode-only UFFD open is immediately closed."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import sys


def probe():
    status=Path('/proc/self/status').read_text().splitlines();caps=next(line.split()[1] for line in status if line.startswith('CapEff:'));mounts=Path('/proc/mounts').read_text().splitlines();cgroup=next((line.split()[3] for line in mounts if line.split()[1]=='/sys/fs/cgroup'),'absent')
    result=dict(platform=platform.platform(),python=sys.version,python_binary_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest(),effective_capabilities_hex=caps,cgroup_mount_options=cgroup,fuse_device_present=Path('/dev/fuse').exists(),userfaultfd_device_present=Path('/dev/userfaultfd').exists(),unprivileged_userfaultfd=Path('/proc/sys/vm/unprivileged_userfaultfd').read_text().strip())
    if platform.machine()=='x86_64':
        libc=ctypes.CDLL(None,use_errno=True);fd=libc.syscall(323,os.O_CLOEXEC|os.O_NONBLOCK|1);result['userfaultfd_user_mode_only_descriptor_opened']=fd>=0;result['userfaultfd_probe_errno']=ctypes.get_errno() if fd<0 else 0
        if fd>=0:os.close(fd)
    return result


if __name__=='__main__':print(json.dumps(probe(),indent=2))

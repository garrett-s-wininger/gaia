"""Read bounded PE/CLI ReadyToRun header facts without loading an assembly."""
from pathlib import Path
import struct

def inspect(path):
    body=Path(path).read_bytes()
    def unpack(fmt,offset):
        if offset<0 or offset+struct.calcsize(fmt)>len(body):raise ValueError('PE bounds')
        return struct.unpack_from(fmt,body,offset)
    if body[:2]!=b'MZ':raise ValueError('not PE')
    pe=unpack('<I',0x3c)[0]
    if body[pe:pe+4]!=b'PE\0\0':raise ValueError('bad PE signature')
    machine,sections=unpack('<HH',pe+4);size=unpack('<H',pe+20)[0];optional=pe+24;magic=unpack('<H',optional)[0]
    if magic not in (0x10b,0x20b):raise ValueError('bad PE optional header')
    directory=optional+(112 if magic==0x20b else 96);cli_rva,cli_size=unpack('<II',directory+14*8)
    def offset(rva):
        for i in range(sections):
            virtual_size,virtual_address,raw_size,raw=unpack('<IIII',optional+size+i*40+8)
            if virtual_address<=rva<virtual_address+max(virtual_size,raw_size):return raw+rva-virtual_address
        raise ValueError('unmapped RVA')
    if not cli_rva:return dict(machine=machine,managed=False)
    cli=offset(cli_rva);rva,native_size=unpack('<II',cli+64);signature=body[offset(rva):offset(rva)+4] if rva else b''
    return dict(machine=machine,managed=True,ready_to_run=signature==b'RTR\0',native_header_bytes=native_size,
                il_flags=unpack('<I',cli+16)[0])

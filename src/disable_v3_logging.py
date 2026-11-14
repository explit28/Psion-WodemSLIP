"""Disable only the file-logger entry in the exact, user-tested v3 image.

Keep image size/layout, import/export tables, relocation data, trace-call
wrappers and all networking repair code byte-for-byte. Update the E32 code
checksum after replacing PUSH {r4-r11,lr} with MOV pc,lr at logger entry.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys

V3_SHA256='10e42f8a255643f2a8a377ed2d2607fb0d00fb2d73016c8b092885c7accd1dce'
LOGGER_RVA=0x1410

def patch(original):
    if len(original)!=8120 or hashlib.sha256(original).hexdigest()!=V3_SHA256:
        raise ValueError('Input must be the exact user-tested 8120-byte v3 SLIP.NIF')
    b=bytearray(original);start=struct.unpack_from('<I',b,100)[0];size=struct.unpack_from('<I',b,48)[0]
    entry=start+LOGGER_RVA
    if struct.unpack_from('<I',b,entry)[0]!=0xe92d4ff0:raise ValueError('Unexpected logger entry')
    struct.pack_into('<I',b,entry,0xe1a0f00e)  # MOV pc,lr; no register/flag changes.
    checksum=sum(struct.unpack('<'+'I'*(size//4),b[start:start+size]))&0xffffffff
    struct.pack_into('<I',b,24,checksum)
    allowed=set(range(entry,entry+4))|set(range(24,28))
    changed=[p for p,(x,y) in enumerate(zip(original,b)) if x!=y]
    if len(b)!=len(original) or not changed or not set(changed)<=allowed:
        raise AssertionError('Unexpected change outside logger instruction/checksum')
    report={'basis':'Exact user-tested v3','input_sha256':V3_SHA256,'output_sha256':hashlib.sha256(b).hexdigest(),'size':len(b),'logger_entry_rva':hex(LOGGER_RVA),'logger_entry_file_offset':hex(entry),'patch':'PUSH {r4-r11,lr} -> MOV pc,lr','changed_byte_offsets':changed,'allowed_modified_words':[hex(24),hex(entry)],'layout_imports_exports_relocations_network_code':'Byte-identical to v3','logging':'File logger returns immediately; existing trace wrappers/imports/dead logger bytes retained; no log writes or file creation through logger','hardware_status':'Minimal no-log patch not yet device-tested'}
    return bytes(b),report

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Usage: python disable_v3_logging.py v3-SLIP.NIF output-SLIP.NIF')
    data,report=patch(Path(sys.argv[1]).read_bytes());Path(sys.argv[2]).write_bytes(data)
    print(json.dumps(report,indent=2))

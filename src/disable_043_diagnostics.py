"""Remove active diagnostics from the exact working 0.4.3 driver.

Keep functional code, layout and native tables byte-identical. Three RAM
diagnostic entry points return immediately, and allocation reverts to the
original object size. Unreachable diagnostic bodies/imports remain inert.
"""
from pathlib import Path
import hashlib,json,struct

SHA256='7d131b4bd6f0654eac93df3e6ffd78faf21b5ab16e5f0f4678ea8ba93d6c721f'
ORIGINAL_OBJECT_SIZE=0x8c4

def patch(original,reference):
    if hashlib.sha256(original).hexdigest()!=SHA256:
        raise ValueError('Input must be the exact user-tested 0.4.3 diagnostic driver')
    b=bytearray(original);u=lambda p:struct.unpack_from('<I',b,p)[0]
    start,size=u(100),u(48);words=[]
    for name in ['ram_init','logger','ram_dump']:
        rva=reference['labels'][name];off=start+rva
        if u(off)&0xffff0000!=0xe92d0000:
            raise ValueError(f'Unexpected entry instruction: {name}')
        words.append(off);struct.pack_into('<I',b,off,0xe1a0f00e)  # MOV pc,lr
    alloc=start+0xe84
    if u(alloc)!=0x8920:raise ValueError('Unexpected diagnostic allocation size')
    words.append(alloc);struct.pack_into('<I',b,alloc,ORIGINAL_OBJECT_SIZE)
    words.append(24)
    struct.pack_into('<I',b,24,sum(struct.unpack('<'+'I'*(size//4),b[start:start+size]))&0xffffffff)
    allowed={p for off in words for p in range(off,off+4)}
    changed=[p for p,(x,y) in enumerate(zip(original,b)) if x!=y]
    assert len(b)==len(original) and set(changed)<=allowed
    report={'basis_sha256':SHA256,'output_sha256':hashlib.sha256(b).hexdigest(),'size':len(b),'modified_words_file_offsets':[hex(x) for x in words],'changed_byte_offsets':changed,'diagnostic_entries':'ram_init/logger/ram_dump return immediately','object_size':ORIGINAL_OBJECT_SIZE,'ram_diagnostic_buffer_allocated':False,'diagnostic_file_IO':False,'functional_code_and_tables':'Byte-identical to working 0.4.3 outside the listed diagnostic/allocation/checksum words','retained_inert_bytes':'Unreachable diagnostic bodies, wrappers and imports remain to preserve binary layout','hardware_status':'0.4.3 was user-tested; this no-diagnostic derivative needs a device comparison'}
    return bytes(b),report

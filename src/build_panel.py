#!/usr/bin/env python3
"""Build an experimental ER5 SLIP control panel from the exact SDK originals.

No compiler and no EXE: retain the stock native Internet editor and change its
new-profile protocol resource, identity, resource namespace and list query.
Never patch the installed Internet applet or the device database with this tool.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct

OLD_RESOURCE_BASE = 0x2DC74000
NEW_RESOURCE_BASE = 0x57445000
NEW_UID3 = 0x0F574453  # experimental, unregistered UID; not a production allocation
ICON_SHA256 = '02cf66a9257597ee89eac1d37fc5b21374277a8c6545433a221c91233981ef6d'

def u32(b, p):
    return struct.unpack_from('<I', b, p)[0]

def put32(b, p, v):
    struct.pack_into('<I', b, p, v)

def uid_crc(b):
    return (binascii.crc_hqx(b[:12:2], 0) |
            (binascii.crc_hqx(b[1:12:2], 0) << 16))

def code_sum(b):
    start, size = u32(b, 0x64), u32(b, 0x30)
    return sum(struct.unpack('<' + 'I' * (size // 4), b[start:start+size])) & 0xFFFFFFFF

def resources(b):
    index = struct.unpack_from('<H', b)[0]
    assert (len(b)-index) % 2 == 0
    offsets = struct.unpack_from('<'+'H'*((len(b)-index)//2), b, index)
    assert offsets[0] == 4 and offsets[-1] == index
    assert list(offsets) == sorted(offsets)
    return [b[a:z] for a, z in zip(offsets, offsets[1:])]

def pack_resources(original, items):
    offsets, body = [], bytearray(original[:4])
    for item in items:
        offsets.append(len(body))
        body.extend(item)
    offsets.append(len(body))
    assert len(body) < 65536
    struct.pack_into('<H', body, 0, len(body))
    body.extend(struct.pack('<'+'H'*len(offsets), *offsets))
    return bytes(body)

def rename_label(data, old, new):
    a, z = old.encode('ascii'), new.encode('ascii')
    needle = bytes([len(a)])+a
    assert data.count(needle) == 1, old
    return data.replace(needle, bytes([len(z)])+z)

def reloc_sites(b):
    pos = u32(b, 0x70)
    size, count = struct.unpack_from('<II', b, pos)
    end, pos = pos + 8 + size, pos + 8
    sites = []
    while pos < end:
        page, blocksize = struct.unpack_from('<II', b, pos)
        assert blocksize >= 8 and blocksize % 4 == 0
        for n in range(pos+8, pos+blocksize, 2):
            item = struct.unpack_from('<H', b, n)[0]
            if item:
                assert item >> 12 == 3
                sites.append(page + (item & 0xFFF))
        pos += blocksize
    assert pos == end and len(sites) == count
    return sites

def build_icon(aif):
    """Retain original Internet artwork/mask; adapt AIF UID and caption."""
    assert len(aif)==1600 and hashlib.sha256(aif).hexdigest()==ICON_SHA256
    assert aif[:12]==struct.pack('<III',0x10000037,0x1000006a,0x10000349)
    assert uid_crc(aif)==u32(aif,12)
    footer=u32(aif,16)
    assert aif[footer]==2  # One caption; AIF encoded count is twice the count.
    caption=u32(aif,footer+1)
    assert aif[caption:footer]==bytes([len('Internet')*4+2])+b'Internet'
    assert struct.unpack_from('<H',aif,footer+5)[0]==1  # English
    assert aif[footer+7]==2  # One icon/mask pair
    image_offset=u32(aif,footer+8)
    assert image_offset==20
    image_size=u32(aif,image_offset)
    mask=image_offset+image_size
    assert mask+u32(aif,mask)==caption
    assert struct.unpack_from('<II',aif,image_offset+8)==(48,48)
    assert struct.unpack_from('<II',aif,mask+8)==(48,48)
    text=b'WodemSLIP';new_caption=bytes([len(text)*4+2])+text
    b=bytearray(aif[:caption]+new_caption+aif[footer:])
    new_footer=caption+len(new_caption)
    put32(b,16,new_footer);put32(b,8,NEW_UID3);put32(b,12,uid_crc(b))
    assert b[20:caption]==aif[20:caption]  # Both artwork and transparency mask.
    assert b[new_footer:]==aif[footer:]
    assert uid_crc(b)==u32(b,12) and u32(b,8)==NEW_UID3
    assert u32(b,new_footer+1)==caption
    assert b[caption:new_footer]==new_caption
    report={'source':'Original EPOC Internet control-panel icon: computer, globe and handheld','input_sha256':ICON_SHA256,'output_sha256':hashlib.sha256(b).hexdigest(),'uid3':hex(NEW_UID3),'caption':'WodemSLIP','pixels':[48,48],'artwork_and_transparency_mask':'Byte-identical to original Internet.aif','size':len(b),'checks':['Exact SDK input hash','Matching applet UID3','UID CRC','Caption encoding and pointer','Footer offset and contents','Original icon/mask pair retained']}
    return bytes(b),report

def build(ctl, rsc):
    assert len(ctl) == 26812
    assert ctl[:12] == struct.pack('<III', 0x10000079, 0x10000297, 0x10000349)
    assert uid_crc(ctl) == u32(ctl, 12)
    assert code_sum(ctl) == u32(ctl, 24)
    assert u32(ctl, 24) == 0xCEC3DD33
    items = resources(rsc)
    assert len(items) == 49
    assert items[36] == b'ppp'
    assert items[35] == b'New Internet service'
    assert items[0] == struct.pack('<II', 4, OLD_RESOURCE_BASE+1)

    # New independent resource namespace prevents collisions with Internet.ctl.
    resource_changes = 0
    for i, item in enumerate(items):
        data = bytearray(item)
        for p in range(len(data)-3):
            value = u32(data, p)
            if OLD_RESOURCE_BASE < value <= OLD_RESOURCE_BASE+len(items):
                put32(data, p, NEW_RESOURCE_BASE + value-OLD_RESOURCE_BASE)
                resource_changes += 1
        items[i] = bytes(data)
    items[1] = rename_label(items[1], 'Internet service settings', 'Wodem SLIP connections')
    items[1] = rename_label(items[1], 'Current Internet service', 'Current SLIP connection')
    items[1] = rename_label(items[1], 'Set the Internet service for connecting Internet programs, e.g. Web',
                            'Create or edit SLIP connections for a serial link.')
    items[35] = b'Wodem SLIP'
    items[36] = b'slip'
    patched_rsc = pack_resources(rsc, items)

    image = bytearray(ctl)
    start, size, base = u32(image, 0x64), u32(image, 0x30), u32(image, 0x4C)
    end = start+size
    assert end == u32(image, 0x6C)  # no initialized data between code and imports
    assert u32(image, 0x34) == 0 and u32(image, 0x68) == 0
    changes = []
    for p in range(start, end, 4):
        value = u32(image, p)
        if OLD_RESOURCE_BASE < value <= OLD_RESOURCE_BASE+len(items):
            put32(image, p, NEW_RESOURCE_BASE + value-OLD_RESOURCE_BASE)
            changes.append(p)
    assert len(changes) > 10

    # Keep the original query bytes in place. Append a precise SLIP-only query;
    # retarget its existing, loader-relocated pointer. Existing code/IAT/export
    # locations are unchanged; only following file sections shift.
    query = b"SELECT Name,Id FROM DialOutService WHERE hidden=0 AND IfName='slip'\0"
    query += b'\0' * (-len(query) % 4)
    old_query = ctl.index(b'SELECT Name,Id FROM DialOutService WHERE hidden=0\0')
    old_ptr = base + old_query-start
    refs = [p for p in range(start, end, 4) if u32(image, p) == old_ptr]
    assert refs == [0x176C]
    assert refs[0]-start in reloc_sites(ctl)
    put32(image, refs[0], base+size)
    image[end:end] = query
    put32(image, 0x30, size+len(query))
    for field in (0x6C, 0x70, 0x74):  # imports, code relocations, data relocations
        value = u32(image, field)
        if value:
            assert value >= end
            put32(image, field, value+len(query))
    put32(image, 8, NEW_UID3)
    put32(image, 12, uid_crc(image))
    put32(image, 24, code_sum(image))

    # Structural checks against the input, including relocation after rebasing.
    assert reloc_sites(image) == reloc_sites(ctl)
    assert u32(image, u32(image, 0x58)) == u32(ctl, u32(ctl, 0x58))
    assert image[u32(image, 0x6C):u32(image, 0x70)] == ctl[u32(ctl, 0x6C):u32(ctl, 0x70)]
    relocated_pointer = u32(image, refs[0]) + 0x08000000
    relocated_base = base + 0x08000000
    query_offset = relocated_pointer-relocated_base+start
    assert image[query_offset:query_offset+len(query)] == query
    assert resources(patched_rsc)[36] == b'slip'
    assert resources(patched_rsc)[0] == struct.pack('<II', 4, NEW_RESOURCE_BASE+1)
    assert uid_crc(image) == u32(image, 12)
    assert code_sum(image) == u32(image, 24)
    report = {
        'status': 'experimental; device runtime and network not tested',
        'uid3': hex(NEW_UID3), 'resource_base': hex(NEW_RESOURCE_BASE),
        'protocol_resource': {'id': 37, 'value': 'slip'},
        'stock_ifname_field_offset': '0x1a0',
        'resource_literal_file_offsets': [hex(p) for p in changes],
        'resource_internal_ids_updated': resource_changes,
        'sql': query.rstrip(b'\0').decode('ascii'),
        'query_pointer_file_offset': hex(refs[0]),
        'original_ctl_sha256': hashlib.sha256(ctl).hexdigest(),
        'original_rsc_sha256': hashlib.sha256(rsc).hexdigest(),
        'output_ctl_sha256': hashlib.sha256(image).hexdigest(),
        'output_rsc_sha256': hashlib.sha256(patched_rsc).hexdigest(),
        'checks': ['original UID CRC', 'original code checksum', 'output UID CRC',
                   'output code checksum', 'resource index and SLIP resource',
                   'unique control UID and resource namespace',
                   'unchanged export and import section contents',
                   'unchanged relocation sites', 'rebased query pointer simulation'],
    }
    return image, patched_rsc, report

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('internet_ctl', type=Path)
    ap.add_argument('internet_r01', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    ctl, rsc, report = build(args.internet_ctl.read_bytes(), args.internet_r01.read_bytes())
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'WodemSLIP.ctl').write_bytes(ctl)
    (args.output/'WodemSLIP.rsc').write_bytes(rsc)
    (args.output/'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))

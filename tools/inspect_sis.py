"""Inspect the uncompressed, non-Unicode SIS format used by EPOC ER5.

This reader is deliberately limited to the single-language normal/text file
records generated for this project. It is independent of the SIS writer.
"""
import binascii
import json
import struct
import sys
from pathlib import Path

def inspect(path):
    data=Path(path).read_bytes()
    if len(data)<68:raise ValueError('Truncated SIS header')
    uid,type_uid,installer_uid,uid_crc=struct.unpack_from('<4I',data)
    expected=(binascii.crc_hqx(data[:12:2],0) | binascii.crc_hqx(data[1:12:2],0)<<16)
    if uid_crc!=expected:raise ValueError('Invalid UID checksum')
    crc,language_count,file_count,dependency_count=struct.unpack_from('<4H',data,16)
    if crc!=binascii.crc_hqx(data[:16]+data[18:],0):raise ValueError('Invalid SIS checksum')
    if type_uid!=0x1000006d or installer_uid!=0x10000419:raise ValueError('Not an ER5 non-Unicode SIS')
    if language_count!=1 or dependency_count:raise ValueError('Unsupported table layout')
    major,minor=struct.unpack_from('<2H',data,40);variant=struct.unpack_from('<I',data,44)[0]
    language_offset,file_offset,dependency_offset,_,name_offset=struct.unpack_from('<5I',data,48)
    if struct.unpack_from('<H',data,language_offset)[0]!=1:raise ValueError('Expected English package')
    def blob(pos,length):
        if pos<0 or length<0 or pos+length>len(data):raise ValueError('SIS pointer outside file')
        return data[pos:pos+length]
    records=[]
    for i in range(file_count):
        fields=struct.unpack_from('<9I',data,file_offset+i*36)
        langdep,kind,options,sl,sp,dl,dp,pl,pp=fields
        if langdep or kind not in [0,1]:raise ValueError('Unexpected file record type')
        records.append({'kind':kind,'options':options,'source':blob(sp,sl).decode('latin1'),'destination':blob(dp,dl).decode('latin1'),'payload':blob(pp,pl)})
    # ER5 stores the file table in reverse installation order.
    return {'uid':uid,'version':[major,minor,variant],'files':list(reversed(records))}

def selected_files(package,install_defaults):
    selected=[];skip=False
    for rec in package['files']:
        if skip:skip=False;continue
        if rec['kind']==1:
            if rec['options']==1 and not install_defaults:skip=True
        else:selected.append(rec)
    return selected

if __name__=='__main__':
    try:
        package=inspect(sys.argv[1])
        print(json.dumps({'uid':hex(package['uid']),'version':package['version'],'installation_order':[{'kind':f['kind'],'options':f['options'],'destination':f['destination'],'bytes':len(f['payload'])} for f in package['files']]},indent=2))
    except (IndexError,OSError,ValueError,struct.error) as e:
        raise SystemExit(f'Error: {e}')

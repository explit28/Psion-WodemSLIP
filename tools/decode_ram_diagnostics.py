"""Decode bounded WDR1 diagnostics without printing application payload bytes."""
import collections,json,struct,sys
from pathlib import Path

def packet(prefix):
    if len(prefix)<20 or prefix[0]>>4!=4:return {'type':'unrecognized','captured_bytes':len(prefix)}
    ihl=(prefix[0]&15)*4
    result={'type':'IPv4','source':'.'.join(map(str,prefix[12:16])),'destination':'.'.join(map(str,prefix[16:20])),'protocol':prefix[9],'total_length':int.from_bytes(prefix[2:4],'big'),'fragment_field':int.from_bytes(prefix[6:8],'big')}
    if ihl<20:return result|{'invalid_header_length':ihl}
    if prefix[9]==6 and len(prefix)>=ihl+20 and not(int.from_bytes(prefix[6:8],'big')&0x1fff):
        tcp=prefix[ihl:];bits=tcp[13]
        result.update(type='TCP',source_port=int.from_bytes(tcp[:2],'big'),destination_port=int.from_bytes(tcp[2:4],'big'),sequence=int.from_bytes(tcp[4:8],'big'),acknowledgment=int.from_bytes(tcp[8:12],'big'),flags=[name for bit,name in [(1,'FIN'),(2,'SYN'),(4,'RST'),(8,'PSH'),(16,'ACK'),(32,'URG'),(64,'ECE'),(128,'CWR')] if bits&bit])
    elif prefix[9]==1 and len(prefix)>ihl:result.update(type='ICMP',icmp_type=prefix[ihl])
    return result

def decode(data):
    if len(data)<32:raise ValueError('Diagnostic file is shorter than its header')
    magic,version,size,capacity,total,index,dumped,reserved=struct.unpack_from('<8I',data)
    if (magic,version,size,capacity)!=(0x31524457,1,128,256):raise ValueError('Unsupported diagnostic format')
    count=min(total,capacity)
    if len(data)!=32+count*size:raise ValueError('Diagnostic file length does not match its header')
    records=[]
    for pos in range(32,len(data),size):
        row=data[pos:pos+size];words=struct.unpack_from('<16I',row)
        if words[0]!=magic:raise ValueError('Invalid record magic')
        stage,seq,flags=words[1:4]
        entry={'sequence':seq,'stage':stage,'driver_flags':hex(flags),'queued_mbufs':words[11],'rx_partial_bytes':words[12]}
        if stage in [160,170]:entry['completion_status']=struct.unpack_from('<i',row,20)[0]
        if stage in [120,180]:entry.update(direction='TX' if stage==120 else 'RX',packet=packet(row[64:64+min(words[14],64)]))
        records.append(entry)
    records.sort(key=lambda row:row['sequence'])
    expected=list(range(total-count,total))
    if [row['sequence'] for row in records]!=expected:raise ValueError('Record sequence is inconsistent')
    return {'format':'WDR1','events_total':total,'events_retained':count,'older_events_overwritten':max(0,total-capacity),'next_ring_slot':index,'stage_counts':dict(collections.Counter(row['stage'] for row in records)),'records':records}

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python decode_ram_diagnostics.py WODEMDIAG.BIN')
    try:print(json.dumps(decode(Path(sys.argv[1]).read_bytes()),indent=2))
    except (OSError,ValueError) as error:raise SystemExit(f'Cannot decode diagnostics: {error}')

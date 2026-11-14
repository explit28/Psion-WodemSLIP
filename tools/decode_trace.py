"""Decode SLIPDBG.BIN; no external dependencies required."""
import struct
import sys
from pathlib import Path

STAGES = {
    10: 'Start entry',
    20: 'Serial initialization entry',
    30: 'PortName read returned; before RComm::Open',
    40: 'RComm::Open returned',
    50: 'Read current serial configuration returned',
    60: 'Set serial configuration returned',
    70: 'Serial initialization returned to Start',
    80: 'Read scheduling returned; before protocol callback',
    90: 'Protocol callback returned; before LinkLayerUp',
    100: 'LinkLayerUp returned; before progress callback',
    110: 'Progress callback returned; Start about to return',
    120: 'Send entry',
    130: 'Send return value about to be finalized',
    140: 'Transmit encoder entry',
    150: 'Encoded bytes ready; before serial write',
    160: 'Serial write completion callback',
    170: 'Serial read completion callback',
    180: 'Received packet about to enter IP stack',
    190: 'Received packet callback returned',
}

def decode(data):
    rows=[]
    for pos in range(0,len(data)-47,48):
        row=struct.unpack_from('<12I',data,pos)
        if row[0]!=0x314c5053:raise ValueError(f'Invalid record magic at byte {pos}.')
        if row[1] not in STAGES:raise ValueError(f'Unknown trace stage {row[1]} at byte {pos}.')
        rows.append(row)
    return rows,len(data)%48

def main():
    try:
        rows,trailing=decode(Path(sys.argv[1]).read_bytes())
    except (OSError,ValueError,IndexError) as e:
        print(f'Error: {e}\nUsage: python3 decode_trace.py SLIPDBG.BIN',file=sys.stderr)
        return 1
    if not rows:print('No complete trace records found.',file=sys.stderr);return 1
    for i,r in enumerate(rows,1):
        signed=r[2] if r[2]<0x80000000 else r[2]-0x100000000
        print(f'{i:03d} stage={r[1]:03d}: {STAGES[r[1]]}')
        print(f'    r0=0x{r[2]:08x} ({signed}) r1=0x{r[3]:08x} r2=0x{r[4]:08x} r3=0x{r[5]:08x}')
        print(f'    r5=0x{r[6]:08x} r6=0x{r[7]:08x} lr=0x{r[8]:08x} notify=0x{r[9]:08x} protocol=0x{r[10]:08x} state=0x{r[11]:08x}')
    if trailing:print(f'Warning: {trailing} trailing bytes from an incomplete record.',file=sys.stderr)
    print('Last recorded checkpoint:',STAGES[rows[-1][1]])
    print('A checkpoint identifies completed progress; it does not identify the exact faulting instruction.')
    return 0

if __name__=='__main__':sys.exit(main())

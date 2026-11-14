"""Execute complete ARM Send and async encoder against SLIP frame vectors.

Native descriptors, packet queues and serial writes are modeled. This is
not real Psion kernel/network execution. The original ARM encoder executes.
"""
from pathlib import Path
import json,struct,random
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_INVALID
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parent.parent
U=lambda b,p=0:struct.unpack_from('<I',b,p)[0]
SELF=0x20001000;CHAIN=0x2000d000;STACK=0x70008000;END=0x40000000;API=0x30000000

class Driver:
    def __init__(self,folder,base=0x18000000):
        self.binary=(ROOT/folder/'SLIP.NIF').read_bytes();self.report=json.loads((ROOT/folder/'validation.json').read_text());self.base=base
        b=self.binary;code=bytearray(b[124:124+U(b,48)])
        # Apply the original loader relocation entries.
        p=U(b,112);end=p+8+U(b,p);p+=8
        while p<end:
            page,sz=struct.unpack_from('<II',b,p)
            for off in range(p+8,p+sz,2):
                r=struct.unpack_from('<H',b,off)[0]
                if r:
                    s=page+(r&4095);struct.pack_into('<I',code,s,(U(code,s)+base-0x10000000)&0xffffffff)
            p+=sz
        slots=[];p=U(b,108)+4
        for _ in range(U(b,84)):
            no,n=struct.unpack_from('<II',b,p);ip=U(b,108);name=b[ip+no:b.index(b'\0',ip+no)].decode().split('[')[0]
            for ordinal in struct.unpack_from('<'+'I'*n,b,p+8):slots.append((name,ordinal))
            p+=8+n*4
        self.native={}
        for i,key in enumerate(slots):
            addr=API+i*256;struct.pack_into('<I',code,U(b,96)+i*4,addr);self.native[addr]=key
        self.cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM)
        for addr,size in [(base,0x10000),(0x20000000,0x800000),(0x70000000,0x10000),(END,0x1000),(API,0x10000)]:self.cpu.mem_map(addr,size)
        self.cpu.mem_write(base,bytes(code));self.next=0x20010000;self.freed=set();self.writes=[];self.pending=False;self.faults=[];self.events=[];self.ready=0;self.received=[];self.read_requests=0
        self.put(SELF+0x74,0x11);self.put(SELF+0x94,0x30000000);self.put(SELF+0x98,1024);self.put(SELF+0x4a0,8)
        self.put(SELF+120,0x2000c000);self.put(0x2000c000,0x2000c100);self.put(0x2000c100+40,API+0xf000)
        self.put(0x2000c100+68,API+0xf100)
        self.put(SELF+0x4a8,0x30000000);self.put(SELF+0x4ac,1024)
        self.cpu.hook_add(UC_HOOK_CODE,self.native_call)
        self.cpu.hook_add(UC_HOOK_MEM_INVALID,self.fault)
    def get(self,p):return U(self.cpu.mem_read(p,4))
    def put(self,p,v):self.cpu.mem_write(p,struct.pack('<I',v&0xffffffff))
    def alloc(self,n):p=self.next;self.next+=(n+15)&~15;assert self.next<0x207f0000;return p
    def node(self,data):
        p=self.alloc(28);buf=self.alloc(max(len(data),1));self.cpu.mem_write(buf,data or b'\0')
        for off,val in [(0,0),(4,0),(8,0),(12,len(data)),(16,1),(20,max(len(data),1)),(24,buf)]:self.put(p+off,val)
        return p
    def packet(self,data,fragment):
        header=self.node(b'metadata');last=header
        for i in range(0,len(data),fragment):
            p=self.node(data[i:i+fragment]);self.put(last,p);last=p
        self.put(CHAIN,header)
    def fault(self,cpu,access,addr,size,value,user):self.faults.append({'pc':hex(cpu.reg_read(UC_ARM_REG_PC)-self.base),'address':hex(addr)});return False
    def native_call(self,cpu,addr,size,user):
        if addr==API+0xf000:
            assert cpu.reg_read(UC_ARM_REG_R0)==0x2000c000 and cpu.reg_read(UC_ARM_REG_R1)==SELF
            self.ready+=1;cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
        if addr==API+0xf100:
            assert cpu.reg_read(UC_ARM_REG_R0)==0x2000c000 and cpu.reg_read(UC_ARM_REG_R2)==SELF
            packet=cpu.reg_read(UC_ARM_REG_R1);header=self.get(packet);assert header
            p=self.get(header);data=bytearray();seen={header}
            while p:
                assert p not in seen and p not in self.freed;seen.add(p)
                data.extend(cpu.mem_read(self.get(p+24)+self.get(p+8),self.get(p+12)));p=self.get(p)
            self.received.append(bytes(data));self.freed.update(seen);self.put(packet,0)
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
        if not getattr(self,'execute_logger',False) and self.report.get('logger_rva') is not None and addr==self.base+self.report['logger_rva']:
            # File logging is tested separately; bypass actual FS operations.
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
        if addr not in self.native:return
        lib,ordinal=self.native[addr];r0=cpu.reg_read(UC_ARM_REG_R0);r1=cpu.reg_read(UC_ARM_REG_R1);ret=0
        self.events.append((lib,ordinal))
        if (lib,ordinal)==('EUSER',804):ret=r0+8
        elif (lib,ordinal)==('EUSER',965):
            assert 0<=r1<=self.get(r0+4);self.put(r0,(self.get(r0)&0xf0000000)|r1)
        elif (lib,ordinal)==('EUSER',970):self.put(r0,self.get(r0)&0xf0000000)
        elif (lib,ordinal)==('EUSER',1121):self.put(r1,0)
        elif (lib,ordinal)==('EUSER',1139):pass
        elif (lib,ordinal)==('ESOCK',111):
            p=self.get(r0);assert p,'MBuf13: empty chain'
            seen=set()
            while p:
                assert p not in seen and p not in self.freed;seen.add(p);ret+=1;p=self.get(p)
        elif (lib,ordinal)==('ESOCK',15):
            p=self.get(r1);assert p
            last=self.get(r0+4)
            if last:self.put(last+4,p)
            else:self.put(r0,p)
            self.put(r0+4,p);self.put(r1,0)
        elif (lib,ordinal)==('ESOCK',151):
            p=self.get(r0);ret=p
            if p:assert p not in self.freed;self.put(r0,self.get(p));self.put(p,0)
        elif (lib,ordinal)==('ESOCK',157):
            p=self.get(r0)
            if p:
                new=self.get(p+4);self.put(r0,new)
                if not new:self.put(r0+4,0)
                self.put(p+4,0);self.put(r1,p);ret=1
        elif (lib,ordinal)==('NIFMAN',87):self.put(r0,0);self.put(r0+4,0)
        elif (lib,ordinal)==('ESOCK',8):ret=self.node(b'\0'*128)
        elif (lib,ordinal)==('ESOCK',12):
            assert r1 and r1 not in self.freed
            last=self.get(r0+4)
            if last:self.put(last,r1)
            else:self.put(r0,r1)
            self.put(r0+4,r1)
        elif (lib,ordinal)==('NIFMAN',76):
            p=self.get(r0);assert p and p not in self.freed
            self.put(r0,self.get(p));self.put(p,0);self.put(r0+4,p);ret=p
        elif (lib,ordinal)==('NIFMAN',42):
            p=self.get(r0+4)
            if p:assert p not in self.freed;self.freed.add(p);self.put(r0+4,0)
        elif (lib,ordinal)==('ESOCK',17):self.put(r0,self.get(r1));self.put(r1,0)
        elif (lib,ordinal)==('NIFMAN',38):
            expected=cpu.reg_read(UC_ARM_REG_R2);hdrsize=cpu.reg_read(UC_ARM_REG_R3)
            head=self.get(r1);p=head;length=0
            while p:assert p not in self.freed;length+=self.get(p+12);p=self.get(p)
            assert length==expected,(length,expected)
            header=self.node(b'\0'*hdrsize);self.put(r0,head);self.put(r0+4,header);self.put(r1,0);self.put(r1+4,0);ret=header
        elif (lib,ordinal)==('NIFMAN',54):
            header=self.get(r0+4);assert header
            self.put(header,self.get(r0));self.put(r0,header);self.put(r0+4,0)
        elif (lib,ordinal)==('NIFMAN',23):
            assert r0==SELF+16 and r1==SELF+0x4a8;self.read_requests+=1
        elif (lib,ordinal)==('ESOCK',66):
            if r0:assert r0 not in self.freed;self.freed.add(r0)
        elif (lib,ordinal)==('NIFMAN',26):
            assert not self.pending,'Overlapping serial writes'
            n=self.get(r1)&0xfffffff;assert 0<n<=1024
            self.writes.append(bytes(cpu.mem_read(r1+8,n)));self.pending=True
        else:raise AssertionError(f'Unexpected API: {lib}/{ordinal}')
        for reg in [UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12]:cpu.reg_write(reg,0xdead0000+reg)
        cpu.reg_write(UC_ARM_REG_R0,ret);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def call(self,entry,r1=0):
        cpu=self.cpu;cpu.reg_write(UC_ARM_REG_SP,STACK);cpu.reg_write(UC_ARM_REG_LR,END);cpu.reg_write(UC_ARM_REG_R0,SELF);cpu.reg_write(UC_ARM_REG_R1,r1)
        cpu.emu_start(self.base+entry,END,count=1000000)
        assert cpu.reg_read(UC_ARM_REG_PC)==END,'Instruction limit reached'
        assert cpu.reg_read(UC_ARM_REG_SP)==STACK,'Unbalanced call stack'
        return cpu.reg_read(UC_ARM_REG_R0)
    def send(self,data,fragment):self.packet(data,fragment);return self.call(0x1cc,CHAIN)
    def receive(self,chunk):
        assert 0<len(chunk)<=1024
        self.put(SELF+0x4a8,0x30000000|len(chunk));self.cpu.mem_write(SELF+0x4b0,chunk)
        before=self.read_requests;flags=self.get(SELF+0x74)
        self.call(0x790,0)
        return before,flags
    def drain(self):
        for _ in range(100):
            if not self.pending:return
            self.pending=False;self.call(0x768,0)
        raise AssertionError('Encoder does not become idle')

def frames(stream):
    out=[];current=bytearray();escape=False
    for b in stream:
        if b==0xc0:
            if current:out.append(bytes(current));current.clear()
            escape=False
        elif escape:
            assert b in [0xdc,0xdd];current.append(0xc0 if b==0xdc else 0xdb);escape=False
        elif b==0xdb:escape=True
        else:current.append(b)
    assert not current and not escape,'Unterminated output frame'
    return out

# v2's first-packet branch reaches a null byte pointer in strict ARM mapping.
baseline=Driver('build/baseline-v2')
try:baseline.send(b'example IP payload',128)
except Exception:
    assert baseline.faults and baseline.faults[-1]=={'pc':'0x6ac','address':'0x0'},baseline.faults
else:raise AssertionError('Expected v2 null byte-pointer fault was not reproduced')

old_rx=Driver('build/baseline-v2');old_rx.receive(b'\xc0')
assert old_rx.get(SELF+0x74)==0 and old_rx.read_requests==0

cases=0;rx_cases=0;rng=random.Random(13)
lengths=[0,1,2,31,44,128,255,576,1022,1023,1024,1025,1500,2048]
for base in [0x10000000,0x18000000]:
    for n in lengths:
        vectors=[bytes(i%256 for i in range(n)),b'\xc0'*n,b'\xdb'*n,bytes(rng.randrange(256) for _ in range(n))]
        for ix,data in enumerate(vectors):
            d=Driver('build/driver',base);accepted=d.send(data,[1,17,128,600][ix]);d.drain()
            assert frames(b''.join(d.writes))==([data] if data else []),(base,n,ix)
            before=len(d.writes);d.call(0x588);assert not d.pending and len(d.writes)==before
            assert d.get(SELF+0x80)==d.get(SELF+0x88)==d.get(SELF+0x8c)==0
            assert d.get(SELF+0x74)==0x11 and d.get(SELF+0x49c)==0
            assert accepted in [0,1]
            if not accepted:assert d.ready>=1,'Blocked protocol was not resumed after transmission'
            # Feed the actual encoded stream back through the ARM parser.
            wire=b''.join(d.writes)
            for pos in range(0,len(wire),17):
                before,flags=d.receive(wire[pos:pos+17]);assert d.read_requests==before+1
                assert (d.get(SELF+0x74)&~8)==(flags&~8)
            assert d.received==([data] if data else []),(base,n,ix,d.received[:2],data[:50])
            cases+=1
    # Queue additional packets while a serial write is outstanding.
    d=Driver('build/driver',base);packets=[bytes([i,0xc0,0xdb])*j for i,j in [(1,1),(2,10),(3,200),(4,500),(5,3)]]
    for data in packets:d.send(data,17)
    d.drain();assert frames(b''.join(d.writes))==packets
    wire=b''.join(d.writes)
    for pos in range(0,len(wire),127):d.receive(wire[pos:pos+127])
    assert d.received==packets
    assert not d.faults and d.get(SELF+0x74)==0x11;cases+=1
    # A flow-controlled client must be able to send again after each drain.
    d=Driver('build/driver',base);packets=[]
    for i in range(50):
        data=bytes([i,0xc0,0xdb])*rng.randrange(1,100);packets.append(data)
        prior=d.ready;accepted=d.send(data,128);d.drain();assert d.get(SELF+0x49c)==0
        if not accepted:assert d.ready>prior
    assert frames(b''.join(d.writes))==packets
    wire=b''.join(d.writes)
    for pos in range(0,len(wire),127):d.receive(wire[pos:pos+127])
    assert d.received==packets;cases+=1

    # Receive boundaries include mbuf edges and an ESC split across reads.
    for n in [1,2,44,127,128,129,255,256,576,1024,1500]:
        for idx in range(4):
            data=([bytes(i%256 for i in range(n)),b'\xc0'*n,b'\xdb'*n,bytes(rng.randrange(256) for _ in range(n))])[idx]
            encoded=bytearray(b'\xc0')
            for byte in data:encoded.extend(b'\xdb\xdc' if byte==0xc0 else b'\xdb\xdd' if byte==0xdb else bytes([byte]))
            encoded.append(0xc0);d=Driver('build/driver',base);chunk_size=[1,2,127,1024][idx]
            for pos in range(0,len(encoded),chunk_size):
                before,flags=d.receive(bytes(encoded[pos:pos+chunk_size]));assert d.read_requests==before+1
                assert (d.get(SELF+0x74)&~8)==(flags&~8)
            assert d.received==[data] and d.get(SELF+0x8b0)==d.get(SELF+0x8b4)==0
            rx_cases+=1
    # Receive while output is pending: preserve output/flow state.
    d=Driver('build/driver',base);data=b'\xc0\xdb'*1000;d.send(data,128)
    initial=d.get(SELF+0x74)
    for chunk in [b'\xc0abc\xdb',b'\xdcdef\xc0']:
        before,flags=d.receive(chunk);assert d.read_requests==before+1
        assert (d.get(SELF+0x74)&~8)==(initial&~8)
    assert d.received==[b'abc\xc0def'];d.drain();assert frames(b''.join(d.writes))==[data];rx_cases+=1

out={'baseline_v2_fault_reproduced':baseline.faults[-1],'baseline_v2_receive_state_loss_reproduced':True,'complete_tx_loopback_cases_passed':cases,'additional_receive_cases_passed':rx_cases,'coverage':'Both load bases; Send/encoder and async writes; sizes 0..2048; C0/DB escaping; fragmented mbufs; multiple queued packets; flow wakeup; byte-for-byte receive loopback; split ESC; exact full receive buffers; read rearming; simultaneous receive with pending writes; idle and ownership checks; stack restoration','limits':'Native descriptor, mbuf, queue, protocol callbacks and serial APIs modeled from SDK contracts. Logger is bypassed here; release no-op entries and forbidden file operations are tested in test_release_no_diagnostics.py. Does not emulate full Psion kernel, real serial hardware/driver or TCP/IP implementation.'}
(ROOT/'build/driver/encoder-checks.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))

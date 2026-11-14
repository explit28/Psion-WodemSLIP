"""Execute ARM diagnostics, recovery and synchronous callbacks with mocked OS APIs."""
from pathlib import Path
import json,struct
import importlib.util
from keystone import Ks,KS_ARCH_ARM,KS_MODE_ARM
from unicorn.arm_const import *

root=Path(__file__).resolve().parent.parent
p=root/'tests/test_data_path.py'
ns={'__file__':str(p)}
exec(p.read_text().split("# v2's first-packet")[0],ns)
Driver=ns['Driver'];SELF=ns['SELF'];CHAIN=ns['CHAIN'];API=ns['API'];END=ns['END'];STACK=ns['STACK'];frames=ns['frames']
U=ns['U'];ks=Ks(KS_ARCH_ARM,KS_MODE_ARM)
spec=importlib.util.spec_from_file_location('decoder',root/'tools/decode_ram_diagnostics.py')
decoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(decoder)

class Diagnostic(Driver):
    def __init__(self,*args):
        self.execute_logger=True
        super().__init__(*args)
        self.fs_events=[];self.dumps=[];self.fail=None;self.todo=[];self.reply=None;self.injected=0
        if self.report.get('trace_enabled'):self.call(self.report['labels']['ram_init'])
    def native_call(self,cpu,addr,size,user):
        key=self.native.get(addr)
        if addr==self.base+0x1104:
            assert cpu.reg_read(UC_ARM_REG_R0)==SELF and cpu.reg_read(UC_ARM_REG_R1)==3
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
        if key==('NIFMAN',15):
            assert cpu.reg_read(UC_ARM_REG_R0)==SELF+16
            self.return_api(0);return
        if key and key[0]=='EFSRV':
            _,ordinal=key;r0=cpu.reg_read(UC_ARM_REG_R0);r1=cpu.reg_read(UC_ARM_REG_R1)
            self.fs_events.append(ordinal);ret=-46 if self.fail==ordinal else 0
            if ordinal==133:
                desc=cpu.reg_read(UC_ARM_REG_R2);n=self.get(desc)&0xfffffff
                assert bytes(cpu.mem_read(self.get(desc+4),n))==b'C:\\WODEMDIAG.BIN'
            if ordinal==170 and not ret:
                n=self.get(r1)&0xfffffff;assert 32<=n<=32800
                self.dumps.append(bytes(cpu.mem_read(self.get(r1+4),n)))
            self.return_api(ret);return
        if key==('EUSER',164):self.fs_events.append('fs_close');self.return_api(0);return
        if key==('ESOCK',67):
            r0=cpu.reg_read(UC_ARM_REG_R0);node=self.get(r0)
            while node:assert node not in self.freed;self.freed.add(node);node=self.get(node)
            self.put(r0,0);self.put(r0+4,0);self.return_api(0);return
        super().native_call(cpu,addr,size,user)
        if addr==API+0xf000 and self.todo:self.inject(self.todo.pop(0))
        elif addr==API+0xf100 and self.reply is not None:
            data=self.reply;self.reply=None;self.inject(data)
    def return_api(self,value):
        cpu=self.cpu
        for reg in [UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12]:cpu.reg_write(reg,0xdead0000+reg)
        cpu.reg_write(UC_ARM_REG_R0,value&0xffffffff);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))
    def inject(self,data):
        self.packet(data,17);chain=self.alloc(4);self.put(chain,self.get(CHAIN));self.put(CHAIN,0);stub=self.base+0x8000
        code,_=ks.asm(f'push {{r4-r11,lr}}; ldr r0,[pc,#8]; ldr r1,[pc,#8]; bl #{self.base+0x1cc}; pop {{r4-r11,pc}}; .word {SELF}; .word {chain}',stub)
        self.cpu.mem_write(stub,bytes(code));self.cpu.reg_write(UC_ARM_REG_PC,stub);self.injected+=1
    def records(self):
        n=self.get(SELF+0x910);data=bytes(self.cpu.mem_read(SELF+0x920,min(n,256)*128))
        records=[data[i:i+128] for i in range(0,len(data),128)]
        return sorted(records,key=lambda rec:U(rec,8))
    def emit(self,stage):
        saved=SELF+0x8c4;self.cpu.mem_write(saved,b'\0'*56)
        cpu=self.cpu;cpu.reg_write(UC_ARM_REG_SP,STACK);cpu.reg_write(UC_ARM_REG_LR,END)
        cpu.reg_write(UC_ARM_REG_R0,stage);cpu.reg_write(UC_ARM_REG_R1,saved);cpu.reg_write(UC_ARM_REG_R2,SELF)
        cpu.emu_start(self.base+self.report['logger_rva'],END,count=100000)
        assert cpu.reg_read(UC_ARM_REG_PC)==END and cpu.reg_read(UC_ARM_REG_SP)==STACK

recovery=0;ring_cases=0;data_cases=0
for base in [0x10000000,0x18000000]:
    for status in [-30,-31,-32]:
        for busy in [False,True]:
            for partial in [b'',b'\xc0abc\xdb',b'\xc0'+b'X'*300+b'\xdb']:
                d=Diagnostic('build/driver',base)
                if busy:d.send(b'outgoing'*200,128)
                if partial:d.receive(partial)
                before=d.read_requests;flags=d.get(SELF+0x74);d.call(0x790,status&0xffffffff)
                assert d.get(SELF+0x74)==flags&~8 and d.read_requests==before+1
                assert d.get(SELF+0x8b0)==d.get(SELF+0x8b4)==d.get(SELF+0x8bc)==0
                d.receive(b'\xc0recovered\xc0');d.drain()
                assert d.received==[b'recovered'] and not d.pending and d.get(SELF+0x74)==0x11
                if busy:assert frames(b''.join(d.writes))==[b'outgoing'*200]
                assert not d.fs_events;recovery+=1
    # Real ARM wrappers, not bypassed: escaped/fragmented payload + immediate reply.
    for n in [1,44,576,1024,1500,2048]:
        d=Diagnostic('build/driver',base);payload=(b'\xc0\xdbXYZ'*500)[:n]
        expected=[payload]
        d.send(payload,17)
        for _ in range(100):
            if not d.pending:break
            d.pending=False;d.call(0x768)
        else:raise AssertionError('Unbounded transmission')
        assert frames(b''.join(d.writes))==expected
        wire=bytearray(b'\xc0')
        for byte in payload:wire.extend(b'\xdb\xdc' if byte==0xc0 else b'\xdb\xdd' if byte==0xdb else bytes([byte]))
        wire.append(0xc0);d.reply=b'ACK';expected.append(b'ACK')
        for i in range(0,len(wire),127):d.receive(bytes(wire[i:i+127]))
        d.drain();assert d.received==[payload] and frames(b''.join(d.writes))==expected
        assert not d.fs_events
        # Packet prefix captured before Send transfers ownership / before Process frees it.
        captured=d.records()
        assert any(U(r,4)==120 and r[64:64+min(n,64)]==payload[:64] for r in captured)
        assert any(U(r,4)==180 and r[64:64+min(n,64)]==payload[:64] for r in captured)
        data_cases+=1
    for n in [1,255,256,257,600]:
        d=Diagnostic('build/driver',base)
        for _ in range(n):d.emit(170)
        assert len(d.records())==min(n,256)
        assert [U(r,8) for r in d.records()]==list(range(max(0,n-256),n))
        assert not d.fs_events;d.emit(200)
        assert d.fs_events==[17,133,170,46,14,'fs_close'] and len(d.dumps)==1
        dump=d.dumps[0];assert len(dump)==32+min(n+1,256)*128
        assert struct.unpack_from('<4I',dump)==(0x31524457,1,128,256)
        decoded=decoder.decode(dump);assert decoded['events_total']==n+1 and decoded['events_retained']==min(n+1,256)
        d.call(d.report['labels']['ram_dump']);assert len(d.dumps)==1
        # A fresh Start clears the previous session without touching disk.
        d.emit(10);assert len(d.records())==1 and U(d.records()[0],4)==10
        ring_cases+=1
    # File failures must not corrupt the stack or the operational flags.
    for error_api in [17,133,170,46]:
        d=Diagnostic('build/driver',base);d.emit(170);d.fail=error_api;d.emit(200)
        assert d.get(SELF+0x74)==0x11 and d.get(SELF+0x918)==0
        d.fail=None;d.call(d.report['labels']['ram_dump']);assert d.get(SELF+0x918)==2
    # Exercise actual Stop-return wrapper and destructor fallback, not just logger entry.
    d=Diagnostic('build/driver',base);d.emit(170)
    d.cpu.mem_write(STACK,struct.pack('<5I',0x1111,0x2222,0x3333,0x4444,END))
    d.cpu.reg_write(UC_ARM_REG_SP,STACK);d.cpu.reg_write(UC_ARM_REG_R4,SELF)
    d.cpu.emu_start(base+0x580,END,count=100000)
    assert d.cpu.reg_read(UC_ARM_REG_PC)==END and d.cpu.reg_read(UC_ARM_REG_SP)==STACK+20
    assert len(d.dumps)==1 and decoder.decode(d.dumps[0])['records'][-1]['stage']==200
    d=Diagnostic('build/driver',base);d.emit(170);d.call(0x12c,3)
    assert len(d.dumps)==1 and decoder.decode(d.dumps[0])['events_total']==1

ip=bytearray(40);ip[0]=0x45;ip[2:4]=(40).to_bytes(2,'big');ip[9]=6;ip[12:16]=bytes([192,168,240,2]);ip[16:20]=bytes([192,168,178,1]);ip[20:22]=(1234).to_bytes(2,'big');ip[22:24]=(80).to_bytes(2,'big');ip[32]=0x50;ip[33]=0x12
assert decoder.packet(bytes(ip))['flags']==['SYN','ACK'] and decoder.packet(bytes(ip))['destination_port']==80
report={'receive_error_recovery_cases_passed':recovery,'data_and_reentrant_diagnostics_cases_passed':data_cases,'ring_dump_reset_cases_passed':ring_cases,'file_failure_cases_passed':8,'stop_destructor_flush_cases_passed':4,'decoder_ring_cases_passed':ring_cases,'no_file_IO_during_data_path':True,'max_dump_bytes':32800,'limits':'Actual ARM driver/logger and wrappers executed; native OS APIs, protocol callbacks and completion order modeled. No device, full EPOC kernel or physical UART/timing test.'}
(root/'build/driver/ram-diagnostic-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

"""Execute uploaded ER5 TCPIP Send/StartSending paths against the ARM NIF.

The TCPIP image is a private test input, never included in the public archive.
Lookup/list/notification services are modeled; this is not a full TCP stack.
"""
from pathlib import Path
import hashlib,json,struct,sys
from unicorn.arm_const import *

root=Path(__file__).resolve().parent.parent
p=root/'tests/test_ram_diagnostics.py';ns={'__file__':str(p)}
exec(p.read_text().split('recovery=0;')[0],ns)
Diagnostic=ns['Diagnostic'];SELF=ns['SELF'];CHAIN=ns['CHAIN'];API=ns['API'];STACK=ns['STACK'];END=ns['END'];frames=ns['frames']
TCP=0x50000000;ROUTE=0x20400000;NETWORK=0x20401000;IFACE=0x20402000;MANAGER=0x20403000;NIFVT=0x20404000;PROTOCOL=0x2000c000

class Integrated(Diagnostic):
    def __init__(self,folder,base,tcpip):
        self.flow_notifications=0
        super().__init__(folder,base)
        b=tcpip;u=lambda off:struct.unpack_from('<I',b,off)[0]
        code=bytearray(b[u(100):u(100)+u(48)])
        p=u(112)
        if p:
            end=p+8+u(p);p+=8
            while p<end:
                page,size=struct.unpack_from('<II',b,p)
                for q in range(p+8,p+size,2):
                    val=struct.unpack_from('<H',b,q)[0]
                    if val:
                        assert val>>12==3
                        pos=page+(val&4095);old=struct.unpack_from('<I',code,pos)[0]
                        struct.pack_into('<I',code,pos,(old+TCP-u(76))&0xffffffff)
                p+=size
        self.cpu.mem_map(TCP,0x20000);self.cpu.mem_write(TCP,bytes(code))
        self.put(SELF,NIFVT);self.put(NIFVT+0x24,base+0x1cc);self.put(NIFVT+0x18,base+0x220)
        self.put(ROUTE+0x38,NETWORK);self.put(NETWORK+0x88,IFACE);self.put(IFACE+0xc,SELF);self.put(IFACE+0x18,1)
        self.put(MANAGER+8,0x20405000);self.put(0x20405000+0x1c,0x20406000)
    def native_call(self,cpu,addr,size,user):
        if addr==API+0xf000:
            assert cpu.reg_read(UC_ARM_REG_R0)==PROTOCOL and cpu.reg_read(UC_ARM_REG_R1)==SELF
            self.ready+=1;cpu.reg_write(UC_ARM_REG_PC,TCP+0xb2c8);return
        if addr==TCP+0x15ec8:self.return_api(MANAGER);return
        if addr==TCP+0x8fac:
            assert cpu.reg_read(UC_ARM_REG_R1)==SELF
            self.return_api(IFACE);return
        if addr==TCP+0x15d64:self.return_api(0);return
        if addr==TCP+0xa278:
            assert cpu.reg_read(UC_ARM_REG_R1)==IFACE and cpu.reg_read(UC_ARM_REG_R2)==0
            self.flow_notifications+=1;self.return_api(0);return
        if addr==TCP+0x15c44:raise AssertionError('Unexpected TCPIP interface error notification')
        super().native_call(cpu,addr,size,user)
    def ip_send(self,payload):
        self.packet(payload,128);cpu=self.cpu
        cpu.reg_write(UC_ARM_REG_SP,STACK);cpu.reg_write(UC_ARM_REG_LR,END)
        cpu.reg_write(UC_ARM_REG_R0,ROUTE);cpu.reg_write(UC_ARM_REG_R1,CHAIN)
        cpu.emu_start(TCP+0xa7a8,END,count=1000000)
        assert cpu.reg_read(UC_ARM_REG_PC)==END and cpu.reg_read(UC_ARM_REG_SP)==STACK
        return cpu.reg_read(UC_ARM_REG_R0)

def main():
    if len(sys.argv)!=2:raise SystemExit('Usage: python test_tcpip_flow.py /path/to/device/TCPIP.PRT')
    b=Path(sys.argv[1]).read_bytes()
    assert hashlib.sha256(b).hexdigest()=='730c083b5608addb395eb238147328ea7a5e879dc0f79726fcc3a201d79e0ae9','Device TCPIP.PRT does not match the inspected input'
    # Pin inspected instruction sequences, so another layout fails rather than
    # accidentally executing unrelated routines at these private-input offsets.
    assert b[124+0xa7a8:124+0xa7b0]==struct.pack('<II',0xe92d4010,0xe1a04000)
    assert b[124+0xb2c8:124+0xb2d0]==struct.pack('<II',0xe92d4030,0xe24dd00c)
    cases=0
    for base in [0x10000000,0x18000000]:
        old=Integrated('build/diagnostic-042',base,b)
        assert old.ip_send(b'X'*44)==0 and old.get(IFACE+0x18)==2
        old.drain();assert old.ready==old.flow_notifications==1 and old.get(IFACE+0x18)==1
        new=Integrated('build/driver',base,b)
        for _ in range(50):
            assert new.ip_send(b'X'*44)==1 and new.get(IFACE+0x18)==1
            new.drain()
        assert new.ready==new.flow_notifications==0
        assert frames(b''.join(new.writes))==[b'X'*44]*50
        cases+=1
        new=Integrated('build/driver',base,b);packets=[bytes([i])*44 for i in range(12)];returns=[]
        for payload in packets:returns.append(new.ip_send(payload))
        assert returns[:9]==[1]*9 and returns[9:]==[0,0,0],returns
        assert new.get(IFACE+0x18)==2
        new.drain()
        assert new.flow_notifications==new.ready==1 and new.get(IFACE+0x18)==1
        assert frames(b''.join(new.writes))==packets
        assert new.get(SELF+0x49c)==0 and new.get(SELF+0x74)==0x11 and not new.fs_events
        cases+=1
    result={'actual_tcpip_boundary_cases_passed':cases,'old_false_block_and_resume_reproduced':True,'new_small_packets_accepted_without_spurious_resume':100,'queue_saturation_and_actual_native_resume_verified':True,'tcpip_sha256':hashlib.sha256(b).hexdigest(),'executed_tcpip_rvas':['0xa7a8 Send dispatch/return','0xb2c8 StartSending','0x9100 lookup dispatch','0x9134 state transition','0x8274 reads real NIF State'],'limits':'Real ARM NIF and selected device TCPIP code paths; manager lookup, address query and higher-level notification modeled. Does not reproduce complete TCP handshake, physical UART timing or prove browser recovery.'}
    (root/'build/driver/tcpip-flow-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':main()

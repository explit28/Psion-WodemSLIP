"""Execute repair control flow in ARM with mocked SDK allocation APIs."""
import struct,json,random,sys
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm_const import *
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM

root=Path(__file__).resolve().parent.parent
outdir=root/'build/driver'
b=(outdir/'SLIP.NIF').read_bytes();r=json.loads((outdir/'validation.json').read_text())
U=lambda buf,p:struct.unpack_from('<I',buf,p)[0]
SELF=0x20000000;FACTORY=SELF+0x2000;STACK=0x70008000;END=0x40000000;API=0x30000000
REGS=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12,UC_ARM_REG_SP,UC_ARM_REG_LR]

def setup(base):
    cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM);cpu.mem_map(base,0x10000);cpu.mem_write(base,b[124:124+U(b,48)])
    for address in [SELF,0x70000000,API,END]:cpu.mem_map(address,0x10000)
    native={}
    for idx,(name,slot) in enumerate(r['iat'].items()):
        addr=API+idx*0x100;cpu.mem_write(base+slot,struct.pack('<I',addr));native[addr]=name.removeprefix('iat_')
    return cpu,native

def clobber(cpu,ret):
    for reg in [UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R12]:cpu.reg_write(reg,0xaabb0000+reg)
    cpu.reg_write(UC_ARM_REG_R0,ret);cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR))

for base in [0x10000000,0x18000000]:
    for seed in range(4):
        cpu,native=setup(base);events=[];cleanup=[]
        saved=0x12345600+seed
        cpu.mem_write(STACK,struct.pack('<II',saved,END))
        cpu.reg_write(UC_ARM_REG_SP,STACK);cpu.reg_write(UC_ARM_REG_R0,SELF);cpu.reg_write(UC_ARM_REG_R1,FACTORY);cpu.reg_write(UC_ARM_REG_R4,FACTORY)
        def hook(c,addr,size,user):
            if addr==base+0x98:
                assert c.reg_read(UC_ARM_REG_R0)==SELF and c.reg_read(UC_ARM_REG_R1)==FACTORY
                events.append('constructor');clobber(c,SELF);return
            if addr not in native:return
            name=native[addr];events.append(name)
            if name=='cleanup_push':assert c.reg_read(UC_ARM_REG_R0)==SELF;cleanup.append(SELF)
            elif name=='comm_construct':
                assert cleanup==[SELF] and c.reg_read(UC_ARM_REG_R0)==SELF+16
                assert c.reg_read(UC_ARM_REG_R1)==c.reg_read(UC_ARM_REG_R2)==0
                c.mem_write(SELF+16+28,struct.pack('<II',SELF+0x1000,SELF+0x1100))
            elif name=='cleanup_pop':assert cleanup.pop()==SELF
            else:raise AssertionError(name)
            clobber(c,0)
        cpu.hook_add(UC_HOOK_CODE,hook);cpu.emu_start(base+0xe78,END,count=100000)
        assert events==['constructor','cleanup_push','comm_construct','cleanup_pop']
        assert cpu.reg_read(UC_ARM_REG_R0)==SELF and cpu.reg_read(UC_ARM_REG_R4)==saved
        assert cpu.reg_read(UC_ARM_REG_SP)==STACK+8 and cleanup==[]
        if r.get('flow_repair'):assert U(bytes(cpu.mem_read(SELF+0x4a0,4)),0)==8

    # Destructor must preserve the C++ destructor flags and the caller's LR.
    for partial in [False,True]:
        cpu,native=setup(base);events=[]
        cpu.mem_write(SELF+16+28,struct.pack('<II',SELF+0x1000,0 if partial else SELF+0x1100))
        vals=[0x11110000+i for i in range(13)]+[STACK,END];vals[0]=SELF;vals[1]=3
        for reg,val in zip(REGS,vals):cpu.reg_write(reg,val)
        def destructor(c,addr,size,user):
            if addr in native:
                assert native[addr]=='comm_delete' and c.reg_read(UC_ARM_REG_R0)==SELF+16
                events.append('comm_delete');c.mem_write(SELF+44,b'\0'*8);clobber(c,0)
            elif addr==base+0x1104:
                assert c.reg_read(UC_ARM_REG_R0)==SELF and c.reg_read(UC_ARM_REG_R1)==3
                assert c.reg_read(UC_ARM_REG_LR)==END and c.reg_read(UC_ARM_REG_SP)==STACK
                events.append('base_destructor');c.emu_stop()
        cpu.hook_add(UC_HOOK_CODE,destructor);cpu.emu_start(base+0x12c,END,count=100)
        assert events==['comm_delete','base_destructor']
        assert [cpu.reg_read(reg) for reg in REGS]==vals

    # Execute the actual changed handshake instruction for all low 10 bits.
    for handshake in range(1024):
        cpu,_=setup(base);cpu.reg_write(UC_ARM_REG_R3,handshake)
        cpu.emu_start(base+0xd58,base+0xd5c,count=1)
        assert cpu.reg_read(UC_ARM_REG_R3)==handshake&~0xf0

out={'factory_initialization_cases_passed':8,'destructor_cases_passed':4,'handshake_cases_passed':2048,'verified':'CleanupStack-protected initialization; original constructor called with factory; MComm read/write priorities; return value and saved factory frame; cleanup of full/partial initialization; destructor flags and LR; DSR/DCD mask preserves all other low handshake bits','limits':'Native constructor, CleanupStack and MComm allocation/deletion APIs mocked. No hardware test or full Symbian Leave unwinding emulation.'}
(outdir/'repair-checks.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))

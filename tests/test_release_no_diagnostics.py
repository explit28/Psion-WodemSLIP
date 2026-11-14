"""Verify exact 0.4.3 derivation and execute release with diagnostics forbidden."""
from pathlib import Path
import hashlib,json,struct,random
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

root=Path(__file__).resolve().parent.parent
p=root/'tests/test_ram_diagnostics.py';ns={'__file__':str(p)}
exec(p.read_text().split('recovery=0;')[0],ns)
Diagnostic=ns['Diagnostic'];SELF=ns['SELF'];STACK=ns['STACK'];END=ns['END'];frames=ns['frames']
original=(root/'build/diagnostic-043/SLIP.NIF').read_bytes();release=(root/'build/driver/SLIP.NIF').read_bytes()
report=json.loads((root/'build/driver/validation.json').read_text());patch=report['diagnostic_removal']
assert hashlib.sha256(original).hexdigest()=='7d131b4bd6f0654eac93df3e6ffd78faf21b5ab16e5f0f4678ea8ba93d6c721f'
words=[int(x,16) for x in patch['modified_words_file_offsets']]
allowed={p for off in words for p in range(off,off+4)}
assert len(words)==5 and len(release)==len(original)==8572
assert all(x==y or pos in allowed for pos,(x,y) in enumerate(zip(original,release)))
u=lambda b,p:struct.unpack_from('<I',b,p)[0]
assert u(release,u(release,100)+0xe84)==0x8c4
assert u(release,24)==sum(struct.unpack('<'+'I'*(u(release,48)//4),release[u(release,100):u(release,100)+u(release,48)]))&0xffffffff

# Each diagnostic public/internal entry must return with absolutely no data access.
registers=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12,UC_ARM_REG_SP,UC_ARM_REG_LR]
entry_cases=0
for base in [0x10000000,0x18000000]:
    for name in ['ram_init','logger','ram_dump']:
        rva=report['labels'][name]
        assert u(release,u(release,100)+rva)==0xe1a0f00e
        for seed in range(16):
            rng=random.Random(seed);cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM);cpu.mem_map(base,0x10000)
            cpu.mem_write(base+rva,release[u(release,100)+rva:u(release,100)+rva+4]);target=base+0xf000
            values=[rng.randrange(0x1000,0x7fffffff) for _ in registers];values[-1]=target
            flags=rng.choice([0x10,0x20000010,0x80000010,0xf0000010]);cpu.reg_write(UC_ARM_REG_CPSR,flags)
            for reg,val in zip(registers,values):cpu.reg_write(reg,val)
            accesses=[]
            cpu.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,lambda *args:accesses.append(args[2]))
            cpu.emu_start(base+rva,target,count=1)
            assert cpu.reg_read(UC_ARM_REG_PC)==target and cpu.reg_read(UC_ARM_REG_CPSR)==flags
            assert [cpu.reg_read(reg) for reg in registers]==values and not accesses
            entry_cases+=1

class Release(Diagnostic):
    def native_call(self,cpu,addr,size,user):
        key=self.native.get(addr)
        if key and (key[0]=='EFSRV' or key==('EUSER',164)):
            raise AssertionError(f'Forbidden diagnostic file operation: {key}')
        super().native_call(cpu,addr,size,user)

recovery=0;path_cases=0
for base in [0x10000000,0x18000000]:
    for error in [-30,-31,-32]:
        for busy in [False,True]:
            for partial in [b'',b'\xc0abc\xdb',b'\xc0'+b'X'*300+b'\xdb']:
                d=Release('build/driver',base)
                guard_start=SELF+0x8c4;guard=b'Z'*(0x8920-0x8c4);d.cpu.mem_write(guard_start,guard)
                if busy:d.send(b'outgoing'*200,128)
                if partial:d.receive(partial)
                before=d.read_requests;flags=d.get(SELF+0x74);d.call(0x790,error&0xffffffff)
                assert d.get(SELF+0x74)==flags&~8 and d.read_requests==before+1
                d.reply=b'ACK';d.receive(b'\xc0recovered\xc0');d.drain()
                expected=([b'outgoing'*200] if busy else [])+[b'ACK']
                assert frames(b''.join(d.writes))==expected and d.received==[b'recovered']
                assert bytes(d.cpu.mem_read(guard_start,len(guard)))==guard
                assert not d.fs_events and d.get(SELF+0x74)==0x11
                recovery+=1
    d=Release('build/driver',base)
    for i in range(100):
        payload=bytes([i,0xc0,0xdb])*17
        assert d.send(payload,128)==1;d.drain()
    assert d.ready==0 and not d.fs_events
    # Execute Stop's retained wrapper and destructor: neither may dump a file.
    d.cpu.mem_write(STACK,struct.pack('<5I',1,2,3,4,END));d.cpu.reg_write(UC_ARM_REG_SP,STACK);d.cpu.reg_write(UC_ARM_REG_R4,SELF)
    d.cpu.emu_start(base+0x580,END,count=1000)
    assert d.cpu.reg_read(UC_ARM_REG_SP)==STACK+20
    d.call(0x12c,3);assert not d.fs_events
    path_cases+=1

result={'exact_diff_words_verified':len(words),'diagnostic_noop_entry_cases_passed':entry_cases,'release_receive_recovery_cases_passed':recovery,'release_repeated_send_stop_destructor_cases_passed':path_cases,'functional_code_byte_identical_to_working_043':True,'no_diagnostic_buffer_access_after_original_object':True,'object_allocation_bytes':0x8c4,'no_file_IO_in_exercised_paths':True,'driver_sha256':hashlib.sha256(release).hexdigest(),'limits':'Actual ARM driver, wrappers and no-op entries; native APIs/protocol callbacks modeled. A device comparison remains necessary.'}
(root/'build/driver/no-diagnostic-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

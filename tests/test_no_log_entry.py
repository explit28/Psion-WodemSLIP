"""Execute the minimal logger-return instruction and verify exact diff."""
from pathlib import Path
import hashlib,struct,random,json
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

root=Path(__file__).resolve().parent.parent
original=(root/'build/v3-reference/SLIP.NIF').read_bytes()
modified=(root/'build/driver/SLIP.NIF').read_bytes()
assert len(original)==len(modified)==8120
entry=struct.unpack_from('<I',modified,100)[0]+0x1410
assert struct.unpack_from('<I',modified,entry)[0]==0xe1a0f00e
allowed=set(range(24,28))|set(range(entry,entry+4))
assert all(x==y or p in allowed for p,(x,y) in enumerate(zip(original,modified)))
for off in [48,76,84,88,92,96,100,108,112,116]:assert original[off:off+4]==modified[off:off+4]
regs=[UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11,UC_ARM_REG_R12,UC_ARM_REG_SP,UC_ARM_REG_LR]
cases=0
for base in [0x10000000,0x18000000]:
    for seed in range(16):
        cpu=Uc(UC_ARCH_ARM,UC_MODE_ARM);cpu.mem_map(base,0x10000)
        cpu.mem_write(base+0x1410,modified[entry:entry+4]);target=base+0x8000
        rng=random.Random(seed);values=[rng.randrange(1,0x7fffffff) for _ in regs];values[-1]=target
        flags=rng.choice([0x10,0x20000010,0x80000010,0xf0000010])
        cpu.reg_write(UC_ARM_REG_CPSR,flags)
        for reg,value in zip(regs,values):cpu.reg_write(reg,value)
        accesses=[]
        def access(c,kind,address,size,value,user):accesses.append((kind,address))
        cpu.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,access)
        cpu.emu_start(base+0x1410,target,count=2)
        assert cpu.reg_read(UC_ARM_REG_PC)==target
        assert [cpu.reg_read(r) for r in regs]==values
        assert cpu.reg_read(UC_ARM_REG_CPSR)==flags
        assert accesses==[]
        cases+=1
report={'minimal_diff_checked':True,'driver_sha256':hashlib.sha256(modified).hexdigest(),'logger_return_cases_passed':cases,'verified':'Only logger instruction/checksum differ; preserved all registers/flags; no data memory accesses; original image layout/tables unchanged','limits':'No device test; removing synchronous file I/O still changes timing'}
(root/'build/driver/no-log-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

"""Build the repaired ER5 SLIP driver; optional synchronous diagnostic logging.

No new absolute pointers are introduced. The import table is moved to the
end of the image, and existing loader-relocated import-slot references are
retargeted to it. All original imports, exports and relocation sites remain.
"""
from pathlib import Path
import struct, hashlib, json, zipfile, sys
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

U=lambda b,p:struct.unpack_from('<I',b,p)[0]
P=lambda b,p,v:struct.pack_into('<I',b,p,v)
SHA='58ce94961455347d4276297ca42d947ec173e7d5b62660798e375cd7c6b68603'
STAGES={10:'Start entry',20:'Serial initialization entry',30:'PortName read returned; before RComm::Open',40:'RComm::Open returned',50:'Read current serial configuration returned',60:'Set serial configuration returned',70:'Serial initialization returned to Start',80:'Read scheduling returned; before protocol callback',90:'Protocol callback returned; before LinkLayerUp',100:'LinkLayerUp returned; before progress callback',110:'Progress callback returned; Start about to return',120:'Send entry',130:'Send return value about to be finalized'}
HOOKS=[(0x460,10,'r0'),(0xc54,20,'r0'),(0xcf8,30,'r6'),(0xd08,40,'r6'),(0xd24,50,'r6'),(0xd6c,60,'r6'),(0x46c,70,'r5'),(0x49c,80,'r5'),(0x4b0,90,'r5'),(0x4c0,100,'r5'),(0x4d8,110,'r5')]

def branch(src,dst):
    rel=dst-src-8
    assert rel%4==0 and -(1<<25)<=rel<(1<<25)
    return struct.pack('<I',0xea000000|((rel//4)&0xffffff))

class Asm:
    def __init__(self,base):self.base=base;self.b=bytearray();self.labels={};self.fixes=[];self.ks=Ks(KS_ARCH_ARM,KS_MODE_ARM)
    @property
    def pc(self):return self.base+len(self.b)
    def label(self,n):assert n not in self.labels;self.labels[n]=self.pc
    def ins(self,s):
        out,n=self.ks.asm(s,addr=self.pc);assert len(out)==4,(s,out);self.b.extend(out)
    def ref(self,op,name):self.fixes.append((len(self.b),op,name));self.b.extend(b'\0'*4)
    def align(self):self.b.extend(b'\0'*(-len(self.b)%4))
    def finish(self,extra):
        labels=self.labels|extra
        for pos,op,name in self.fixes:
            pc=self.base+pos;target=labels[name]
            if op in ['b','bl','beq','bne','bhi']:s=f'{op} #{target}'
            elif op.startswith('ldr '):
                delta=target-pc-8;assert abs(delta)<=4095
                s=op+f', [pc, #{delta}]'
            elif op.startswith('adr '):
                delta=target-pc-8
                s=('add' if delta>=0 else 'sub')+op[3:]+f', pc, #{abs(delta)}'
            else:raise ValueError(op)
            out,n=self.ks.asm(s,addr=pc);assert len(out)==4,s;self.b[pos:pos+4]=bytes(out)
        return self.b

def relocs(b):
    p=U(b,112);end=p+8+U(b,p);count=U(b,p+4);p+=8;sites=[]
    while p<end:
        page,sz=struct.unpack_from('<II',b,p)
        for q in range(p+8,p+sz,2):
            e=struct.unpack_from('<H',b,q)[0]
            if e:assert e>>12==3;sites.append(page+(e&4095))
        p+=sz
    assert p==end and len(sites)==count
    return sites

def build(src,outdir,repair=True,packet_repair=True,tx_repair=True,trace=False,sdk_root=None,ram_trace=False,flow_repair=False):
    assert not packet_repair or repair
    assert not tx_repair or packet_repair
    assert not flow_repair or ram_trace
    original=Path(src).read_bytes();assert hashlib.sha256(original).hexdigest()==SHA
    start,size,base=U(original,100),U(original,48),U(original,76)
    oldiat=U(original,96);oldimp=U(original,108);p=oldimp+4;groups=[]
    for _ in range(U(original,84)):
        nameoff,n=struct.unpack_from('<II',original,p)
        name=original[oldimp+nameoff:original.index(b'\0',oldimp+nameoff)].decode()
        ords=list(struct.unpack_from('<'+'I'*n,original,p+8));groups.append((name,ords));p+=8+n*4
    original_groups=[(n,list(o)) for n,o in groups]
    # EUSER RHandleBase::Close; EFSRV APIs taken from exact SDK import libs.
    if trace:groups[0][1].append(164)
    if repair:
        # Initialize and delete the MComm reader/writer pair explicitly.
        groups[0][1].extend([807,776])  # CleanupStack PushL(CBase*), Pop()
        groups[3][1].extend([14,15])    # MComm CommConstructL, CommDelete
    if trace:
        groups.append(('EFSRV[100000bb].DLL',[17,105,133,142,170,46,14]))
        # Verify the filename UID against the import library, not an assumed UID.
        lib=Path(sdk_root)/'EPOC32/Release/MARM/Rel/EFSRV.LIB'
        import re
        names=re.findall(rb'EFSRV\[[0-9a-fA-F]+\]\.DLL',lib.read_bytes())
        assert names and len(set(names))==1
        groups[-1]=(names[0].decode(),groups[-1][1])
    a=Asm(size)
    ram=None
    if ram_trace:
        assert trace and repair and tx_repair
        import importlib.util
        spec=importlib.util.spec_from_file_location('ram_diagnostics',Path(__file__).with_name('ram_diagnostics.py'))
        ram=importlib.util.module_from_spec(spec);spec.loader.exec_module(ram)
        ram.emit(a)
    if trace and not ram_trace:
        a.label('logger')
        for s in ['push {r4-r11, lr}','sub sp, sp, #80','mov r4, r1','mov r5, r0','mov r6, r2','mov r7, #0']:
            a.ins(s)
        for off in range(0,32,4):a.ins(f'str r7, [sp, #{off}]')
        a.ref('ldr r7','magic');a.ins('str r7, [sp, #32]');a.ins('str r5, [sp, #36]')
        for src_off,dst_off in [(0,40),(4,44),(8,48),(12,52),(20,56),(24,60),(52,64)]:
            a.ins(f'ldr r7, [r4, #{src_off}]');a.ins(f'str r7, [sp, #{dst_off}]')
        for src_off,dst_off in [(12,68),(120,72),(116,76)]:
            a.ins(f'ldr r7, [r6, #{src_off}]');a.ins(f'str r7, [sp, #{dst_off}]')
        # RFs is 12 bytes; RFile/RSubSessionBase is 16 bytes in ER5 headers.
        a.ins('mov r0, sp');a.ins('mov r1, #4');a.ref('bl','connect')
        a.ins('cmp r0, #0');a.ref('bne','done')
        # Construct TPtrC8 on the stack from a PC-relative filename pointer.
        a.ins('sub sp, sp, #8')
        a.ins('mov r7, #0x10000000');a.ins('orr r7, r7, #14');a.ins('str r7, [sp]')
        a.ref('adr r7','filename');a.ins('str r7, [sp, #4]')
        for s in ['add r0, sp, #20','add r1, sp, #8','mov r2, sp','mov r3, #0x200']:a.ins(s)
        a.ref('bl','open');a.ins('cmn r0, #1');a.ref('bne','opened')
        for s in ['add r0, sp, #20','add r1, sp, #8','mov r2, sp','mov r3, #0x200']:a.ins(s)
        a.ref('bl','replace')
        a.label('opened');a.ins('cmp r0, #0');a.ref('bne','fsclose')
        a.ins('mov r7, #0');a.ins('str r7, [sp, #36]')
        a.ins('add r0, sp, #20');a.ins('mov r1, #3');a.ins('add r2, sp, #36');a.ref('bl','seek')
        a.ins('cmp r0, #0');a.ref('bne','fileclose')
        # Reuse the 8-byte descriptor frame for the 48-byte trace record.
        a.ins('mov r7, #0x10000000');a.ins('orr r7, r7, #48');a.ins('str r7, [sp]')
        a.ins('add r7, sp, #40');a.ins('str r7, [sp, #4]')
        a.ins('add r0, sp, #20');a.ins('mov r1, sp');a.ref('bl','write')
        a.ins('add r0, sp, #20');a.ref('bl','flush')
        a.label('fileclose');a.ins('add r0, sp, #20');a.ref('bl','file_close')
        a.label('fsclose');a.ins('add r0, sp, #8');a.ref('bl','fs_close');a.ins('add sp, sp, #8')
        a.label('done');a.ins('add sp, sp, #80');a.ins('pop {r4-r11, pc}')
    api_names=['connect','open','replace','seek','write','flush','file_close','fs_close'] if trace else []
    if repair:api_names.extend(['cleanup_push','cleanup_pop','comm_construct','comm_delete'])
    for name in api_names:
        a.label(name);a.ref('ldr ip','iat_'+name);a.ins('mov pc, ip')
    if trace:
        a.align();a.label('magic');a.b.extend(struct.pack('<I',0x314c5053))
        a.label('filename');a.b.extend(b'C:\\SLIPDBG.BIN\0');a.align()
        assert len(b'C:\\SLIPDBG.BIN')==14
    hook_targets={}
    md=Cs(CS_ARCH_ARM,CS_MODE_ARM)
    active_hooks=HOOKS+([(0x1cc,120,'r0'),(0x218,130,'r5')] if packet_repair else [])
    if tx_repair:
        STAGES.update({140:'Transmit encoder entry',150:'Encoded bytes ready; before serial write',160:'Serial write completion callback',170:'Serial read completion callback',180:'Received packet about to enter IP stack',190:'Received packet callback returned'})
        active_hooks.extend([(0x590,140,'r0'),(0x728,150,'r6'),(0x768,160,'r0'),(0x790,170,'r0'),(0x97c,180,'r5'),(0x994,190,'r5')])
    if ram_trace:
        STAGES[200]='Stop complete; bounded diagnostics dump'
        active_hooks.append((0x580,200,'r4'))
    for site,stage,selfreg in (active_hooks if trace else []):
        old=original[start+site:start+site+4]
        inst=list(md.disasm(old,site));assert len(inst)==1 and ('pc' not in inst[0].op_str or (ram_trace and stage==200))
        a.label('hook_'+str(stage));hook_targets[site]=a.pc
        for s in ['push {r0-r12, lr}','mrs r12, cpsr','push {r12}',f'mov r2, {selfreg}',f'mov r0, #{stage}','add r1, sp, #4']:a.ins(s)
        a.ref('bl','logger')
        for s in ['pop {r12}','msr cpsr_f, r12','pop {r0-r12, lr}']:a.ins(s)
        a.b.extend(old);a.b.extend(branch(a.pc,site+4))
    extra_patches={}
    if repair:
        # Replace factory's final pop/tail-call with a protected second-phase
        # initialization. The factory's original {r4,lr} frame remains live.
        assert original[start+0xe78:start+0xe80]==struct.pack('<I',0xe8bd4010)+branch(0xe7c,0x98)
        a.label('factory_initialize');extra_patches[0xe78]=a.pc
        a.b.extend(struct.pack('<I',0xeb000000|(((0x98-a.pc-8)//4)&0xffffff)))
        a.ins('mov r4, r0')
        if flow_repair:
            a.ins('mov r3, #8');a.ins('str r3, [r4, #1184]')
        a.ref('bl','cleanup_push')
        a.ins('add r0, r4, #16');a.ins('mov r1, #0');a.ins('mov r2, #0');a.ref('bl','comm_construct')
        a.ref('bl','cleanup_pop');a.ins('mov r0, r4')
        if ram_trace:a.ref('bl','ram_init')
        a.ins('pop {r4, pc}')
        # MComm's allocated reader/writer objects must also be deleted.
        assert original[start+0x12c:start+0x130]==branch(0x12c,0x1104)
        a.label('destructor_cleanup');extra_patches[0x12c]=a.pc
        a.ins('push {r0-r3, r12, lr}')
        if ram_trace:
            a.ref('bl','ram_dump');a.ins('ldr r0, [sp]')
        a.ins('add r0, r0, #16');a.ref('bl','comm_delete')
        a.ins('pop {r0-r3, r12, lr}');a.b.extend(branch(a.pc,0x1104))
    if packet_repair:
        assert original[start+0x1d8:start+0x1dc]==struct.pack('<I',0xe2850080)
        a.label('send_count_before_transfer');extra_patches[0x1d8]=a.pc
        a.ins('mov r0, r4')
        a.b.extend(struct.pack('<I',0xeb000000|(((0x105c-a.pc-8)//4)&0xffffff)))
        a.ins('push {r0}')
        a.ins('add r0, r5, #128');a.ins('mov r1, r4')
        a.b.extend(struct.pack('<I',0xeb000000|(((0x1050-a.pc-8)//4)&0xffffff)))
        a.ins('pop {r0}');a.b.extend(branch(a.pc,0x1e8))
    if tx_repair:
        # A newly dequeued packet's first mbuf needs the same pointer/end
        # setup as subsequent mbufs. The old jump bypasses that setup.
        assert original[start+0x660:start+0x664]==branch(0x660,0x6ac)
        a.label('tx_first_buffer');extra_patches[0x660]=a.pc
        a.ins('cmp r0, #0');a.ref('beq','tx_first_empty')
        a.b.extend(branch(a.pc,0x664))
        a.label('tx_first_empty');a.b.extend(branch(a.pc,0x5ec))
        # SetLength requires used bytes, not remaining capacity.
        assert U(original,start+0x710)==0xe0651009
        a.label('tx_used_length');extra_patches[0x710]=a.pc
        a.ins('add r0, r6, #148')
        a.b.extend(struct.pack('<I',0xeb000000|(((0xf78-a.pc-8)//4)&0xffffff)))
        a.ins('sub r1, r5, r0');a.b.extend(branch(a.pc,0x714))
        # Bit 0x20 records a frame whose closing END delimiter is pending.
        # Avoid an endless stream of END bytes after the last write finishes.
        assert U(original,start+0x588)==0xe92d47f0
        a.label('tx_idle_check');extra_patches[0x588]=a.pc
        for off in [140,136,128]:
            a.ins(f'ldr r3, [r0, #{off}]');a.ins('cmp r3, #0');a.ref('bne','tx_enter')
        a.ins('ldr r3, [r0, #116]');a.ins('tst r3, #32');a.ref('bne','tx_enter')
        # A Send() that returned blocked must be woken after the final write.
        a.ins('tst r3, #2');a.ref('beq','tx_idle_return')
        a.ins('bic r3, r3, #2');a.ins('str r3, [r0, #116]')
        a.ins('mov r1, r0');a.ins('ldr r0, [r0, #120]');a.ins('cmp r0, #0');a.ref('beq','tx_idle_return')
        a.ins('ldr r3, [r0]');a.ins('ldr pc, [r3, #40]')
        a.label('tx_idle_return');a.ins('mov pc, lr')
        a.label('tx_enter');a.ins('push {r4-r10, lr}');a.b.extend(branch(a.pc,0x58c))
        assert original[start+0x634:start+0x638]==struct.pack('<I',0x0a000034)
        a.label('tx_frame_pending');extra_patches[0x634]=a.pc
        a.ins('ldr r3, [r6, #116]');a.ins('cmp r0, #0');a.ref('beq','tx_no_packet')
        a.ins('orr r3, r3, #32');a.ins('str r3, [r6, #116]');a.b.extend(branch(a.pc,0x638))
        a.label('tx_no_packet');a.ins('bic r3, r3, #32');a.ins('str r3, [r6, #116]');a.b.extend(branch(a.pc,0x70c))
        # Record the protocol's blocked state when Send returns false.
        assert U(original,start+0x20c)==0xe5950074
        a.label('tx_record_backpressure');extra_patches[0x20c]=a.pc
        if flow_repair:
            # A pending UART write is not queue exhaustion. Keep accepting
            # packets until queued data mbufs exceed the high-water mark.
            a.ins('ldr r0, [r5, #116]');a.ins('ldr r1, [r5, #1180]');a.ins('ldr r2, [r5, #1184]')
            a.ins('cmp r1, r2');a.ins('orrgt r0, r0, #2');a.ins('strgt r0, [r5, #116]')
            a.ins('tst r0, #2');a.ins('moveq r0, #1');a.ins('movne r0, #0');a.b.extend(branch(a.pc,0x218))
        else:
            a.ins('ldr r0, [r5, #116]');a.ins('tst r0, #4')
            a.ins('orrne r0, r0, #2');a.ins('strne r0, [r5, #116]');a.b.extend(branch(a.pc,0x210))
        # Balance the queue's data-mbuf counter as each mbuf is released.
        assert U(original,start+0x700)==0xe3a03000
        a.label('tx_count_released_buffer');extra_patches[0x700]=a.pc
        a.ins('ldr r3, [r6, #1180]');a.ins('sub r3, r3, #1');a.ins('str r3, [r6, #1180]')
        a.ins('mov r3, #0');a.b.extend(branch(a.pc,0x704))
        # Resume a partially filled receive mbuf at its saved cursor.
        assert U(original,start+0x8e0)==0xe5913018
        a.label('rx_resume_partial');extra_patches[0x8e0]=a.pc
        a.ins('ldr r3, [r1, #24]');a.ins('ldr r2, [r1, #8]');a.ins('add r6, r3, r2')
        a.ins('ldr r3, [r1, #12]');a.ins('add r8, r6, r3')
        a.ins('ldr r6, [r5, #2232]');a.b.extend(branch(a.pc,0x8f4))
        # A receive chunk must not clear link/write/serial/frame state bits.
        assert U(original,start+0xa6c)==0xe2033008
        # Queue the final partial mbuf, using its used length. An exact-size
        # final mbuf was already queued and leaves current == NULL.
        assert U(original,start+0x948)==0xe0662008
        a.label('rx_finish_partial');extra_patches[0x948]=a.pc
        a.ins('ldr r3, [r5, #2228]');a.ins('cmp r3, #0');a.ref('beq','rx_finish_ready')
        a.ins('ldr r2, [r3, #24]');a.ins('ldr r0, [r3, #8]');a.ins('add r2, r2, r0')
        a.ins('sub r2, r6, r2');a.ins('str r2, [r3, #12]');a.ins('mov r1, r3')
        a.ins('add r0, r5, #2224');a.ins('add r0, r0, #12')
        a.b.extend(struct.pack('<I',0xeb000000|(((0x10c8-a.pc-8)//4)&0xffffff)))
        a.ins('mov r3, #0');a.ins('str r3, [r5, #2228]')
        a.label('rx_finish_ready');a.b.extend(branch(a.pc,0x954))
    a.align();newiat=a.pc
    slots={};flat=[]
    for group,ords in groups:
        for ordinal in ords:
            slots[(group,ordinal)]=newiat+len(flat)*4;flat.append(ordinal)
    euser=groups[0][0];efs=groups[-1][0] if trace else None
    ext={}
    if trace:
        for name,ordinal in zip(['connect','open','replace','seek','write','flush','file_close'],[17,105,133,142,170,46,14]):ext['iat_'+name]=slots[(efs,ordinal)]
        ext['iat_fs_close']=slots[(euser,164)]
    if repair:
        for name,group,ordinal in [('cleanup_push',euser,807),('cleanup_pop',euser,776),('comm_construct',groups[3][0],14),('comm_delete',groups[3][0],15)]:ext['iat_'+name]=slots[(group,ordinal)]
    appended=a.finish(ext)
    code=bytearray(original[start:start+size])+appended
    code.extend(struct.pack('<'+'I'*(len(flat)+1),*(flat+[0])))
    # Retarget every relocated reference to an old import slot.
    mapping={};idx=0
    for group,ords in original_groups:
        for ordinal in ords:mapping[base+oldiat+idx*4]=base+slots[(group,ordinal)];idx+=1
    relocated_import_refs=[]
    for site in relocs(original):
        val=U(code,site)
        if val in mapping:P(code,site,mapping[val]);relocated_import_refs.append(site)
    assert len(relocated_import_refs)==len(mapping)
    for site,target in hook_targets.items():code[site:site+4]=branch(site,target)
    if repair:
        for site,target in extra_patches.items():code[site:site+4]=branch(site,target)
        # The stock driver forcibly enables obey/fail DSR and DCD (0xf0).
        # Direct serial wiring need not supply these modem carrier signals.
        assert U(code,0xd58)==0xe38330f0
        P(code,0xd58,0xe3c330f0)  # BIC instead of ORR; preserve CTS/XON/XOFF.
    if tx_repair:
        P(code,0xa6c,0xe1a03003)  # MOV r3,r3: keep the parser's updated flags
    if ram_trace:
        assert U(code,0x850)==0xe2033008 and U(code,0xe84)==0x8c4
        P(code,0x850,0xe3c33008)  # BIC #8: discard escape state, keep link/TX state.
        P(code,0xe84,ram.OBJECT_SIZE)
    # Import block stores each DLL name offset, count, then ordinal list.
    imports=bytearray(b'\0'*4);blocks=[]
    for name,ords in groups:
        blocks.append((len(imports),name));imports.extend(struct.pack('<II',0,len(ords)));imports.extend(struct.pack('<'+'I'*len(ords),*ords))
    for pos,name in blocks:P(imports,pos,len(imports));imports.extend(name.encode()+b'\0')
    imports.extend(b'\0'*(-len(imports)%4));P(imports,0,len(imports))
    oldrel=U(original,112);relblob=original[oldrel:]
    b=bytearray(original[:start])+code+imports+relblob
    P(b,48,len(code));P(b,84,len(groups));P(b,96,newiat);P(b,108,start+len(code));P(b,112,start+len(code)+len(imports))
    assert U(original,116)==0 and U(original,52)==0
    P(b,24,sum(struct.unpack('<'+'I'*(len(code)//4),code))&0xffffffff)
    assert relocs(b)==relocs(original)
    assert b[U(b,112):]==original[oldrel:]
    assert b[U(b,88):U(b,88)+U(b,92)*4]==original[U(original,88):U(original,88)+U(original,92)*4]
    allowed=set(relocated_import_refs)|set(hook_targets)|set(extra_patches)
    if repair:allowed.add(0xd58)
    if tx_repair:allowed.add(0xa6c)
    if ram_trace:allowed.update([0x850,0xe84])
    for pos in range(0,size,4):assert pos in allowed or code[pos:pos+4]==original[start+pos:start+pos+4]
    outdir=Path(outdir);outdir.mkdir(parents=True,exist_ok=True)
    (outdir/'SLIP.NIF').write_bytes(b)
    (outdir/'SLIP-original.NIF').write_bytes(original)
    (outdir/'build_driver.py').write_bytes(Path(__file__).read_bytes())
    report={'status':'0.4.0 preview; clean SIS build not yet hardware-tested','trace_enabled':trace,'repairs':['MComm second-phase initialization protected by CleanupStack','MComm destructor cleanup preserving destructor arguments','clear forced DSR/DCD obey/fail bits; preserve other serial handshake flags'] if repair else [],'original_sha256':SHA,'patched_sha256':hashlib.sha256(b).hexdigest(),'size':len(b),'logger_rva':a.labels.get('logger'),'new_iat_rva':newiat,'old_import_refs_retargeted':len(relocated_import_refs),'stages':STAGES,'hooks':hook_targets,'repair_hooks':extra_patches,'labels':a.labels,'iat':ext,'record_format':'12 little-endian uint32: magic,stage,r0,r1,r2,r3,r5,r6,lr,notify,protocol,state','record_size':48,'efsrv':efs}
    if packet_repair:report['repairs'].append('Count outgoing mbufs before Append transfers ownership and empties the caller chain')
    if tx_repair:report['repairs'].extend(['Initialize first transmit mbuf byte pointers','Set serial descriptor length to encoded bytes used','Track pending frame delimiter to avoid idle repeated writes','Balance data-mbuf count and wake blocked protocol when final serial write completes','Resume receive cursor across chunks; preserve non-parser flags','Finalize partial receive mbuf with used length and queue it; handle exact full-buffer frames without null dereference'])
    if ram_trace:
        report.update(status='0.4.2 diagnostic preview; hardware test pending',trace_mode='bounded RAM ring; flush only on Stop/destruction',record_size=ram.RECORD_SIZE,record_format='WDR1 header + register/state snapshots + up to 64 packet bytes',ram_header_offset=ram.HEADER,ram_records_offset=ram.RECORDS,ram_capacity=ram.CAPACITY,object_size=ram.OBJECT_SIZE,dump_path='C:\\WODEMDIAG.BIN',max_dump_bytes=32+ram.CAPACITY*ram.RECORD_SIZE)
        report['repairs'].append('Serial framing/parity/overrun recovery preserves operational flags and rearms reads')
    if flow_repair:
        report.update(status='0.4.3 diagnostic preview; hardware test pending',flow_repair=True,tx_high_water_mbufs=8)
        report['repairs'].append('Accept packets while queue capacity remains; mark blocked only above initialized mbuf high-water mark, independently of UART write-in-progress')
    (outdir/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return original,bytes(b),report

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Build the repaired ER5 SLIP driver from exact SDK inputs.')
    parser.add_argument('--sdk-root',type=Path,required=True,help='SDK Cpp directory containing EPOC32')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--trace',action='store_true',help='Include persistent diagnostic logging')
    args=parser.parse_args()
    if not args.trace:parser.error('Use build.py for the minimal no-log release; direct driver builds require --trace')
    src=args.sdk_root/'EPOC32/Release/MARM/Rel/SLIP.NIF'
    _,_,report=build(src,args.output,trace=args.trace,sdk_root=args.sdk_root)
    print(json.dumps({k:v for k,v in report.items() if k not in ['labels','iat']},indent=2))

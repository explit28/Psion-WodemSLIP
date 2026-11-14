"""ARMv4-compatible bounded diagnostics; file I/O only on Stop/destruction.

The object's extra storage holds a 32-byte header and 256 128-byte records.
Records contain register/state snapshots and up to 64 IP packet bytes. No
TCP payload beyond that prefix is copied. The dump overwrites one fixed file.
"""
import struct

HEADER=0x900
RECORDS=0x920
CAPACITY=256
RECORD_SIZE=128
OBJECT_SIZE=RECORDS+CAPACITY*RECORD_SIZE
MAGIC=0x31524457  # WDR1

def emit(a):
    a.label('ram_init')
    a.ins('push {r0-r3, lr}')
    a.ins('add r1, r0, #0x900');a.ins('mov r2, #0x8000');a.ins('add r2, r2, #32')
    a.ins('mov r3, #0')
    a.label('ram_zero');a.ins('str r3, [r1], #4');a.ins('subs r2, r2, #4');a.ref('bne','ram_zero')
    a.ins('add r1, r0, #0x900');a.ref('ldr r2','ram_magic');a.ins('str r2, [r1]')
    for off,val in [(4,1),(8,128),(12,256)]:a.ins(f'mov r2, #{val}');a.ins(f'str r2, [r1, #{off}]')
    a.ins('pop {r0-r3, pc}')
    a.label('logger')
    a.ins('push {r4-r11, lr}');a.ins('mov r4, r0');a.ins('mov r5, r1');a.ins('mov r6, r2')
    a.ins('cmp r4, #10');a.ref('bne','ram_record')
    a.ins('mov r0, r6');a.ref('bl','ram_init')
    a.label('ram_record')
    a.ins('add r7, r6, #0x900');a.ins('ldr r8, [r7, #16]')
    a.ins('and r9, r8, #255');a.ins('add r9, r6, r9, lsl #7');a.ins('add r9, r9, #0x900');a.ins('add r9, r9, #32')
    # Erase the destination record so short packet prefixes never expose old data.
    a.ins('mov r0, r9');a.ins('mov r1, #32');a.ins('mov r2, #0')
    a.label('ram_record_zero');a.ins('str r2, [r0], #4');a.ins('subs r1, r1, #1');a.ref('bne','ram_record_zero')
    a.ref('ldr r0','ram_magic');a.ins('str r0, [r9]');a.ins('str r4, [r9, #4]');a.ins('str r8, [r9, #8]')
    a.ins('ldr r0, [r6, #116]');a.ins('str r0, [r9, #12]')
    for src,dst in [(0,16),(4,20),(8,24),(12,28),(20,32),(24,36),(52,40)]:
        a.ins(f'ldr r0, [r5, #{src}]');a.ins(f'str r0, [r9, #{dst}]')
    for src,dst in [(0x49c,44),(0x8b0,48),(0x4a8,52)]:
        a.ins(f'ldr r0, [r6, #{src}]');a.ins(f'str r0, [r9, #{dst}]')
    a.ins('str r6, [r9, #60]')
    # Send entry uses r1=chain; Process entry uses r4=stack packet chain.
    a.ins('cmp r4, #120');a.ins('ldreq r0, [r5, #4]');a.ref('beq','ram_packet')
    a.ins('cmp r4, #180');a.ref('bne','ram_commit');a.ins('ldr r0, [r5, #16]')
    a.label('ram_packet');a.ins('cmp r0, #0');a.ref('beq','ram_commit')
    a.ins('ldr r0, [r0]');a.ins('cmp r0, #0');a.ref('beq','ram_commit')
    a.ins('ldr r10, [r0]')  # Skip packed metadata mbuf.
    a.ins('mov r11, #0');a.ins('mov r3, #0')
    a.label('ram_mbuf');a.ins('cmp r10, #0');a.ref('beq','ram_packet_done')
    # Bound traversal even if the diagnostic sees a malformed/empty chain.
    a.ins('add r3, r3, #1');a.ins('cmp r3, #64');a.ref('bhi','ram_packet_done')
    a.ins('ldr r0, [r10, #24]');a.ins('ldr r1, [r10, #8]');a.ins('add r0, r0, r1');a.ins('ldr r1, [r10, #12]')
    a.label('ram_byte');a.ins('cmp r1, #0');a.ref('beq','ram_next_mbuf')
    a.ins('ldrb r2, [r0], #1');a.ins('add ip, r9, #64');a.ins('strb r2, [ip, r11]')
    a.ins('add r11, r11, #1');a.ins('cmp r11, #64');a.ref('beq','ram_packet_done')
    a.ins('sub r1, r1, #1');a.ref('b','ram_byte')
    a.label('ram_next_mbuf');a.ins('ldr r10, [r10]');a.ref('b','ram_mbuf')
    a.label('ram_packet_done');a.ins('str r11, [r9, #56]')
    a.label('ram_commit');a.ins('add r8, r8, #1');a.ins('str r8, [r7, #16]')
    a.ins('and r0, r8, #255');a.ins('str r0, [r7, #20]')
    a.ins('cmp r4, #200');a.ref('bne','ram_logger_return')
    a.ins('mov r0, r6');a.ref('bl','ram_dump')
    a.label('ram_logger_return');a.ins('pop {r4-r11, pc}')
    a.label('ram_dump')
    a.ins('push {r4-r11, lr}');a.ins('mov r6, r0');a.ins('add r6, r6, #0x900')
    a.ins('ldr r7, [r6, #16]');a.ins('cmp r7, #0');a.ref('beq','ram_dump_return')
    a.ins('ldr r0, [r6, #24]');a.ins('cmp r0, r7');a.ref('beq','ram_dump_return')
    a.ins('sub sp, sp, #40');a.ins('mov r0, #0')
    for off in range(0,40,4):a.ins(f'str r0, [sp, #{off}]')
    a.ins('mov r0, sp');a.ins('mov r1, #4');a.ref('bl','connect')
    a.ins('cmp r0, #0');a.ref('bne','ram_dump_stack_return')
    # TPtrC8 filename descriptor at stack+28, RFs at +0, RFile at +12.
    a.ins('mov r0, #0x10000000');a.ins('orr r0, r0, #16');a.ins('str r0, [sp, #28]')
    a.ref('adr r0','ram_filename');a.ins('str r0, [sp, #32]')
    a.ins('add r0, sp, #12');a.ins('mov r1, sp');a.ins('add r2, sp, #28');a.ins('mov r3, #0x200');a.ref('bl','replace')
    a.ins('cmp r0, #0');a.ref('bne','ram_dump_fsclose')
    # Only initialized records are written until the ring fills.
    a.ins('cmp r7, #256');a.ins('movhi r7, #256');a.ins('mov r0, r7, lsl #7');a.ins('add r0, r0, #32')
    a.ins('orr r0, r0, #0x10000000');a.ins('str r0, [sp, #28]');a.ins('str r6, [sp, #32]')
    a.ins('add r0, sp, #12');a.ins('add r1, sp, #28');a.ref('bl','write')
    a.ins('cmp r0, #0');a.ref('bne','ram_dump_fileclose')
    a.ins('add r0, sp, #12');a.ref('bl','flush');a.ins('cmp r0, #0');a.ref('bne','ram_dump_fileclose')
    a.ins('ldr r0, [r6, #16]');a.ins('str r0, [r6, #24]')
    a.label('ram_dump_fileclose');a.ins('add r0, sp, #12');a.ref('bl','file_close')
    a.label('ram_dump_fsclose');a.ins('mov r0, sp');a.ref('bl','fs_close')
    a.label('ram_dump_stack_return');a.ins('add sp, sp, #40')
    a.label('ram_dump_return');a.ins('pop {r4-r11, pc}')
    a.align();a.label('ram_magic');a.b.extend(struct.pack('<I',MAGIC))
    a.label('ram_filename');a.b.extend(b'C:\\WODEMDIAG.BIN\0');a.align()

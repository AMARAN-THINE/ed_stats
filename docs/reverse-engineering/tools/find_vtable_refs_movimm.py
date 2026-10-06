# Ghidra headless postScript: companion to find_vtable_refs.py -- scans .text for the
# sibling address-materialization idiom, `MOV r64, imm64` (REX.W + 0xB8..0xBF + 8-byte
# immediate), whose immediate matches one of TARGETS. Some compilers/codegen paths use
# this absolute-immediate form instead of a RIP-relative LEA for loading a constant
# pointer (e.g. a vtable address) into a register before storing it into an object.
#
# Same chunked-read approach as find_vtable_refs.py (avoids OOM on large .text sections).
# Usage identical: edit TARGETS, run as a -postScript against an already-imported project.

import struct

af = currentProgram.getAddressFactory()
mem = currentProgram.getMemory()
out = open("vtable_movimm_scan_results.txt", "w")

TARGETS = set([0x14553d420, 0x14553d418])  # <-- edit: the address(es) to search for

REX_BYTES = set([0x48, 0x49])

block = mem.getBlock(".text")
CHUNK = 4 * 1024 * 1024
total = block.getSize()
base = block.getStart()
hits = 0
pos = 0
prev_tail = b""
while pos < total:
    sz = min(CHUNK, total - pos)
    buf = bytearray(sz)
    mem.getBytes(base.add(pos), buf, 0, sz)
    bdata = prev_tail + bytes(buf)
    offset_base = pos - len(prev_tail)
    n = len(bdata)
    for i in range(0, n - 9):
        if bdata[i] not in REX_BYTES:
            continue
        b1 = bdata[i + 1]
        if b1 < 0xb8 or b1 > 0xbf:
            continue
        imm = struct.unpack('<Q', bdata[i + 2:i + 10])[0]
        if imm in TARGETS:
            insn_addr = base.add(offset_base + i)
            out.write("HIT at %s -> imm 0x%x\n" % (insn_addr, imm))
            hits += 1
    prev_tail = bdata[-9:]
    pos += sz
    del buf, bdata

out.write("total hits: %d\n" % hits)
out.close()
print("DONE", hits)

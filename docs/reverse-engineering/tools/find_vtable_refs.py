# Ghidra headless postScript: find RIP-relative LEA instructions (`LEA reg, [rip+disp32]`)
# across the whole .text section whose computed target matches one of TARGETS.
#
# Purpose: locate constructors that materialize a vtable-pointer constant, when Ghidra's
# own reference analysis hasn't created an xref to that address (e.g. the constructor's
# code region wasn't disassembled as instructions in the original analysis pass, or the
# analysis was run with -noanalysis against an already-imported project).
#
# This is a pure byte-pattern scan, independent of Ghidra's disassembly/analysis state --
# it reads raw bytes directly and decodes the REX + 0x8D (LEA) + ModRM(mod=00,rm=101)
# encoding by hand, in bounded chunks to avoid loading an entire (tens-of-MB) section into
# memory at once (a naive single bytearray(block.getSize()) read can OOM the JVM heap).
#
# Usage: edit TARGETS below to the address(es) you're hunting (e.g. a vtable's first-slot
# address, found via scan_vtable_slots.py or similar), then run:
#   analyzeHeadless <project_dir> <project_name> -process <file> -noanalysis \
#       -scriptPath <dir_containing_this_file> -postScript find_vtable_refs.py
#
# A zero-hit result is itself informative: it rules out the two most common idioms for
# materializing an absolute address (this LEA form, and the sibling MOV r64,imm64 form in
# find_vtable_refs_movimm.py-equivalent logic) and points toward multiple-inheritance
# adjustor-thunk construction (secondary vtable address computed via pointer arithmetic
# from a primary vtable, rather than a second literal constant) as the likely explanation.

import struct

af = currentProgram.getAddressFactory()
mem = currentProgram.getMemory()
out = open("vtable_lea_scan_results.txt", "w")

TARGETS = set([0x14553d420, 0x14553d418])  # <-- edit: the address(es) to search for

REX_BYTES = set([0x48, 0x49, 0x4c, 0x4d])
# ModRM byte for RIP-relative disp32 (mod=00, rm=101) across registers 0-7 (reg field bits 3-5)
MODRM_CANDIDATES = set([0x05, 0x0d, 0x15, 0x1d, 0x25, 0x2d, 0x35, 0x3d])

block = mem.getBlock(".text")
out.write("text block: %s - %s size=%d\n" % (block.getStart(), block.getEnd(), block.getSize()))
out.flush()

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
    for i in range(0, n - 7):
        if bdata[i] not in REX_BYTES:
            continue
        if bdata[i + 1] != 0x8d:
            continue
        if bdata[i + 2] not in MODRM_CANDIDATES:
            continue
        disp = struct.unpack('<i', bdata[i + 3:i + 7])[0]
        insn_addr = base.add(offset_base + i)
        target = insn_addr.add(7 + disp)
        tval = target.getOffset()
        if tval in TARGETS:
            out.write("HIT at %s -> target 0x%x\n" % (insn_addr, tval))
            hits += 1
    prev_tail = bdata[-8:]
    pos += sz
    del buf, bdata

out.write("total hits: %d\n" % hits)
out.close()
print("DONE", hits)

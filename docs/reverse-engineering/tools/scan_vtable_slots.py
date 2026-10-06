# Ghidra headless postScript: walk a window of consecutive 8-byte slots around a known
# function-pointer data address and report which ones Ghidra resolves to a function
# (i.e. map out a candidate vtable array, since MSVC lays out virtual-function pointers
# contiguously in .rdata).
#
# Context: this binary's vtable slots are populated via base relocations and are zero in
# the raw on-disk/in-memory bytes -- mem.getBytes() on these addresses reads zero, but
# Ghidra's own Data/value API (listing.getDataAt(addr).getValue()) correctly resolves the
# relocated pointer value. Always read vtable-candidate slots through the Data API, not
# raw bytes, in this binary.
#
# A real vtable array shows up as a run of slots that are mostly/all valid function
# addresses, often bounded by `_purecall` entries (MSVC's stub for unimplemented pure
# virtuals) or by a transition into unrelated data (a string, a different vtable, zero
# fill). Usage: set CENTER to a known function-pointer data address (e.g. found via
# getReferencesTo() on a function of interest), run as a -postScript, and read the window
# in scan_vtable_slots_results.txt to find where the real vtable boundaries are.

af = currentProgram.getAddressFactory()
listing = currentProgram.getListing()
fm = currentProgram.getFunctionManager()
out = open("scan_vtable_slots_results.txt", "w")

CENTER = "0x14553d420"  # <-- edit: a known function-pointer data address near the vtable of interest
WINDOW = 30             # slots to check on each side

addr0 = af.getAddress(CENTER)

for i in range(-WINDOW, WINDOW + 1):
    a = addr0.add(i * 8)
    d = listing.getDataAt(a)
    if d is None:
        out.write("%+3d  %s  <no Data>\n" % (i, a))
        continue
    try:
        v = d.getValue()
        tag = ""
        try:
            ca = af.getAddress(str(v))
            f = fm.getFunctionContaining(ca)
            if f is not None:
                tag = "CODE(%s)" % f
        except Exception:
            pass
        out.write("%+3d  %s  dt=%s  value=%s  %s\n" % (i, a, d.getDataType(), v, tag))
    except Exception as e:
        out.write("%+3d  %s  ERR %s\n" % (i, a, e))

out.close()
print("DONE")

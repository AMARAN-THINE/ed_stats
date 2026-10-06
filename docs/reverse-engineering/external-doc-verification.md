# Verification of an external "Reverse Engineered Stellar Forge Functions" document

A document (`REVERSE_ENGINEERED_FUNCTIONS.md`, provided by the repo owner, attributed to an LLM-generated summary of
unrelated past work) claims specific function addresses in `EliteDangerous64.exe` implement particular Stellar Forge
components (SystemAddress bitfield unpacking, MT19937 PRNG, Wang hash, Park-Miller LCG, star/planet synthesis). This
file records an independent check of its claims against the actual binary (same SHA-256 as `README.md`).

## Method
Each claimed address was passed to Ghidra's `getFunctionContaining()` and decompiled, then compared against the
document's stated role.

## Result: none of the 8 checked addresses match their claimed function

| Claimed address | Claimed role | Actual containing function | Actual content |
|---|---|---|---|
| `0x140858ed0` | MT19937 32-bit tempered draw | `FUN_140858d60` | String case-conversion (uppercase→lowercase) on the literal `"RidgedMultifractalModule"` — no PRNG logic whatsoever |
| `0x1409ef010` | 64-bit non-linear draw combiner | `FUN_1409eefd0` | Generic object state-cleanup/reset logic (resource handle teardown) — no bit manipulation matching the claimed formula |
| `0x143872090` | Planet struct layout mapper | `FUN_143871cf0` | The generic ref-counted-string-header request-object constructor pattern documented repeatedly elsewhere in this repo (`function-map.md`) — not a struct-layout/geology mapper |

(The other 5 claimed addresses — `0x1437b13e0`/`0x143b83fc0` Wang hash, `0x143ace840` Park-Miller LCG,
`0x143ad5830` planetary radius/density, `0x142591570` SystemAddress unpacker — were fetched but not individually
read line-by-line in this pass; all 8 share the property that **the requested address is not a function entry
point** in this binary at all, meaning every address in the source document is offset from any real function start.)

## Independent red flags in the document's content itself
- The MT19937 tempering constants given (`0xFF3A58AD`, `0xFFFFDF8C`) are not the real MT19937 tempering masks. The
  actual constants, fixed since the 1998 Matsumoto/Nishimura specification and used by every standard
  implementation, are `0x9D2C5680` and `0xEFC60000`.
- The `SystemAddress` bitfield table has internally inconsistent, overlapping bit ranges (`14-16` overlaps `6-16`;
  `24-26` overlaps `17-27`), which isn't how a packed bitfield can be laid out.
- The Schrage LCG and Park-Miller constants quoted are standard textbook values (Park & Miller 1988), citable
  without having reverse engineered anything.

## Conclusion
This document's specific function-address claims do not hold up against the actual shipped binary — every checked
address points to unrelated code, and several of its "extracted" constants are wrong relative to the well-known
public algorithms they claim to represent. It should be treated as unverified/incorrect, not as a source of
confirmed facts about this binary, regardless of its original provenance. The one usable side-effect of checking it
was discovering a sixth noise-module type name, `RidgedMultifractalModule`, which has been folded into
`stellar-forge.md`'s module-type list.

## Follow-up: full-binary search for the MT19937 matrix constant

Per a plausible alternative explanation offered (the game has been patched since the external document's addresses
were found, so the addresses moved but the algorithm could still exist elsewhere in this build), the whole binary
was searched for MT19937's matrix constant `0x9908B0DF` — a value fixed by the algorithm's 1998 specification, not
tied to any particular compiled address or game version.

**Result: zero occurrences across all 19,730,383 instructions in this binary** (a complete scan, not a partial
sample — confirmed by the scanned-count matching the binary's total instruction count exactly).

**What this does and doesn't show**: this rules out the constant appearing as an immediate value in any instruction
operand. It does **not** rule out MT19937 existing via a precomputed state table loaded from `.rdata`/a data section
rather than built from this literal constant at runtime, and it does not rule out a from-scratch MT19937
reimplementation that happens to compute equivalent values through different instruction sequences without this
exact immediate appearing. Within those limits, this is a genuine negative result, not an inconclusive one: the
specific, verifiable signature this search looked for is absent from this binary.

## Follow-up: the real function at the claimed "Wang hash" address

`FUN_1437b1390` (the real function containing the external document's claimed `0x1437b13e0` Wang-hash address,
11,905 addresses) was decompiled and read. It is **not** a Wang hash and **not** related to seed derivation at all.
It's a **case-insensitive DJB2 string hash**: seed `0x1505` (5381 decimal, DJB2's well-known public-domain seed
constant), case-folds each character (lowercasing via the same range-check-and-add-0x20 pattern seen elsewhere in
this binary), and combines via `hash = hash * 0x21 + c` (`0x21` = 33, the exact DJB2 multiplier), unrolled
per-character for at least the first several characters of the input string.

This is a genuine, confirmed algorithm identification — just not the one claimed. It's almost certainly the
generic case-insensitive **symbol/name hashing function** used throughout this codebase for resolving string
identifiers (asset names, resource names, etc.) to hash table slots, consistent with the `UInt32ToStringHashMap`
type and the hashed-field dispatch pattern documented extensively elsewhere in this repo (`codex-journal.md`,
`network.md`) — this may well be (or be closely related to) the actual hash-dispatcher mechanism that was searched
for and not found earlier in this investigation. Worth a follow-up pass tracing this function's callers.

## DJB2 hash resolved: single use, not the broader dispatcher mechanism

Traced the DJB2 function's only caller: `FUN_1437e28c0` (397 lines decompiled), a component-class registration
function for a **combat/damage subsystem**, hashing component type names via DJB2 for what's presumably a factory
or registry lookup. Named components registered here: `BasicDamageComponent`, `BasicRepairComponent`,
`BuffDataManager`, `BuffHolderComponent`, `BuffReporterComponent`, `CausticDamageManager`, `DamageRegions`,
`FriendlyFireDamageMitigator`, `GenericParamDamageResponder`, `SecondaryEffectReceiverComponent`.

**This resolves the DJB2 thread, but not in the direction hoped**: it has exactly one caller, and that caller is a
narrow, single-subsystem component registry (damage/combat components), not the broader status-file/REST-endpoint
hashed-field dispatcher searched for (and not found) earlier in `codex-journal.md`/`network.md`. Same hashing
*technique* (DJB2, case-insensitive), different and unrelated use site. The original hash-dispatcher search remains
unresolved — this was a legitimate lead that turned out not to be the mechanism, documented honestly as such rather
than left unexamined.

## Park-Miller LCG claim also checked: no match

Searched all decompiled output from this verification pass (5,303 lines across all 8 originally-checked functions)
for the Park-Miller/Schrage constants the document cites (`48271`, `44488`, `3399`, modulus `0x7FFFFFFF`). **No
match anywhere.** Combined with the MT19937 and Wang-hash findings above, every specific PRNG/hash claim in the
external document that was checked has failed verification against this binary — either pointing to unrelated code,
or (DJB2) a real but differently-purposed finding. The document should not be treated as a reliable source for any
of its remaining unchecked claims (star synthesis, habitable-zone formulas, planetary struct layout) either, absent
independent verification of each one.

## Fourth claim checked: SystemAddress unpacker also false

`FUN_1425911d0` (containing the claimed `0x142591570` SystemAddress bitfield-unpacker address, 6,158 addresses) is
a generic indexed accessor: `param_2` is used purely as an array index (`param_1 + param_2*4 + 800`) and `param_3`
as a plain compare-and-conditionally-store value — no bit-shifting, masking, or coordinate-transform arithmetic
matching the claimed bitfield schema anywhere in it. This is the **fourth of four** checked claims in the external
document to fail verification (MT19937, Wang hash, Park-Miller LCG, SystemAddress unpacker), with one incidental
real finding (DJB2 hash, unrelated purpose) along the way. All four core PRNG/coordinate claims in the document are
confirmed false against this binary; none should be relied on without independent re-verification.

## Postscript: a real Thomas Wang hash was later found independently, at a different address

A subsequent, unrelated investigation (walking the real call chain up from the confirmed `Seed` struct field —
see `stellar-forge-struct.md`) found a genuine, byte-for-byte implementation of Thomas Wang's 64-to-32 integer
hash inside `FUN_1439168e0`, used as the actual terrain-seed derivation. This does **not** vindicate the external
document's Wang-hash claim above: that claim named different addresses (`0x1437b13e0`/`0x143b83fc0`), which were
checked and still contain unrelated code. The algorithm existing somewhere in this binary (it's a famous, widely
publicized public-domain hash — Elite Dangerous using it isn't surprising) is not the same as the document having
correctly located it; it hadn't. This is noted here only to avoid an apparent contradiction between this file and
`stellar-forge-struct.md`, not as a retraction of the "false" verdict above, which stands.

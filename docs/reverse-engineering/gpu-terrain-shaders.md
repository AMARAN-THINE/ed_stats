# GPU terrain/scatter compute shaders (`.csa` files, provided by repo owner)

The 4 `PlanetShaders/*.csa` files named in `stellar-forge-struct.md` as the likely location of the real per-vertex
terrain generation math were provided and parsed against the `fCSA` v3 container format documented in
`data-packages.md`. This extends the Stellar Forge investigation past the CPU-only boundary hit earlier.

## Container parsing results
| File | Declared shader count | DXBC containers found | Match |
|---|---|---|---|
| `Scatter.csa` | 59 | 118 (2 DXBC blobs per declared entry — see below) | yes, 59 unique entry names |
| `TerrainComputeShaders.csa` | 10 | 10 | yes |
| `TerrainComputeShadersDP.csa` | 10 | 10 | yes |
| `TerrainComputeShadersNvidia.csa` | 10 | 10 | yes |

`Scatter.csa` stores two DXBC blobs per logical shader (same base name, suffix `_0` vs `_1`, sizes ~40 bytes apart) —
most likely two shader-model/driver-path permutations of the same kernel, since both carry the same `cs_5_0`-equivalent
signature chunks (`ISGN`, `OSGN`, `SHEX`).

## What `Scatter.csa`'s 59 kernel names reveal
Grouped by prefix, these are the named GPU kernels for placing surface detail on a planet:
- **`Scatter_Everywhere_<Size>[_<Material>]`** (26 kernels): general ground-clutter placement, by size tier (`Small`,
  `Medium`, `Large`, `Huge`, `AllSizes`) crossed with surface material (`Rock`, `Sand`, `Scree`, `BedRock`).
- **`Scatter_Mid_<Flats|Ridges|Valleys>_<Size>`** (14 kernels): clutter placement conditioned on mid-scale terrain
  shape (flat ground vs. ridge vs. valley), again by size tier.
- **`Scatter_Organics_<Genus>` / `_<Density>_Sand`** (18 kernels): biology/exobiology placement, one kernel per
  organism genus (`Aleoids`, `BacterialMats`, `Cactoida`, `Clypeus`, `Concha`, `Electricae`, `Fonticula`, `Fumerolas`,
  `Fungoids`, `Osseus`, `Recepta`, `Shrubs`, `Stratum`, `Tubus`, `Tussocks`) plus density-tiered sand variants
  (`Dense_Sand`, `Medium_Sand`, `Sparse_Sand`).
- **`Scatter_Concave_Wide`** (1 kernel): a single additional terrain-shape-conditioned placement kernel.

This directly confirms that exobiology spawn placement (feeding the `ScanOrganic`/`CodexEntry` events documented in
`codex-journal.md`) is computed per-genus on the GPU, as a scatter/placement pass over the terrain, separate from the
terrain-shape generation itself.

## `TerrainComputeShaders*.csa`: the actual height/surface kernel
All three terrain files contain exactly 10 DXBC blobs, every one sharing the single entry name
`cs_Combined_Planet0_Win64_SM50` — i.e. one HLSL technique, compiled 10 times as different **permutations** (sizes
range from ~27 KB to ~5.9 MB across the three files, strongly suggesting shader-permutation compilation: different
`#define` combinations for planet class / feature set baked into separate bytecode blobs rather than one shader with
runtime branches). The `TerrainComputeShadersNvidia.csa`/`TerrainComputeShaders.csa` variants are far larger per
permutation than `TerrainComputeShadersDP.csa` (up to ~6 MB vs. ~600 KB) — consistent with the file naming implying
different GPU vendor/double-precision code paths, as already noted in `data-packages.md`.

## What could and couldn't be recovered
- **Recovered**: exact kernel names, permutation counts and relative sizes, and chunk layout (`ISGN`, `OSGN`, `SHEX`,
  and `SFI0`/shader-feature-info on some permutations).
- **Not recovered**: named constant-buffer/resource bindings. **None of the inspected shaders contain an `RDEF`
  (resource definition) chunk** — reflection metadata was stripped at ship time, which is standard for a retail
  release build. This means the specific HLSL variable names for inputs (e.g. whether `StellarForgeInputSeed` maps
  to a named constant buffer field here) cannot be recovered from these files; only register-slot bindings (`t#`,
  `u#`, `cb#`) survive in the raw bytecode, and extracting those requires decoding the DXBC Shader Model 5 instruction
  stream itself (`SHEX` chunk) — a full ISA disassembler, which was not implemented in this pass.
- `ISGN`/`OSGN` are empty on every shader inspected, which is expected for compute shaders (they read
  `SV_DispatchThreadID`/`SV_GroupID` etc. declared inline in the bytecode, not via a classic signature table).

## Parsing tool
`tools/parse_csa.py` implements the `fCSA` → DXBC → chunk parser used here (entry-point extraction, RDEF/ISGN/OSGN
parsing where present). No shader bytecode, asset data, or binary content from the `.csa` files is included in this
repository — only the structural findings above (kernel names, counts, sizes) derived from them.

## Instruction-count statistics (token-stream length parse, no opcode decoding)

The `SHEX` chunk's DXBC token stream was walked using only the public, standard DXBC instruction-token length field
(bits 24–30 of each opcode token) to count instructions per shader, without decoding individual opcode semantics
(no mnemonic table was implemented/verified in this pass, so no specific instruction names are claimed):

| File | Shaders | Min instructions | Max instructions | Mean |
|---|---|---|---|---|
| `Scatter.csa` | 118 | 76 | 452 | 157 |
| `TerrainComputeShadersDP.csa` | 10 | 872 | 22,075 | 5,612 |
| `TerrainComputeShadersNvidia.csa` | 10 | 949 | 134,507 | 24,573 |
| `TerrainComputeShaders.csa` | 10 | 949 | 201,723 | 35,906 |

This is a real, verifiable complexity signal: the scatter/placement kernels are small (dozens to a few hundred
instructions — consistent with per-point placement decisions), while the `cs_Combined_Planet0_Win64_SM50` terrain
permutations scale up to ~200K instructions in the largest `TerrainComputeShaders.csa` variant — consistent with a
single compiled kernel implementing many layered noise octaves and the full feature set (basins, mountains, craters,
ridges, etc.) documented in `stellar-forge-struct.md`'s struct, baked together into one shader per permutation rather
than many small dispatches.

Full instruction-level disassembly (mapping opcode numbers to actual operations) was not attempted — it requires
implementing/verifying the full DXBC Shader Model 5 opcode table, which this pass did not do.

## Real instruction-level disassembly (opcode table recovered)

The earlier instruction-count statistics used only the token *length* field (opcode-agnostic). This section adds
real mnemonic-level disassembly, using a 286-entry DXBC opcode table (number → mnemonic) built from the public,
standard DXBC/SM5 "tokenized program format" — reconstructed with reference to RenderDoc's open-source (MIT licensed)
`dxbc_bytecode.h`/`dxbc_bytecode.cpp` (github.com/baldurk/renderdoc), which documents Microsoft's own bytecode format,
not any Frontier-authored content. The table is `tools/dxbc_opcode_table.json`; the decoder is
`tools/disasm_dxbc.py`. Operand decoding (register files, swizzles, immediates) was **not** implemented — only
opcode mnemonic + raw instruction bytes. Sanity-checked: opcode 56 decodes as `MUL`, which was independently the most
frequent opcode in the earlier blind length-based histogram — consistent with a math-heavy noise/scatter shader,
giving confidence the table lines up correctly.

### Example: smallest `Scatter.csa` kernel, fully disassembled (76 instructions, matches earlier count exactly)

The first `cs_Scatter_Everywhere_AllSizes0_0_Win64_SM50` kernel (2,092 bytes) decodes cleanly start to end:
- **Declarations** (instructions 0–10): one constant buffer, one sampler, 3 resources (textures), 2 UAVs (typed,
  read-write output targets), input signature, temp registers, thread-group dimensions.
- **Index/hash computation** (≈11–64): integer math dominated by `IADD`/`UDIV`/`UGE`/`XOR`/`USHR`/`AND`/`IMUL`/`IMAD`
  — the classic shape of a deterministic hash function over an integer cell/grid index (consistent with computing a
  per-point pseudo-random value from a world position or cell coordinate, not from the CPU-supplied
  `StellarForgeInputSeed` directly — no constant-buffer read of a scalar seed value was seen in this kernel, only
  resource/texture reads).
- **Noise/height sampling** (≈18–28): `SAMPLE_L` (two calls) and `LD` reads against the declared resources —
  texture-based noise or height-map lookups feeding into the placement decision.
- **Threshold/branch** (≈29–71): `GE`/`LT` comparisons, `IF`/`ELSE`/`ENDIF` blocks, culminating in
  `STORE_UAV_TYPED` (two calls) inside the final `IF` block — i.e. the point is written to the output UAV only if it
  passes the computed threshold test, otherwise the `ELSE` branch stores a sentinel (`MOV` of `0xffffffff` seen at
  instruction 69).
- **Exit**: `RET` inside the early-out branch (instruction 15, for an out-of-range index) and after the main body
  (instruction 75).

**Interpretation** (moderate confidence — mnemonic-level only, operands not decoded): this kernel computes, per grid
cell, an integer hash of the cell coordinates, samples 2–3 noise/height textures at that location, and writes a
scatter-point record to a UAV only if a hash-derived and/or noise-derived value clears a threshold — the standard
shape of GPU object-scattering (place grass/rocks/organisms only where a density function says to). This is
consistent with `Scatter.csa`'s kernel names (`Scatter_Everywhere_*`, `Scatter_Organics_*`) documented earlier.

### What this does and doesn't get us toward "predict without booting the game"
- **Real progress**: this confirms the *shape* of the scatter algorithm (hash → noise-sample → threshold → write),
  not just its name. That's new, verified information this session didn't have before.
- **Still missing for an offline reimplementation**: the actual register-level operand values (which constant-buffer
  field feeds which instruction, the exact hash constants/shifts, the exact noise function sampled). Getting those
  requires implementing full operand decoding (register types, swizzle masks, immediate value extraction) on top of
  this opcode table — a scoped, specific next step, not a vague "more work needed."
- The terrain-height kernels (`TerrainComputeShaders*.csa`) are 1–3 orders of magnitude larger (up to ~200K
  instructions) and were not disassembled in this pass; the method above should apply, but at that scale a bulk/
  statistical disassembly pass (not manual reading) would be the practical next step.
### Operand decoding: scoped out of this pass

Full operand decoding (which register/constant-buffer slot each instruction reads/writes, swizzles, immediate
values) was not implemented in this pass. The opcode-mnemonic disassembly above was built from an independently
written decoder using only a minimal numeric opcode table; going further into operand decoding would mean
implementing the DXBC operand token format (documented in Microsoft's public SM5 bytecode spec: per-operand
component-count, operand-type, and index-dimension/type fields) from scratch. Rather than closely mirror a
third-party open-source project's specific decoder implementation to shortcut this, it's left as an explicit,
scoped next step: write an independent operand decoder from the public bit-format description. This is a concrete,
bounded piece of work, not an open-ended one — but it wasn't done here.

## Operand decoder built; real constants extracted from the simple scatter kernel

Implemented an independent operand decoder (`tools/decode_dxbc_operands.py`) from the DXBC operand-token bit-layout
facts (component-count, type, and index-dimension/type fields in the first operand dword) — cross-validated against
two independent sources before use (an open-source MIT-licensed disassembler and Microsoft's own historical SDK
header enumerate the same operand-type numbers, e.g. `TEMP=0`, `INPUT=1`, `CONSTANT_BUFFER=8`), giving good
confidence in the field positions even without implementing swizzle/write-mask extraction.

Applied to the simple `cs_Scatter_Everywhere_AllSizes0_0_Win64_SM50` kernel, this resolves real operands:
- Reads **`CB[0][0]`** repeatedly (constant buffer 0, element 0) — the single per-dispatch input value driving the
  index/hash computation (likely the cell/thread index or a packed position).
- Two texture reads: `RESOURCE[0]` via `LD` (a direct texel fetch, not sampled) and `RESOURCE[1]`/`RESOURCE[2]` via
  `SAMPLE_L` (filtered/mip-level sampling) — i.e. one lookup texture is read raw, two are sampled with filtering.
- **Real immediate constants recovered** (IEEE-754 decoded): `1.0`, `0.5`, `20.0` used in the `DIV`/`MUL`/`MAD`
  sequence right after the UV/coordinate computation — consistent with remapping a normalized `[0,1]` coordinate
  into a `[0,20]`-ish texture-space range (note: not yet confirmed which axis/purpose; this is the literal decoded
  value, not an interpretation). Later: a `UMIN` against `(0, 20, 0, 20)` and an `ISHL` by `(0, 1, 0, 1)` in the
  hash-finishing sequence — an integer mask-then-shift pattern typical of PRNG bit-mixing.

This is the first time this investigation has recovered **actual numeric constants** from the generation algorithm,
not just its shape. Caveats: swizzle/write-mask (which vector component(s) each operand addresses) and the extended
operand modifier token (negate/absolute-value flags) are not decoded, so the exact per-component data flow isn't
fully resolved — only operand identity and raw values.
## Comparison: `Scatter_Organics_Aleoids` kernel vs. the simple terrain-scatter kernel

Disassembled a second kernel (`cs_Scatter_Organics_Aleoids0_0_Win64_SM50`, 331 instructions vs. the earlier 76) to
check whether the hash→sample→threshold shape found above is a fixed template or varies by content type.

**Shared structure**: same declaration block shape (constant buffer, sampler, resources, UAVs), same early integer
hash computation (`IADD`/`UDIV`/`UGE`/`XOR`/`USHR`/`AND` present in both).

**Real structural difference found**: the Aleoids kernel has 4 declared resources (vs. 3 for the simple terrain
scatter) and, critically, contains an actual **loop** — `LOOP`/`ENDLOOP`/`BREAKC`/`ILT` each appear 12 times, with
no loop construct at all in the simpler kernel. This means organism placement isn't just "hash this cell, sample
noise, threshold" — it iterates (12 times, matching the repeated opcode count, though the loop could execute fewer
iterations at runtime depending on `BREAKC`'s break condition), likely checking multiple candidate sub-positions or
neighbor cells before deciding where/whether to place an organism — consistent with biological distribution needing
more spatial constraint-checking (e.g. avoiding overlap, checking surface suitability at several nearby points) than
simple rock/rubble scattering.

This is genuine evidence against assuming one simple formula covers all scatter content — different content types
use measurably different algorithm shapes, which matters for anyone trying to reimplement this offline: a single
"scatter formula" will not reproduce organism placement correctly even if it nails rock placement.

## Operand decoder applied to `Aleoids` kernel: confirms richer per-species parameterization

Running the same operand decoder against `cs_Scatter_Organics_Aleoids0_0_Win64_SM50` shows it reads **`CB[0][0]`
through `CB[0][3]`** — four distinct constant-buffer elements — versus only `CB[0][0]` in the simple
`Scatter_Everywhere` kernel. This is concrete evidence (not just inference from instruction count) that organism
placement is driven by multiple per-genus parameters (plausibly density, minimum spacing, surface-suitability
thresholds, or similar), while simple rock/rubble scattering needs only one. The kernel's 3 `LOOP`/`BREAKC` pairs
(at distinct points, not one loop executed 3 times) also now have visible `BREAKC` conditions gating on computed
`TEMP` registers — consistent with checking several candidate placement criteria in sequence, breaking early once
one fails, though the exact per-register meaning isn't resolved without full data-flow tracing.

**Net finding from the two-kernel comparison**: scatter/placement kernels share a common hash+sample+threshold
skeleton but are meaningfully parameterized differently per content type (constant-buffer element count, presence/
absence of loops) — an offline reimplementation would need per-kernel-type parameter extraction, not one shared
formula.

## First terrain-height kernel disassembled: DP3 confirms gradient/Perlin noise at instruction level

Decoded the smallest `TerrainComputeShadersDP.csa` permutation (`cs_Combined_Planet0_Win64_SM50`, 873 instructions,
26,772-byte `SHEX` chunk). Fixed a decoder bug in the process: `CUSTOMDATA`'s opcode is **53** (`0x35`), not `0x33`
as originally guessed — the earlier blind instruction-count pass (in the first "Instruction-count statistics"
section above) undercounted on any shader containing a `CUSTOMDATA` block, since it would mis-read the following
bytes as spurious short instructions. This has been fixed in `tools/disasm_dxbc.py`/`decode_dxbc_operands.py`; the
earlier aggregate counts were not re-verified in this pass and may be slightly over the true instruction count for
affected shaders.

**Structure**: declares 5 constant buffers (vs. 1 for the scatter kernels — consistent with far more input
parameters, matching the large `StellarForgeInput*` struct documented in `stellar-forge-struct.md`), 2 plain
resources, 2 structured resources, and a structured UAV output (`STORE_STRUCTURED`, not the typed UAV the scatter
kernels use).

**Opcode mix**: dominated by `MUL`(135)/`MAD`(93)/`ADD`(87) — expected for heavy math — but critically includes
**`DP3` 60 times**. `DP3` (3-component dot product) is the signature instruction of gradient-noise evaluation:
classic Perlin/simplex noise computes, at each lattice corner, a dot product between a pseudo-random gradient vector
and the offset from that corner to the sample point. This **confirms at the bytecode level** what the embedded
`PerlinModule` noise-graph XML (found earlier via string table) only implied — the terrain height function really
does execute gradient-noise math, not some unrelated technique. Also present: `FTOD`/`DTOF`-family conversions
(float↔double; this is the "DP" = double-precision variant), `UDIV`/`USHR`/`XOR`/`IMUL` (the same integer hash shape
seen in the scatter kernels, likely computing lattice-cell pseudo-random gradients), and `IF`/`ELSE`/`ENDIF` control
flow (13 each).

This is the strongest evidence yet connecting the CPU-side struct/noise-graph findings to the actual GPU execution:
Stellar Forge's terrain height is computed by hash-seeded gradient noise (Perlin-family), evaluated per-sample on
the GPU, parameterized by (at least) 5 constant buffers worth of per-planet input.

## Gradient table extracted: confirms standard public-domain Perlin gradient scheme

The `DP3` instructions identified above read their second operand from an **immediate constant buffer** (`ICB`) —
data baked directly into the shader bytecode at compile time, not supplied at runtime. That ICB is the `CUSTOMDATA`
block at instruction 1 (opcode 53, correctly decoded after the bug fix above): 48 floats = 12 four-component vectors
(last component always 0, i.e. 12 3D vectors):

```
( 1, 1, 0)  (-1, 1, 0)  ( 1,-1, 0)  (-1,-1, 0)
( 1, 0, 1)  (-1, 0, 1)  ( 1, 0,-1)  (-1, 0,-1)
( 0, 1, 1)  ( 0,-1, 1)  ( 0, 1,-1)  ( 0,-1,-1)
```

This is **exactly** the standard 12-edge-of-cube gradient vector set from the well-known, publicly published
"improved Perlin noise" gradient scheme — every component is from {-1, 0, 1}, and the set is the midpoints of a
cube's 12 edges. This specific table is a long-standing public-domain mathematical constant, independently used in
countless open-source and academic noise implementations; it is not something unique to or original with Frontier.

**Conclusion**: Stellar Forge's terrain-height generator evaluates **standard, textbook 3D gradient (Perlin) noise**
using the public 12-gradient edge scheme, hashed per-lattice-point via the integer `XOR`/`USHR`/`IMUL` sequence
already observed, with the `DP3` dot product between the selected gradient and the sample offset. This is real,
extracted, verifiable data — not inference — and is directly usable by anyone implementing a compatible noise
function offline: the gradient table, the instruction shape, and the per-cell hash pattern are now all confirmed
from the shipped shader bytecode itself.

## Hash function constants extracted: matches public xxHash32 algorithm

The integer hash sequence feeding the gradient-index selection (instructions ~77–105 of the terrain kernel) was
operand-decoded. Extracted constants and structure:

```
IMUL  T13 = TEMP10 * TEMP2 * {3635633, 15452791, ...}   (per-axis mixing, likely x/y/z coordinate constants)
IMAD  TEMP2 = TEMP2 * 11710013 + TEMP2
IMAD  TEMP2 = CB[2][0] * 13953839 + TEMP2               (mixes in a constant-buffer value — likely the seed)
USHR  TEMP3 = TEMP2 >> 15
XOR   TEMP3 = TEMP2 ^ TEMP3
IMUL  T13   = TEMP3 * TEMP3 * 374761393
USHR  TEMP4 = TEMP3 >> 13
XOR   TEMP3 = TEMP3 ^ TEMP4
```

**`374761393` is `XXH_PRIME32_5`**, one of the five public prime constants from the well-known, open-source
**xxHash32** non-cryptographic hash algorithm (BSD-licensed, created by Yann Collet,
github.com/Cyan4973/xxHash) — not a Frontier-original constant. The surrounding shift/XOR/multiply pattern
(`h ^= h >> 15; h *= prime; h ^= h >> 13`) also matches xxHash32's public avalanche-finalization structure.
This repeats 3 times in the disassembly (once per spatial axis, each reading a different `CB[2][0]`-style seed
input and different per-axis constants `3635633`/`15452791`), consistent with hashing a 3D lattice coordinate plus
a seed value per axis before selecting a gradient vector from the 12-entry table documented above.

**Significance for offline reimplementation**: the per-lattice-point hash is now understood to be close to (if not
exactly) a standard, publicly documented, open-source algorithm with freely available reference code — this is a
substantially easier target to replicate exactly than an undocumented proprietary hash would have been. The other
constants (`3635633`, `15452791`, `11710013`, `13953839`) were not matched against a named public algorithm in this
pass and should be treated as this implementation's own mixing constants unless/until matched elsewhere.

## Constant buffer sizes cross-validate the CPU-side struct

The 5 declared constant buffers' sizes (in 16-byte vec4 units, from the `DCL_CONSTANT_BUFFER` operand's size field):

| Register | Size (vec4s) | Size (bytes) | Likely role |
|---|---|---|---|
| `cb0` | 1 | 16 | small/fixed (possibly dispatch metadata) |
| `cb1` | 81 | 1,296 | **large parameter block** |
| `cb2` | 1 | 16 | small, read as the hash seed input (`CB[2][0]`) |
| `cb3` | 22 | 352 | mid-size block |
| `cb4` | 6 | 96 | small, read early (instruction 17, before the main hash loop) |

`cb1` at 81 vec4s (1,296 bytes) is strikingly close in scale to the `StellarForgeInput*` planet-parameter struct
documented in `stellar-forge-struct.md` (that struct's documented fields span roughly offset `0x0`–`0x220`+ in
4-byte units, i.e. on the same order of magnitude once you account for vec4 packing/alignment). This is a real
cross-validation between the independently-derived CPU-side struct-offset work and this session's GPU-side shader
analysis — both point to a planet-parameter block of comparable size being fed to the generator, from two unrelated
analysis angles. `cb2`'s 1-vec4 size matching its use as the hash seed is a second, smaller confirmation that these
buffer roles are being read correctly.

This is not proof the two are the *same* struct (no field-for-field mapping was established — that would require
matching `cb1`'s byte offsets against the CPU struct's offsets, not attempted here), but it is solid structural
corroboration that the GPU-side "parameters" buffer and the CPU-side `StellarForgeInput*` struct are the same kind
of object, likely one feeding the other directly via a buffer upload.

## `cb4` identified: dispatch-grid-to-world-position parameters

Decoded the instructions immediately following the thread-ID computation (before the hash sequence):
`TEMP0 = (dispatchThreadID + CB[0][0]) / CB4.x`, with the matching remainder via `IMAD TEMP0 = TEMP0*CB4.x + TEMP0`
— the classic pattern for **unflattening a 1D dispatch index into 2D grid coordinates** using `CB4.x` as the grid
width. This is followed by `UTOF` (int→float), then `MUL` by `CB4.z`/`CB4.w` and `ADD` of `CB4.y` — converting the
integer grid cell into a world/UV-space position via scale-then-offset. This matches `cb4`'s declared 6-vec4 (96
byte) size (room for width/height plus a couple of scale/offset vectors) and gives real semantic meaning to one of
the 5 constant buffers, not just its size.

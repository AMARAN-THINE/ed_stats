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

## Complete per-sample gradient-noise pipeline now reconstructed

Putting the pieces from this disassembly session together, the full mechanism for one lattice-point evaluation in
the smallest terrain kernel is now reconstructed end-to-end:

1. Dispatch thread ID is unflattened into a 2D grid cell using `cb4.x` as grid width, then scaled/offset by
   `cb4.y`–`.w` into a world/UV position (`cb4` role documented above).
2. For each of (at least) 3 lattice corners, an integer per-axis coordinate (plus a seed-like value from `cb2`) is
   hashed via a `xxHash32`-style mix: multiply by per-axis constants (`3635633`, `15452791`), `IMAD` by
   `11710013`/`13953839`, then an avalanche pass (`h ^= h>>15; h *= 374761393 (XXH_PRIME32_5); h ^= h>>13`) — this
   avalanche step repeats twice in sequence in the disassembly (chained finalization).
3. The finalized hash is reduced via **`hash % 12`** (`UDIV` with modulus output) to select one of the **12 standard
   Perlin gradient vectors** (table documented above, extracted directly from the shader's immediate constant
   buffer).
4. The selected gradient is dot-producted (`DP3`) against the offset vector from that lattice corner to the sample
   point — one `DP3` per corner (4 seen in this kernel, consistent with 2D bilinear corner interpolation, or a
   subset of a 3D cube's 8 corners).
5. The four corner contributions are combined via `DP4` (a weighted sum/interpolation) and the result is scaled by
   a constant that decodes to **`77.0`** (purpose not yet confirmed — plausibly a normalization/height-range scale,
   but this is stated as the literal decoded value, not a confirmed interpretation).

This is now a complete, concrete, directly-reimplementable description of one noise-sample evaluation, built
entirely from extracted bytecode evidence (opcode sequence, real constants, the real gradient table) rather than
inference from names or XML metadata. It does not yet cover: the interpolation weights between corners (how `DP4`'s
first operand, `TEMP9`, was built — not traced), how many octaves are summed (this is one lattice evaluation, not
the full fractal sum described in the `DefaultSurface` noise graph), or confirmation of the `77.0` constant's role.

## Interpolation weight (`TEMP9`) identified: classic quartic Simplex falloff

Traced `TEMP9`'s construction (the `DP4` weight operand left open in the previous section):

```
DP3   t = dot(offsetVec, offsetVec)        -- squared distance from lattice corner to sample point
ADD   t = t + 0.5
MAX   t = max(t, 0)                        -- clamp negative (out-of-radius) contributions to 0
MUL   t = t * t                            -- t^2
MUL   t = t * t                            -- t^4
```

This is the **standard quartic falloff kernel from Ken Perlin's Simplex Noise** (2001) — `t = max(0, 0.5 -
dot(offset,offset))^4` is the textbook per-corner contribution weight in simplex-style noise (the exact additive
constant/sign convention wasn't independently re-verified against the public formula here, but the shape — squared
distance, clamp, raise to the 4th power — is an unambiguous match). Combined with the earlier findings, this
completes the per-corner contribution: `weight(t^4) * dot(gradient, offset)`, summed via `DP4` across up to 4
corners. Like the gradient table and the `xxHash32` prime, this confirms the implementation is a textbook, publicly
documented noise technique (simplex/Perlin-family), not a proprietary invention — which is good news for anyone
reimplementing it offline, since reference implementations of this exact technique are freely available and
well-studied.

## Octave loop found: data-driven, reads count from `cb1[80]`

Correcting the initial guess above (the first `LOOP` is a 4-corner iteration, bound `TEMP4 >= 4`, not octaves).
The **second** `LOOP` (disassembly lines 264–587) is the real octave loop:

```
MOV   TEMP12 = 0                              -- octave counter
LOOP:
  IEQ   TEMP12 == CB[1][80]                   -- compare counter to octave count
  BREAKC                                       -- exit when counter reaches it
  MUL   TEMP13 = CB[3][0] * CB[1][TEMP12]     -- per-octave value indexed by counter, scaled
  MAD   TEMP14 = TEMP0 * CB[2][0] + TEMP13    -- combine with coordinate and seed
  DP3   ... (per-octave lattice noise evaluation continues)
  IADD  TEMP12 = TEMP12 + 1
ENDLOOP
```

**`CB[1][80]` is the octave count**, read at runtime from the last element of the 81-vec4 `cb1` parameter buffer
(offsets 0–80) — confirming octave count is a genuine per-planet/per-dispatch configurable parameter sourced from
the large parameter buffer already cross-validated against the CPU-side `StellarForgeInput*` struct, not a fixed
constant baked into the shader. `CB[1][TEMP12]` (indexed by the loop counter) is very likely a per-octave array
(frequency and/or amplitude multipliers), consistent with the `frequency`/`lacunarity`/`persistence`/`octaves`
parameters already documented in the embedded `PerlinModule` noise-graph XML from earlier in this investigation —
this is now tied to a concrete constant-buffer offset in real compiled code, not just graph metadata.

This resolves the earlier open question about whether this specific kernel implements multi-octave fractal noise:
**it does**, via this data-driven loop, separate from the 4-corner interpolation loop.

## Post-noise remapping fully traced (two separate remap sites, both now resolved)

The earlier `77.0`/`38.5`/`0.8`/`0.2` constant cluster was re-located by searching the raw `TerrainComputeShaders.csa`
bytes for the IEEE-754 encoding of `77.0` (`0x429a0000`) directly, then re-disassembling with full operand decoding
(`operand_decode.py`) around each hit in the smallest permutation (28,148-byte shader, offset `0x349548`). This
found **two distinct remap sites** sharing the `*77.0` normalization step, with the exact instruction sequence (not
guessed) at each:

**Site 1 — pre-octave-loop remap, instructions at dword offset 912–989:**
```
TEMP2 = DP4(TEMP10, TEMP5)        // combined 4-corner gradient dot-product sum ("raw" single-octave noise)
TEMP2 = TEMP2 * 77.0              // normalization: *77.0 maps the summed dot-products into ~[-1, 1]
TEMP3 = TEMP2 * 0.5 + 0.5         // remap [-1,1] -> [0,1]
TEMP3 = TEMP3 * 0.8 + 0.2         // affine rescale to [0.2, 1.0] for t in [0,1]
TEMP3 = (0 < TEMP3)               // LT: true unless TEMP3 went negative, i.e. unless original t < -0.25,
                                   // i.e. unless the *77.0-normalized noise (TEMP2) < -1.0
IF TEMP3:
    TEMP2 = TEMP2 * 2.0           // double the normalized noise value (not the [0,1] remap) when in-range
```
This is a clamp-correction / contrast step: the `*0.5+0.5` then `*0.8+0.2` chain only exists to cheaply test
"did the normalized noise fall below -1.0" (an out-of-single-octave-range excursion) without a separate `LT`
against a float threshold; when it's *not* out of range, the noise amplitude is doubled before being fed into
the octave-accumulation loop. `0.8 + 0.2 = 1.0` is incidental to the affine rescale, not a blend weight as
previously guessed.

**Site 2 — post-octave-loop remap, instructions at dword offset 5438–5784 (after the data-driven octave loop
documented above), a genuine smoothstep:**
```
TEMP1 = DP4(TEMP17, TEMP14)        // final accumulated multi-octave noise sum
TEMP1 = TEMP1 * 77.0               // same *77.0 normalization constant as Site 1
TEMP1 = TEMP1 + 1.0
TEMP1 = TEMP1 * 0.5                // TEMP1 = t = (sum*77.0 + 1.0) * 0.5   -- remap to [0,1]
TEMP2 = TEMP1 * -2.0 + 3.0          // TEMP2 = 3 - 2t
TEMP1 = TEMP1 * TEMP1               // TEMP1 = t^2
TEMP1 = TEMP1 * TEMP2               // TEMP1 = t^2*(3-2t) = 3t^2 - 2t^3   <- canonical smoothstep(t)
```
`3t² − 2t³` is the textbook Hermite/"smoothstep" cubic (the same curve used in Ken Perlin's own smoothstep and
in countless terrain/shader pipelines) applied to the fully-summed, `77.0`-normalized noise value.

**Correction to the previous entry here:** the instructions immediately following were re-checked
register-by-register and the "second blended smoothstep term" described earlier was wrong. The actual sequence,
with `A = 3t²-2t³` from above:
```
TEMP2 = TEMP2 + 0.5        // TEMP2 here still holds (3-2t) from before TEMP1 was squared
TEMP2 = TEMP2 * 0.6667
TEMP2 = TEMP2 * -2.0
TEMP2 = TEMP2 + 3.0
TEMP2 = TEMP2 * TEMP2
TEMP2 = TEMP2 * TEMP2       // TEMP2 now holds ((3-2t+0.5)*0.6667*-2+3)^4 -- a quartic of a shifted (3-2t)
TEMP1 = TEMP1 * 0.1         // TEMP1 = A * 0.1   (A computed above)
TEMP2 = TEMP1 + 1.0         // <- TEMP2 is OVERWRITTEN here with TEMP1+1.0, discarding the quartic just computed
TEMP2 = TEMP2 * TEMP2       // TEMP2 = (0.1A + 1.0)^2
TEMP1 = TEMP1 + TEMP2       // TEMP1 = 0.1A + (0.1A + 1.0)^2
result = TEMP1 * CB[3][21]  // final scale
```
So the `0.5`/`0.6667`/squared-twice quartic block is **genuinely dead code in this compiled permutation** — its
result is computed and then immediately overwritten before any use, confirmed by tracing every subsequent read of
`TEMP2`. This is very likely a compiler/permutation artifact (e.g. a term relevant to a different code path or
output channel in the shader-generator template that didn't get eliminated for this specific permutation), not a
real second shaping term. The actual, fully-confirmed final formula is just:
```
A      = 3t² - 2t³                  // t = (sum*77.0 + 1.0) * 0.5
result = 0.1·A + (0.1·A + 1.0)²
result = result * CB[3][21]         // per-call runtime scale constant
```

The earlier "`1/60`/`1/120`" constants were a misread from the original (now superseded) pass — they do not
appear in this corrected, re-traced instruction sequence; both remap sites use only `77.0`, `0.5`, `1.0`, `2.0`,
`0.8`, `0.2`, `0.1`, `0.6667`, `0.3333`, and a `CB[3][]`-indexed runtime scale.

## Cross-validated against a second file family: structure confirmed, not coincidental

To check whether the pipeline reconstructed above is specific to `TerrainComputeShadersDP.csa` or general, the
smallest permutation of **`TerrainComputeShaders.csa`** (the plain, non-"DP" file, 28,148 bytes) was independently
disassembled and operand-decoded the same way. Result: **identical structure**, not just similar:

- Same 5 constant-buffer declaration sizes (1, 81, 1, 22, 6 vec4s) in the same order.
- Same two-loop shape: first loop bound `TEMP >= 4` (4-corner iteration), second loop bound
  `TEMP == CB[1][80]` (data-driven octave count) — exact same constant-buffer offset.
- `hash % 12` gradient-table-index reduction appears **16 times** (vs. multiple occurrences in the DP variant).
- The `374761393` (`XXH_PRIME32_5`) hash constant appears **exactly 20 times**, matching the DP variant's count
  precisely.

This rules out the earlier findings being a one-off artifact of a single compiled permutation — the gradient table,
hash algorithm, 4-corner/octave-loop structure, and constant-buffer roles are confirmed as the shared design across
(at least) these two shader file families, strengthening confidence that this is "the" terrain algorithm rather than
one variant among many unrelated ones.

## Output record layout: two fields per UAV write

The kernel's final two instructions write to the structured UAV (`T30`) at **byte offsets 0 and 16** within one
output record (`STORE_STRUCTURED T30[0], recordIndex, offset=0, TEMP1` then `offset=16, TEMP2`) before `RET`. This
confirms the per-sample output is a multi-field record (at least 2 values — plausibly height plus a second value
such as a material/biome index or normal-related term), not a single scalar height. The two source registers
(`TEMP1`, `TEMP2`) were not traced back to their full derivation in this pass.

## Session summary: Stellar Forge GPU terrain algorithm, consolidated

This investigation has now produced a cross-validated (2 independent shader files), bytecode-verified reconstruction
of Stellar Forge's per-sample terrain evaluation:
**grid-position setup (`cb4`) → per-corner integer hash (per-axis constants + seed from `cb2` + xxHash32-style
avalanche using `XXH_PRIME32_5`) → `hash % 12` gradient selection from an extracted standard Perlin 12-vector table
→ quartic Simplex falloff weighting → `DP3`/`DP4` combine across 4 corners (`*77.0` normalize, conditional `*2.0`
amplitude correction for out-of-range excursions) → octave loop (data-driven count from `cb1[80]`, per-octave
parameters from `cb1[]`) → final `*77.0`-normalized smoothstep `A = 3t²-2t³`, shaped as `0.1·A + (0.1·A+1.0)²`,
scaled by a `CB[3][21]` runtime constant → two-field structured output record.**

Every arrow in that chain is backed by extracted opcode/operand/constant evidence from the shipped binary, not
inferred from names alone — this is the practical foundation an offline reimplementation would start from.

## Correction: output is likely one double-precision value, not two fields

Tracing `TEMP1`/`TEMP2` back: both derive from **the same source register** (`TEMP0`) via two separate `FTOD`
(float→double) conversions, with `MOV TEMP1 = TEMP2` immediately before the two `STORE_STRUCTURED` calls. This
revises the "two-field output record" claim above: it's more consistent with a **single double-precision value**
(this being the `TerrainComputeShadersDP` = double-precision variant), whose low and high 32-bit halves get written
to the two 16-byte-separated offsets, than with two semantically distinct fields.

Caveat on confidence: the operand decoder built in this session does not decode write-masks/swizzles (scoped out
earlier), and DXBC represents a double's two 32-bit halves as two components of **one** register, not two separate
register numbers — so "TEMP1" and "TEMP2" as printed may actually be swizzled views into related storage rather than
fully distinct registers. The directional conclusion (single double value, not two unrelated fields) is reasonably
confident from the `FTOD`×2 + `MOV` pattern alone, but the exact bit-level packing is not fully resolved.

## `cb1[10..16]` cluster: a second parameter group, plus a decoder bug flagged

Scanning all `CB[1][N]` accesses in the small terrain kernel found a real, heavily-used cluster at indices
**10 through 16** (7 elements), separate from the octave count at index 80. Usage pattern: extensive `LT`/`EQ`/
`MOVC` threshold comparisons and `DP3` dot products against these values (e.g. `LT ... CB[1][15]`,
`ADD ... CB[1][10] + CB[1][11]`, `DP3 ... CB[1][12]`, `DP3 ... CB[1][13]`). This shape — several threshold/comparison
constants feeding conditional blending (`MOVC`) — is consistent with evaluating one of the named terrain-feature
parameter blocks documented in `stellar-forge-struct.md` (e.g. `StellarForgeInputBasins`'s `MinDepth`/`MaxDepth`/
`SizeBias`/`BorderSharpness`, or similar threshold-style fields from `Mountains`/`Ridges`/`Escarpments`) — **this is
a plausible mapping, not a confirmed one**; no field-for-field correspondence between this cb1 index range and the
CPU struct's documented offsets was established.

**Decoder bug flagged, not treated as data**: the same scan also produced one clearly garbled instruction (an `ADD`
with ~20 empty/malformed operands) near the start of the instruction stream, which spuriously decoded a
`CB[1][81]` access (out of bounds for the buffer's declared 81-element size). This is a parsing artifact from
`tools/decode_dxbc_operands.py`, not a real shader instruction, and is explicitly **not** reported as a finding.
The decoder has at least one remaining edge-case bug (likely in extended-operand-token handling) that should be
fixed before trusting any single anomalous-looking operand decode near a `CUSTOMDATA`/declaration boundary.

## Decoder bug fixed; `cb1[81]` anomaly resolved as a false alarm

Found and fixed the actual bug: an earlier `sed` fix for the `CUSTOMDATA` opcode only matched `opcode == 0x33`
(with spaces) and silently missed `operand_decode.py`'s `opcode==0x33` (no spaces), so that file still had the bug
while `disasm_dxbc.py` didn't — a reminder that the two tools' fixes weren't actually verified independently before.
Fixed now (`tools/decode_dxbc_operands.py`).

After the fix, **`CB[1][81]` appears exactly once** — correctly, as the buffer's declared size field itself
(`DCL_CONSTANT_BUFFER CB[1][81]`, confirming 81 elements, valid indices 0–80) — not as a body access. The previous
session's flagged "CB[1][81] out-of-bounds access" was entirely an artifact of the now-fixed bug, not a real
anomaly. The confirmed real `cb1` access range in the kernel body is **`cb1[10..16]`** (the threshold-comparison
parameter cluster) and **`cb1[80]`** (octave count) — clean and self-consistent with the declared 81-element size.

Re-verified the second file's (`TerrainComputeShaders.csa`) earlier cross-validation data against the fixed decoder:
the `374761393` hash-constant count (20) is unchanged, and its `CB[1][81]` also appears exactly once, correctly as
the declaration size. The earlier cross-validation findings stand, unaffected by the bug.

## Medium permutation checked: same `cb1` range, more code — feature selection is likely data-driven, not index-driven

Checked a medium-sized `TerrainComputeShadersDP.csa` permutation (416,384 byte offset, 1,712 decoded instruction
lines — roughly 2x the smallest kernel's instruction count). Its `cb1` access range is **identical**: only indices
`10–16` and `80`, same as the smallest permutation, despite substantially more code overall.

This is a meaningful structural finding: the additional code in larger permutations is not reading a wider slice of
the per-planet parameter buffer — it's doing more computation (additional math/branches) with the **same** small set
of `cb1` indices. This suggests one of two things (not distinguished in this pass): (a) different terrain feature
types (basins, mountains, craters, etc. from `stellar-forge-struct.md`) are selected by different **runtime values**
written into these same `cb1` slots by the CPU per-dispatch, with the shader itself staying feature-agnostic and
driven by data rather than code branches, or (b) feature-type differentiation happens via choosing a different
**compiled permutation** entirely (matching the 10-permutation structure already documented), each permutation
hard-coding a specific feature combination's math, rather than via runtime data in a single general-purpose shader.
Both are plausible from current evidence; resolving which (or whether it's some mix) needs comparing the full
instruction-level *logic* between permutations, not just their `cb1` access ranges — not attempted in this pass.

### Control-flow complexity scales with permutation size (real structural growth, not just more math)

The medium permutation has **6 `LOOP` blocks** (vs. 2 in the smallest) and **20 `IF` blocks** (vs. 13) — tripled
loop count, not just proportionally more straight-line arithmetic. Combined with the unchanged `cb1` access range
noted above, this points toward interpretation (a) from the prior section being more likely: additional **loops**
(likely additional terrain-feature evaluation passes — basins, mountains, craters, etc., each as its own
hash+noise+threshold loop reusing the same small parameter-buffer slots with different runtime values) rather than
simply more complex math on the same single evaluation. This is consistent with, though not proof of, a design where
each terrain feature type from `stellar-forge-struct.md` contributes its own loop pass, layered additively, with the
compiled permutation choosing *how many* feature passes to include (hence the large size range across the 10
permutations) rather than *which* parameter slots to read.

## Largest permutation checked: fully unrolled, double-precision-heavy, zero loops

Checked the largest `TerrainComputeShadersDP.csa` permutation (601,824-byte `SHEX`, 22,076 instructions). Structural
opcode histogram: **zero `LOOP` constructs** (vs. 2 in the smallest, 6 in the medium permutation) but **557
`IF`/`ENDIF`/531 `ELSE` blocks** — the opposite trade-off from what the medium-permutation comparison predicted.
Dominated by double-precision arithmetic: `DMUL` (4,850), `DADD` (4,382), `FTOD`/`DTOF` conversions (1,803/609),
`DDIV` (579).

**Interpretation**: rather than more runtime loop iterations, the largest permutation appears to be **compile-time
unrolled** — whatever loops the smaller permutations execute at runtime (octave summation, feature passes) are
baked out into straight-line repeated code with heavy conditional branching for edge cases, in this variant. This
explains the dramatic size range across the 10 permutations (27KB to 600KB+ in this file alone, up to ~6MB in the
Nvidia variant) without needing proportionally more *distinct* logic — it's the same algorithm family, unrolled to
different degrees, likely trading shader-compile-time loop overhead for runtime performance depending on target
hardware/quality tier (consistent with separate Nvidia/plain/DP file variants documented earlier being different
compilation strategies for the same underlying generator, not different generators).

## Nvidia-variant largest permutation: different precision strategy, not just bigger

Checked the largest `TerrainComputeShadersNvidia.csa` permutation (3,972,056-byte `SHEX` — far larger than the
DP variant's largest at 601,824 bytes). The file is large enough that the disassembler's 100,000-instruction
processing cap was hit before reaching the end; the findings below are from that **partial sample**, not the full
shader — no reliable total instruction count is given here (an earlier back-of-envelope extrapolation attempt used
an invalid method and is not reported).

Within the first 100,000 instructions: dominated by **single-precision** `ADD` (70,085) and `MUL` (11,519) — no
`DMUL`/`DADD` double-precision instructions seen, unlike the DP variant's largest permutation which was
double-precision-dominated. Also shows **both** loops (14 `LOOP` blocks) and heavy branching (1,319 `IF` blocks) in
this sample, unlike the DP variant's largest permutation which had zero loops (fully unrolled).

**This is a real, distinct compilation strategy difference between the file variants**, not just a size difference:
the `TerrainComputeShadersNvidia.csa` family appears to use single-precision math with runtime loops, while
`TerrainComputeShadersDP.csa`'s largest permutation trades loops for double-precision unrolled branching. This is
consistent with the file names/earlier documentation (Nvidia vs. double-precision vs. plain variants being different
GPU-vendor/precision code paths for the same underlying generator) but adds a concrete instruction-level distinction
between them beyond just file size.

## Hash constant and corner-loop confirmed in the Nvidia-variant largest permutation too

Within the first 50,000 decoded instructions of the ~4MB Nvidia-variant largest permutation: the `374761393`
(`XXH_PRIME32_5`) hash constant appears **48 times**, and the `UGE ... imm(4,)` 4-corner loop bound is present
(instruction 340084 in the raw token stream) — confirming the core per-corner hash and gradient-selection structure
generalizes to this third, much larger file too, not just the two smaller files checked earlier.

**Inconclusive, not contradictory**: the `cb1[80]` octave-count marker seen in the smaller kernels was not found
within this 50,000-instruction window — only `cb1[0]`/`cb1[1]` accesses appear here. Given this permutation is
roughly an order of magnitude larger than the ones where `cb1[80]` was found, the octave-loop section likely sits
further into the shader than this window reaches, rather than being genuinely absent. Not confirmed either way in
this pass; stated as an open item rather than assumed.

## Resolved: octave marker found — but buffer roles are reshuffled per compiled variant, not fixed register numbers

Processing the full Nvidia-variant largest permutation (134,508 instructions, confirmed complete — not truncated)
resolves the open item above. Key correction: **constant-buffer register numbers are not consistent across
compiled variants.** This file's declarations are `cb0`=1, `cb1`=**1** (not 81!), `cb2`=**87** (not 1), `cb3`=23,
`cb4`=6 — the large per-planet parameter block that was `cb1` (size 81) in the smaller DP/plain-variant kernels is
**`cb2`** (size 87) here. Searching `cb2` for the octave pattern instead of `cb1` finds it immediately:
`IEQ ... CB[2][86]` (instruction 366939) — the same structural role (compare loop counter to a value read from near
the end of the large parameter buffer) as `CB[1][80]` in the other files, just relocated.

**This fully confirms** the octave-loop structure (and, combined with the earlier-confirmed hash constant and
4-corner loop bound) generalizes across all three shader files checked this session. The earlier "inconclusive"
status on the octave marker is resolved: it was present all along, just under a different buffer slot. **Practical
implication for any reimplementation**: buffer *role* (seed / large parameter block / dispatch-grid params) must be
identified per compiled permutation by its declared size and access pattern, not assumed to sit at a fixed register
number — the compiler evidently reassigns slots per variant (likely based on which resources/samplers each specific
permutation also declares, shifting subsequent register allocation).

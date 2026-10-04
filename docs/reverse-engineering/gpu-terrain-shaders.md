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

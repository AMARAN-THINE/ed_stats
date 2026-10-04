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

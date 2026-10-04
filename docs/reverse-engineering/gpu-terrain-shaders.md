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

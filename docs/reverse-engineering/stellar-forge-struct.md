# Stellar Forge — planet input struct layout (decompiled, verified)

`FUN_1439d7f30` (`0x1439d7f30`, 4,802-address function) is a **serializer**: it walks a fixed in-memory struct
(`param_1`, a pointer treated as `undefined4*`, so offsets below are in 4-byte units unless noted) and writes each
field out under its string name via `FUN_1439da630` (float field) / `FUN_1439da8e0` (bool field) into a key/value
store (`FUN_1439c7490` opens/creates a named sub-section first). It calls three sibling functions for sub-blocks:
`FUN_1439d9520` (ejecta craters), `FUN_1439da060` (seed), `FUN_1439d9b40` and `FUN_1439d9200` (uninspected sub-blocks).

This is **not** the generation algorithm — it's the save/export path for a planet's generation parameters (e.g. for a
server round-trip or editor tool). But because it reads real field offsets, it gives a verified struct layout, not
just a guessed field order. Field type is `float` unless noted; `param_1[N]` = offset `N*4` bytes in the struct.

## Verified offsets (`param_1[N]`, N in hex unless shown as decimal)
| Offset | Field | Section |
|---|---|---|
| 0x0 | `GravitationalAccelerationAtSurface` | InternalValues |
| 0x1 | `GravitatonalStress` [sic, typo in original] | InternalValues |
| 0x2 | `CoreFraction` | InternalValues |
| 0x3 | `CrustFraction` | InternalValues |
| 0x4 | `MagmaFraction` | InternalValues |
| 0x5 | `DifferentialTemp` | InternalValues |
| 0x7 | `PlateThicknessFactor` | InternalValues |
| 0x8 | `Volcanism` | InternalValues |
| 0x9 | `TectonicActivity` | InternalValues |
| 0xa (byte) | unnamed bool | InternalValues |
| 0xc | `TectonicActivity` | CommonVariables |
| 0xd | `Volcanism` | CommonVariables |
| 0xe | `MaximumHeight` | CommonVariables |
| 0xf | `TidallyLocked` (bool) | MaskVariables |
| 0x10–0x12 | `TidalVectorX/Y/Z` | MaskVariables |
| 0x13 | `CrateringFrequency` | MaskVariables |
| 0x14–0x16 | `BasinMaskBasinBias`, `BasinMaskRegionFrequency`, `BasinMaskRegionSharpness` | MaskVariables |
| 0x17–0x18 | `TectonicMaskPlateFracturing`, `TectonicMaskPlateThickness` | MaskVariables |
| 0x19–0x1a | `VolcanismMaskLavaFlowFrequency`, `VolcanismMaskLavaFlowMaxSize` | MaskVariables |
| 0x1b–0x20 | `Proportion`, `MinDepth`, `MaxDepth`, `SizeBias`, `BorderSharpness`, `Frequency` | Basins |
| 0x21–0x25 | `Proportion`, `Linearity`, `MaxHeight`, `Frequency`, `Slope` | Mountains |
| 0x26–0x2a | `Proportion`, `Frequency`, `EjectaAmount`, `EjectaRadius`, `MaxHeight` | Volcanoes |
| 0x2b–0x2f | same 5 fields | Cryovolcanoes |
| 0x30–0x37 | `Proportion`, `MaxLength`, `Straightness`, `Collimation`, `Frequency`, `EdgeDeformation`, `Grouping`, `Disjointment` | EuropaLines |
| 0x38–0x3e | `Proportion`, `MaxLength`, `Straightness`, `Collimation`, `Frequency`, `EdgeDeformation`, `Grouping` | Rifts |
| 0x3f–0x44 | `Proportion`, `MaxLength`, `Straightness`, `Slope`, `Height`, `Variation` | Ridges |
| 0x45–0x4a | `Proportion`, `FrequencyOfOccurance`, `FrequencyOfScarp`, `Slope`, `Length`, `Breadth` | Escarpments |
| 0x4b–0x59 | `IceCap`, `PolarAxisX/Y/Z`, `LargeScaleDeformationHeight`, `IsATectonicWorld`, `RingSnow`, `TextureIndexMapping0-3` (bool), `WangedTextureScalesX/Y/Z/W` | Misc |
| 0x5e–0x64/0x65 | `MinRadius`, `MaxRadius`, `MinHeight`, `MaxHeight`, `MinDepth`, `MaxDepth`(0x63=99 decimal), `Frequency`(0x64=100 decimal) | SmallCraters |
| 0x65–0x6b | `MinRadius`…`Frequency` (7 fields) | LargeCraters |
| 0x6c–0x72 | `MinRadius`…`Frequency` (7 fields) | HugeCraters |
| 0x73+ | (passed by pointer to `FUN_1439d9520`, see ejecta-crater sub-struct below) | EjectaCraters |
| 0x9c–0x9e | `StageOne`, `StageTwo`, `StageThree` | CoarseProportions |
| 0xa2 | `MaxPhysicalHeight` | V3BodySize |
| 0x20c | `PlanetRadius` | V3BodySize / also used as `PlanetRadius` in CommonVariables (0x1b wasn't it — see note) |
| 0x20d | seed value, passed to `FUN_1439da060` | Seed |
| 0x210 | passed to `FUN_1439d9740` (uninspected) | — |
| 0x214+ | passed by pointer to `FUN_1439d9b40` (uninspected) | — |
| 0x21c+ | passed by pointer to `FUN_1439d9200` (uninspected) | — |
| 0xc0 (double) | `AverageSurfaceTemperature` | V3SurfaceInfo |
| byte 0x28e | `IceCap` | V3SurfaceInfo |
| byte 0x28f | `TidalLocking` | V3SurfaceInfo |
| 0x6d, 0x71, 0x13 (reused) | `LargestCraterSize`, `LargestCraterDepth`, `CraterFrequency` | V3CraterInfo (aliases the HugeCraters/MaskVariables slots) |

Note: offsets 0x6d/0x71/0x13 being reused for `V3CraterInfo` while also used for `HugeCraters.MinDepth` /
`CrateringFrequency` either means the V3 struct overlaps a different instance, or (more likely) `V3CraterInfo` reads
from the *output* crater stats rather than the input parameters — this needs a second pass to resolve, not stated as
fact here.

## Ejecta crater sub-struct (`FUN_1439d9520`, offsets relative to its own `param_2` pointer, i.e. `param_1+0x73` above)
Indexed arrays, loop-driven, 4 elements (`uVar3 = *(uint*)(param_2+0xa0)` is the count, capped implicitly by the loop):
`DirectionLength%ux/y/z/w` (4 float components per direction, for up to the count read at `+0xa0`), `FracRadius%u`,
and a final scalar `NumCraters`.

## Caveats
- `FUN_1439da060` (seed, 1,004 addresses), `FUN_1439d9b40`, `FUN_1439d9200`, `FUN_1439d9740` were not decompiled in
  this pass — the seed handler in particular is worth a follow-up since it's the actual entropy source.
- This whole function is export/serialization, not generation — it tells you the struct's shape, not the math that
  fills it in (noise functions, crater placement, etc. live elsewhere and were not located in this pass).

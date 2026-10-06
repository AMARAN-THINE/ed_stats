# Stellar Forge — procedural terrain generator (class/field names from strings)

"Stellar Forge" is Frontier's internal name for the system that procedurally generates planetary surfaces and body
properties. This documents what's recoverable **statically from this binary's string table** — the serializer's class
and field names for its terrain-generation input parameters, plus the planet-class taxonomy. No algorithm code was
decompiled; no copyrighted art, textures, or narrative content is included, and the encrypted asset store (see
`data-packages.md`) was not touched. All of this is already visible to anyone who runs `strings` on the retail exe.

## Why this is readable at all
The strings appear as one contiguous, ordered block (a reflection/serialization table): a `StellarForgeInput*` class
name followed immediately by its field names, then the next class name, and so on. This is almost certainly a
save/tooling format for planet "recipes" — fields such as `EjectaRadius` or `TidalVectorX` are generation *parameters*,
not literal measurements of any specific real planet in the game.

## Class hierarchy (65 `StellarForge*` type names found)
See `sf_classes.txt` for the full list. Grouped:
- **Framework**: `StellarForgeBase`, `StellarForgeManager`, `StellarForgeGalaxy`, `StellarForgeLive`,
  `StellarForgeLiveManager`, `StellarForgeLiveComponent`, `StellarForgeSimulation`, `StellarForgeSimulationClient`,
  `StellarForgeUtils`, `StellarForgeSkyboxMap`, `StellarForgeGeneratorComponents`, `StellarForgeGeneratorGalaxyMapComponents`,
  `StellarForgeObjectAdvance`, `StellarForgeAdvanceControl`, `StellarForgeAuxiliaryGenerationSource`,
  `StellarForgeContent`, `StellarForgeContentNoiseGenerators`, `StellarForgeChosenMaterials`,
  `StellarForgeAdditionalInformation`.
- **Terrain-feature input parameter blocks** (`StellarForgeInput*`, 22 classes): `Seed`, `Gravity`, `CommonVariables`,
  `MaskVariables`, `Basins`, `Mountains`, `Volcanoes`, `Cryovolcanoes`, `EuropaLines`, `Rifts`, `Ridges`, `Escarpments`,
  `Misc`, `EjectaCraters`, `SmallCraters`, `LargeCraters`, `HugeCraters`, `CoarseProportions`, `InternalValues`,
  `GasGiantModule`, `GeneralModule`, `RockyPlanetModule`, `V3BodySize`, `V3SurfaceInfo`, `V3CraterInfo`.
- **Body-class terminal types** (`StellarForge_*`, 20): Terrestrial — `EarthLike`, `WaterWorld`, `AmmoniaWorld`,
  `MetalRich`, `HighMetalContent`, `Rocky`, `RockyIcy`, `Icy`; Jovian — `WaterGiant`, `WaterGiantLife`, `WaterLife`,
  `AmmoniaLife`, `SudarskyClassI`–`V`, `HeliumRich`, `Helium`; plus `AsteroidCluster`.

## Per-class field names (from the serialization table)
| Class | Fields |
|---|---|
| `StellarForgeInputGravity` | `SurfaceGravAccelInG` |
| `StellarForgeInputSeed` | (seed value; no named sub-fields) |
| `StellarForgeChosenMaterials` | `Material_%u` (indexed array) |
| `StellarForgeInputCommonVariables` | `TectonicActivity`, `Volcanism`, `MaximumHeight` |
| `StellarForgeInputMaskVariables` | `TidallyLocked`, `TidalVectorX/Y/Z`, `CrateringFrequency`, `BasinMaskBasinBias`, `BasinMaskRegionFrequency`, `BasinMaskRegionSharpness`, `TectonicMaskPlateFracturing`, `TectonicMaskPlateThickness`, `VolcanismMaskLavaFlowFrequency`, `VolcanismMaskLavaFlowMaxSize` |
| `StellarForgeInputBasins` | `MinDepth`, `MaxDepth`, `SizeBias`, `BorderSharpness` |
| `StellarForgeInputMountains` | `Linearity`, `MaxHeight` |
| `StellarForgeInputVolcanoes` | `EjectaAmount`, `EjectaRadius` |
| `StellarForgeInputCryovolcanoes` | (shares the volcano fields) |
| `StellarForgeInputEuropaLines` | `MaxLength`, `Straightness`, `Collimation`, `EdgeDeformation`, `Grouping`, `Disjointment` |
| `StellarForgeInputRifts` | (shares ridge/escarpment-style fields) |
| `StellarForgeInputRidges` | `Variation` |
| `StellarForgeInputEscarpments` | `FrequencyOfOccurance`, `FrequencyOfScarp`, `Breadth` |
| `StellarForgeInputMisc` | `IceCap`, `PolarAxisX/Y/Z`, `LargeScaleDeformationHeight`, `IsATectonicWorld`, `TextureIndexMapping0-3`, `WangedTextureScalesX/Y/Z/W`, `MaxRadius`, `MinHeight` |
| `StellarForgeInputEjectaCraters` | `DirectionLength%u{x,y,z,w}`, `FracRadius%u`, `NumCraters` |
| `StellarForgeInputCoarseProportions` | `StageOne`, `StageTwo`, `StageThree` |
| `StellarForgeInputInternalValues` | `GravitationalAccelerationAtSurface`, `GravitatonalStress` [sic], `CoreFraction`, `CrustFraction`, `MagmaFraction`, `DifferentialTemp`, `PlateThicknessFactor` |
| `StellarForgeAdditionalInformation` | `DisplacementItemName`, `Amplitude0-3`, `DistanceStart`, `DistanceFinish` |
| `StellarForgeInputV3BodySize` | `MaxPhysicalHeight` |
| `StellarForgeInputV3SurfaceInfo` | `AverageSurfaceTemperature` |
| `StellarForgeInputV3CraterInfo` | `LargestCraterSize`, `LargestCraterDepth`, `CraterFrequency` |
| `StellarForgeInputSmallCraters` / `LargeCraters` / `HugeCraters` | (share the crater/ejecta field set, scaled by size tier) |

The table also carries a parallel pair of enumerations right after it: a human-readable body description (`"Earthlike
body"`, `"Water giant with life"`, …) mapped 1:1 to its internal type tag (`Terrestrial_EarthLike`,
`Jovian_WaterGiant_WithLife`, …), followed by a long list of atmospheric component names (oxygen, ammonia, carbon
dioxide, water-rich, methane-rich, …, down to exotic magma compositions like "silicate vapour", "metallic vapour",
"water magma").

## Related identifiers found nearby
- `IStellarForge`, `IStellarForgeLive`, `IStellarForgeSkyboxMap` — COM-style interfaces.
- `GetStellarForgeBodyInfo`, `ServerStellarforgeBridge`, `StellarForgeLiveSystem` — the client queries body info
  either locally or via a server bridge; error string: *"Cannot get stellarforge body info for a body from another
  system. Requested body system: %llu Script System: %llu"*, and *"Failed to find IStellarForge"*.
- Shared working path referenced in strings: `Win64/Shared/StellarForge/`.
- `PlanetColours`, `AtmosphereColours` — separate colour-table lookups, name only.

## What this does not give you
- No formula, noise function, or seed→surface algorithm — only the names of the parameters such a function would take.
  Recovering the actual generation math would require decompiling and understanding the functions that *consume* this
  struct, which is a large, open-ended task not attempted here.
- No copyrighted art/audio/narrative assets, and no attempt to decrypt the `FREA`-protected asset store.

## Addendum: sixth noise-module type found

While verifying an external document's claims against the binary (see `external-doc-verification.md`), a sixth
noise-module type name was found as a string literal: `RidgedMultifractalModule`, alongside the previously
documented `PerlinModule`, `BillowModule`, `AutoScaleModule`, `ConstantModule`, `ConstantColourModule`, and
`CurlPerlinModule`. No sample graph using it was found (same caveat as `CurlPerlinModule`).

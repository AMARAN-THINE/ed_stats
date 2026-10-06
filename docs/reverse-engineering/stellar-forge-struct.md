# Stellar Forge — planet input struct layout (decompiled, verified)

## Seed derivation located: a real Thomas Wang 64-to-32 integer hash, found by walking the call chain upward

Rather than guessing addresses, the call chain was walked upward from the already-known seed serializer
(`FUN_1439da060`): its single caller is `FUN_1439d7f30` (the top-level struct serializer below); its single
caller in turn is `FUN_143cd0400`, an async-task state machine (offset `0x74` holds a 0/1/2/3 state field) that,
on reaching state 2, calls `FUN_1439168e0(local_8a8, local_8e8)` — the function that actually **builds** the
`StellarForgeInput` struct (`param_1`) by copying fields out of a body/celestial-object pointer (`param_2`),
before `FUN_1439d7f30` serializes it. `FUN_1439168e0` contains this inline, twice (once unconditionally near the
top, once more inside an `if (flagbyte == 0) { ... } else { uVar5 = param_2[200]; }` cached-vs-recompute branch
near the end):
```
uVar8 = param_2[3] * 0x40000 + ~param_2[3];      // key*2^18 + ~key  == (~key) + (key<<18)
uVar8 = (uVar8 >> 0x1f ^ uVar8) * 0x15;           // key ^= key>>31; key *= 21
uVar8 = (uVar8 >> 0xb  ^ uVar8) * 0x41;           // key ^= key>>11; key += key<<6 (== key*65)
result = (uint)(uVar8 >> 0x16 ^ uVar8);           // key ^= key>>22; truncate to 32 bits
```
This is byte-for-byte **Thomas Wang's public-domain 64-bit-to-32-bit integer hash** (`hash6432shift`), down to
every shift amount (31/11/22) and multiplier (21, and 65 expressed as `key + key<<6`). Verified independently in
Python against the compiled constants — see `tools/` commit for the check. The result is written directly to
`*(uint*)((longlong)param_1 + 0x834)`, which is **exactly** struct offset `0x20d` in dwords (`0x20d * 4 = 0x834`)
— the field this document had already identified (before this trace) as `Seed`, confirming the match isn't
coincidental.

**The hash input is `param_2[3]`** — a 64-bit field at byte offset `0x18` of the body/celestial-object pointer
passed into `FUN_1439168e0`. This is the actual, located, verified terrain-seed derivation:
```
Seed = WangHash64to32(body_object[0x18])
```
This single `uVar8`/hash sequence is the direct answer to the "SystemAddress → generation seed" search that
every previous attempt this session (string xrefs, raw address scans, and the external document's debunked claim)
failed to find — found here not by searching for the algorithm, but by following the one real, unambiguous call
chain from the already-confirmed seed *consumer* back to its producer.

**What's still open:** whether `body_object+0x18` **is** the game's `SystemAddress`/`BodyID` value, or some other
per-body 64-bit identifier (e.g. an internal pointer-derived or session-local ID) that merely correlates with it,
has not yet been independently confirmed — that requires tracing where `body_object+0x18` itself is written, which
this pass did not do. The hash function identification itself is solid (exact algorithmic match); the semantic
claim "this IS the SystemAddress" is not yet proven and should be treated as the next concrete step, not fact.

**Supporting evidence found (same hash, reused as a hash-table bucket function):** `FUN_143ce8660`, the function
that looks up the body object consumed by `FUN_1439168e0`, independently contains the **exact same** Wang hash
sequence applied to a 64-bit key (`*param_3`), used purely as a hash-table bucket index:
```
bucket = WangHash64to32(key) % *(bucketCount at param_1+0x148)
entry  = bucketArray[param_1+0x140][bucket]
while entry != sentinel:
    if key == entry.storedKey: return entry.objectPointer   // classic chained hash map
    entry = entry.next
```
This is a general-purpose 64-bit-ID-keyed hash map (bucket array + chaining + stored-key comparison), and it's
exactly the kind of structure an engine would use to look up a specific celestial body by a unique 64-bit ID
(a `SystemAddress`/`BodyID`-style key is the obvious candidate for what such a cache would be keyed on). This
doesn't prove `body_object+0x18` is that same key — the call site's exact key-passing wasn't fully resolved in
this pass — but it shows the same hash function is the engine's general per-body-ID hashing primitive, not a
one-off, which is consistent with (though not proof of) the SystemAddress/BodyID hypothesis above.

**Follow-up attempt to resolve this, result: inconclusive, documented honestly.** Two angles were tried to pin
down whether `body_object+0x18` is literally `SystemAddress`/`BodyID`:
1. `FUN_143ce8660` (the lookup) has **37 distinct callers** across the binary — it's a generic ID-keyed cache
   accessor used by many unrelated subsystems, not something specific to celestial bodies. Caller-context alone
   can't disambiguate what any one caller's key represents without reading all 37, which wasn't done.
2. `FUN_142c9e5f0`, the journal handler already documented (`codex-journal.md`) as writing `SystemAddress`/`BodyID`
   fields for the `ApproachBody`/`LeaveBody` events, was decompiled to check what offset it reads those fields
   from on its body-like object — but it turned out to be only the **CSV-header string writer** (a literal
   `"ApproachBody,LeaveBody,StarSystem,..."` header constant, gated behind a debug-export flag), not the function
   that reads the live field values. It doesn't contain the offset information needed.

Neither angle resolved it. The semantic identity of `body_object+0x18` remains **unconfirmed** — treated as an
open question, not fact, consistent with the caveat above. Further progress would need either locating the
sibling function that actually serializes `SystemAddress`/`BodyID` with live values (not just the header) for a
journal event on the same object type, or tracing the object's constructor directly.

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
| 0x20d | seed value, serialized (not computed) by `FUN_1439da060` as `"StellarForgeInputSeed"` | Seed |
| 0x210 | passed to `FUN_1439d9740`, serialized as `StellarForgeInputGravity`/`SurfaceGravAccelInG` | Gravity |
| 0x214+ | passed by pointer to `FUN_1439d9b40`, serialized as `StellarForgeChosenMaterials` (`Material_%u` entries) | — |
| 0x21c+ | passed by pointer to `FUN_1439d9200`, serialized as `Amplitude0-3`/`DistanceStart`/`DistanceFinish` | — |
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

## `FUN_1439da060`/`FUN_1439d9b40`/`FUN_1439d9200`/`FUN_1439d9740` decompiled: confirmed dead end, not entropy sources

A follow-up pass decompiled all 4 previously-flagged functions. All four are **key/value struct-field serializers**
— the same request-object-construction pattern documented repeatedly elsewhere in this repo
(`FUN_140541280`/`FUN_14071b6e0`/`FUN_14071d1f0` building a tree of named fields) — not RNG or generation code.
Despite its name/role ("seed, passed to..."), `FUN_1439da060` only writes the pre-existing seed value it's handed
(`param_2`) into a KV node literally named `"StellarForgeInputSeed"`; it does not compute or derive that value.
This definitively closes this specific lead as a dead end for locating the entropy source — it was a reasonable
thing to check given the misleading field label, but it's export plumbing like the rest of this struct, not
generation math.

The same pass surfaced more field names from these serializers, confirming and extending the table above:
`StellarForgeChosenMaterials` (dynamic `Material_%u` sub-entries), `StellarForgeAdditionalInformation`,
`DisplacementItemName`, `Amplitude0`–`Amplitude3`, `DistanceStart`, `DistanceFinish` (all from `FUN_1439d9200`'s
body, a displacement/amplitude-ramp sub-struct), and `StellarForgeInputGravity`/`SurfaceGravAccelInG`/`Gravity`
(from `FUN_1439d9740`).

## Caveats
- This whole function (and the 4 above) is export/serialization, not generation — it tells you the struct's shape,
  not the math that fills it in (noise functions, crater placement, etc. live elsewhere; the GPU-side noise math
  is covered separately in `gpu-terrain-shaders.md`/`stellar-forge-noise-spec.md`, and the CPU-side seed-derivation
  site remains unlocated after this and prior attempts).

## Noise-generator module graph (confirmed noise algorithm identity)

Two small embedded default resources (`XMLResDocument` / `NoiseGenerator`, symbols `DefaultSurface` and
`DefaultClouds`) show the actual noise-graph format and name the real underlying algorithm — this is the first
concrete evidence of what math generates terrain height/colour, as opposed to just the parameter struct that feeds it.

**Graph shape**: a `NoiseGenerator` has named `Outputs` (`Height`, `Colour`, `EmissiveMask`), each pointing at a
`ModuleRef` into two typed module lists — `NoiseModules` and `ColourModules` — wired together by referencing each
other's `Name`/`refName` (a small dataflow graph, not a flat parameter list).

**Module types found** (`def="..."` attribute): `PerlinModule`, `BillowModule`, `AutoScaleModule`, `ConstantModule`,
`ConstantColourModule`. A sixth type, `CurlPerlinModule`, is named elsewhere in the strings but not present in either
sample graph.

**`DefaultSurface`/`DefaultClouds` preset** (both use the same graph shape in the sampled strings): a `PerlinModule`
node with parameters `frequency=1`, `lacunarity=2`, `persistence=0.5`, `octaves=10`, `seed=0`, feeding an
`AutoScaleModule` (remaps output into `min=-1`/`max=1`) that drives the `Height` output; a `ConstantModule`
(`value=-1`) drives `EmissiveMask`; a `ConstantColourModule` (flat RGBA `1,1,1,1`, i.e. white) drives `Colour`.

**What this confirms**: terrain height is generated by standard fractal/octave **Perlin noise** (10 octaves, lacunarity
2, persistence 0.5 — classic fBm parameters), not a bespoke algorithm, consistent with the string `perlinNoise` and
the fBm-looking string fragment (`fbm{`) found elsewhere in the binary. The `StellarForgeInput*` struct documented
above almost certainly supplies the per-feature parameters (frequency, seed, amplitude-like fields) that these
`PerlinModule`/`BillowModule` nodes consume, rather than the generator reading one single global noise graph per
planet — but the code path that builds a per-planet graph from the struct was not located in this pass.

This also confirms `StellarForgeInputSeed` (handled by `FUN_1439da060`, decompiled above) is, as expected, the Perlin
seed — `FUN_1439da060` is still only the serializer for it, not the RNG/hash itself.

## Serializer chain fully mapped — generation math is not in this binary's CPU code

All sub-block functions called from `FUN_1439d7f30` were decompiled and checked: `FUN_1439d9520` (ejecta craters),
`FUN_1439da060` (seed), `FUN_1439d9b40` (module/gravity-adjacent block), `FUN_1439d9200`
(`StellarForgeAdditionalInformation` / `DisplacementItemName`), `FUN_1439d9740` (`StellarForgeInputGravity`). Every
one follows the identical pattern: allocate a key string, open/append a named section via `FUN_1439c7490`, write one
or more fields via `FUN_1439da630`/`FUN_1439da8e0`. **None of them compute anything** — this whole call tree,
~8,000+ addresses across six functions, is confirmed to be the planet-parameter export/serialization path, not the
generator.

This also means the noise-module graphs documented above (`PerlinModule`, `BillowModule`, etc.) are evaluated
somewhere else, not in this call tree.

### Where the real terrain math likely lives
The CSA compute-shader archives (`PlanetShaders/*.csa`, documented in `data-packages.md`) contain named entry points
such as `cs_Scatter_Everywhere_AllSizes0_0_Win64_SM50` — i.e. GPU compute shaders for planetary surface/scatter
generation. These are **separate data files from the game installation, not inside `EliteDangerous64.exe`**, and were
not obtained or analysed in this session (only the executable was downloaded). If the actual per-vertex terrain
generation algorithm is wanted next, the concrete next step is pulling a `.csa` file from a real game install,
extracting its DXBC shader blobs per the method in `data-packages.md` §2.4, and disassembling the compute shader
bytecode (e.g. with a DXBC disassembler) — a different, GPU-side investigation from anything possible with the exe
alone.

### Summary of what is / isn't established about Stellar Forge from this exe
- **Established**: full class/field taxonomy (`stellar-forge.md`), verified struct byte-offsets for the planet input
  parameters (above), the noise-module graph file format and that it uses standard octave/fractal Perlin noise
  (`DefaultSurface`/`DefaultClouds` presets).
- **Not established from this binary**: the function(s) that build a per-planet noise graph from the input struct;
  the actual height/colour evaluation math; anything GPU-side (that lives in `.csa`/DXBC, a separate asset, not this
  executable).

## `StellarForgeManager` top-level init (`FUN_1401f4700`, 11,163 addresses, 259 calls)

Too large to decompile-and-read exhaustively, but its structure is clear from the named categories it loads in
sequence (each via the same open/create-named-section pattern used throughout this subsystem): `Elite_Dangerous`
(root namespace), `BodyInfoOverrideDatabase`, `OverrideDatabase`, `GalaxyRegions`, `PowerPlayRegions`,
`StationColourGrading`.

**Conclusion**: `StellarForgeManager`'s initialization is a **galaxy-wide static database loader** — region
definitions, per-body overrides, Powerplay region data, and station colour-grading tables — not the per-planet
procedural generator. This is consistent with `StellarForgeGalaxy`/`StellarForgeManager` being the "load the galaxy's
static/authored data" layer, while the actual per-body noise evaluation (documented above as living partly in GPU
compute shaders) is a separate, per-body code path invoked elsewhere, not inside this init function.

This function was not decompiled line-by-line beyond identifying these category loads; a full read of its ~11k
addresses was out of scope for this pass.

## `GetStellarForgeBodyInfo` is a Lua scripting API entry, not a standalone function

`FUN_1429d5990` (1,656 addresses), found via xref to the string `GetStellarForgeBodyInfo`, turns out to be a **Lua
API registration table**, not the body-info query implementation itself. It registers 49 named functions as
scriptable mission/scenario API calls, of which `GetStellarForgeBodyInfo` is one. This confirms mission/scenario Lua
scripts can query Stellar Forge body data directly, alongside functions for:

- **Objectives/missions**: `AddObjective`, `AddObjectiveGroup`, `UpdateObjective`, `UpdateObjectiveGroup`,
  `GenerateIntroScriptedObjective`, `GenerateNextScriptedObjective`, `CommanderHasObjective`,
  `AddCommanderToObjective`, `RemoveCommanderFromObjective`, `GetCommandersWithObjective`, `GetMissionInfo`.
- **Commander/world state**: `GetCommanderState`, `RegisterCommanderStateChangeCallback`,
  `ClearCommanderStateChangeCallback`, `SetStateVariable`, `ClearStateVariable`, `GetStateObject`,
  `GetAvailableStateObjects`, `GetAvailableCommanderStates`.
- **World/system queries**: `GetStarSystemInfo`, `GetSystemAddress`, `GetBodysiteID`, `GetBodysiteInfo`,
  `GetStellarForgeBodyInfo`, `GetAllLevelObjects`, `GetPowers`, `GetPowerSystem`.
- **Encounter/AI control**: `ScriptSpawnedAI`, `PauseGenerationOfNamedEncounter`,
  `UnPauseGenerationOfNamedEncounter`, `ShouldDisableConflictZones`, `ClaimObject`, `ReleaseObject`.
- **Scripting plumbing**: `RegisterEventHandler`, `UnregisterEventHandler`, `IsValidEventName`,
  `RegisterPeriodicCallback`, `UnregisterPeriodicCallback`, `RequestAdvance`, `EnableAdvanceOnEvent`,
  `GetScenarioCSMState`, `GetScenarioTimer`, `GetTimeStep`, `GetCurrentTimeMS`, `GetCurrentEpochTime`,
  `GetRandomGenerator`, `TrackStat`, `AddTeamMarker`, `ClearTeamMarker`.

This is the clearest evidence yet of the mission/scenario scripting layer's shape: a Lua environment with direct,
named access to Stellar Forge body data, system/power state, and a full objective/event/callback framework — this is
almost certainly the system behind Community Goals, scripted encounters, and mission scenarios. The actual
*implementation* of `GetStellarForgeBodyInfo` (what it returns, and whether it touches generation or just reads
cached/stored body data) was not traced past this registration table in this pass.

## Two more large `StellarForge*`-adjacent functions, decompiled

### `StellarForgeAuxiliaryGenerationSource` (`FUN_1439c5250`, 7,124 addresses)

A second galaxy-wide static database loader (same pattern as `StellarForgeManager`'s init), registering:
`ColourTableHelper`, `CompoundComponent`, `ElementComponent`, `ReactionComponent` (chemistry/materials data — likely
what backs mining refinement and material synthesis), `EmissionColours`/`NebulaTable` (nebula rendering data),
`ServerSystemMetaDataOverride`, and `PortDatabase`/`StationDatabase`/`StationNameDatabase` (station generation data).
"Auxiliary generation source" is an accurate name: this is supplementary static data the generator draws on, separate
from the per-planet `StellarForgeInput*` struct.

### `StellarForgeSkyboxMap` (`FUN_143c0fa80`, 7,910 addresses)

Despite the name, this is **not** planet skybox rendering — it's a component-class registration function for the
**Galaxy Map / System Map** UI and rendering subsystem: `GalaxyMap`, `GalaxyMapCamera`, `GalaxyMapInput`,
`GalaxyMapLabelManager`, `GalaxyMapNameSearch`, `GalaxyMapNavigation`, `GalaxyMapTradeRoutes`,
`GalaxyMapFleetCarriers`, `GalaxyMapVisualisation`, `GalaxyMapUIComponent`, `GalaxyRenderManager` (+ "ForCapture"
screenshot variants), `SystemMap`, `SystemMapCamera`, `SystemMapOrrery`/`SystemMapOrreryCamera`,
`SystemMapObjectStore`, `SystemMapUIComponent`, `SystemRenderManager`, `SkyboxStarRenderManager`,
`MilkyWayBBoardManager` (the background starfield billboard renderer), plus settlement/body-placement helpers
(`AncientSettlementProcessor`, `ManualSettlementProcessor`, `SettlementPositionUpdater`, `PlanetMapBodyManager`,
`PlanetMapLightComponent`, `SystemContentProcessor`, `BlackHoleInfoHolder`, `VolcanicDatabase`,
`PlanetResourceResolverInspector`, `TradeRoutesCache`). The "skybox" in the name likely refers to the Milky Way
backdrop rendered behind the galaxy map, which this function also registers (`MilkyWayBBoardManager`,
`SkyboxStarRenderManager`), rather than per-planet sky rendering.

Both functions are, like `StellarForgeManager`'s init, component/database **registration** code, not generation
algorithms — consistent with every large `StellarForge*`-named function found so far being part of the setup/data
layer rather than the noise evaluation itself (which, per the earlier finding, is GPU-side).

## `StellarForgeLiveManager` and the three-tier architecture (complete picture)

`FUN_143c957c0` (`StellarForgeLiveManager`, 2,831 addresses) registers: `FrameOfReferenceShiftHandler` (a
floating-origin technique — re-centering coordinates around the player to avoid float precision loss far from galaxy
origin), `LevelRingCellManager`/`LevelRingCellShape` (ring-based spatial cell partitioning, almost certainly the
streaming/LOD mechanism for loading nearby systems as the player moves), `SpaceLocationComponent`/
`StaticLocationComponent`, `StarVisualAspect`, and `TextureSliceManager`.

**This completes the picture of what the large `StellarForge*` functions actually are.** None of the six largest
`StellarForge`-prefixed functions found in this binary are the generation algorithm; they're three distinct
registration/setup tiers:
1. **Static galaxy database** — `StellarForgeManager` (regions, Powerplay, overrides) and
   `StellarForgeAuxiliaryGenerationSource` (chemistry, nebula colours, station databases).
2. **Runtime/live simulation** — `StellarForgeLiveManager` (frame-of-reference shifting, spatial streaming cells,
   star visuals) — this is the layer active while flying.
3. **Map/UI presentation** — `StellarForgeSkyboxMap` (Galaxy Map, System Map, Orrery, and their cameras/renderers).

The remaining six `StellarForge*`-prefixed functions checked (`StellarForgeGeneratorComponents`, `StellarForgeLive`,
`StellarForgeLiveComponent`, `StellarForgeSimulation`, `StellarForgeSimulationClient`, `StellarForgeUtils`) are all
the identical minimal RTTI/type-registration stub (112 addresses each, same shape as `StellarForgeGalaxy`
documented earlier) — pure C++ static-initialization boilerplate, nothing further to extract from them.

**Where this leaves the investigation**: every `StellarForge`-named function reachable by name from this binary has
now been checked. None contain the noise-evaluation/terrain algorithm itself — that remains confirmed as living in
the GPU compute shaders (`gpu-terrain-shaders.md`). The CPU side of Stellar Forge, as implemented in this
executable, is data management, streaming, and presentation around a GPU-computed core.

## Location/hyperspace streaming subsystem (`DockedHyperspaceComponent`/`DockedHyperspaceLocation`)

Two more large component-registration functions, `FUN_141bf4780` (6,235 addrs) and `FUN_1421b4220` (5,198 addrs),
register the **location streaming and hyperspace transition** subsystem — this is what manages the current star
system "instance" as a loaded/replicated level, separate from the three Stellar Forge tiers documented above:

- **Hyperspace/jump transition**: `HyperspaceComponent`, `HyperspaceEffects`, `HyperspaceLocation`,
  `HyperspaceLiveManager`, `HyperspaceInterdictionStatus`, `HyperspacePersonalisationComponent`,
  `HumanoidHyperspaceComponent`, `PrepareForHyperspaceJump`, `SupercruiseTransitionHelper`,
  `SuperCruiseEncounterStatus`, `DelayLocationOnStream`, `DelayLocationOnThisObject`.
- **Location/level management**: `LocationManager`, `LocationAdmin`, `TransistionLocationAdmin` [sic],
  `LocationLevelObject`, `LocationPhaseContainer`, `LocationObjectCreator`, `LocationInformationComponent`,
  `LocationDeclareFORShifts` (frame-of-reference, ties to `FrameOfReferenceShiftHandler` found earlier),
  `LocationResourceLoadingBudget`, `LocationFixedEventManager`, `LocationAsteroidManager`,
  `LocationDecalsComponent`, `LocationIslandCustomiser`, `LocationExhibitionEnvironmentManager`,
  `HiddenBodysiteManager`, `StarSystemDataCache`.
- **Streaming/loading**: `LoadingScreenComponent`, `LoadingScreenObjects`, `HumanoidLoadingScreenObjects`,
  `LevelBaseComponent`, `ReplicatedLevelContainer`, `ReinstanceManager`.
- **NPCs and signal sources**: `NPCConversationManagerComponent`, `NPCMissionGiverManager`, `USSRegionManager`
  (Unidentified Signal Source spawn regions), `USSTimeReporter`, `RandomEventOverrideParameterCache`.

This is the fourth architectural tier found (alongside static DB / live sim / map UI documented earlier): the
per-system **instance/level streaming layer** that loads and tears down the currently-occupied star system as the
player jumps between systems, handling USS spawns, NPCs, and the hyperspace cinematic transition itself.

## Clarification: the StellarForge `KeyValue` serializer uses string keys, not hashes

Decompiling `FUN_1439da630` (the field-setter called throughout the serializer documented above) confirms it builds
literal string-keyed `"KeyValue"` pairs — the field name parameter (`param_2`) is copied directly as a string into
the pair, not hashed. This is consistent with the field names appearing as real string literals in the decompiled
code (as shown in the offset table above) and confirms that documentation is accurate. It also means this function
is *not* related to the separate hash-dispatcher mechanism used by `Market.json`/`ScanOrganic`/etc.
(`codex-journal.md`) — those remain a distinct, unlocated system; this was a negative result for that specific lead,
not a resolution of it.

## `ILocationInformation` interface accessors (scripting error-tagging pattern confirmed)

Four small functions (`FUN_140a1d2e0`, `FUN_140acf660`, `FUN_1413de6a0`, `FUN_140a1d400`; 278–491 addresses each)
reference the string `"ILocationInformation"` — not as a field name, but as an **interface-not-found error tag**,
the same pattern already seen for `"Failed to find IStellarForge"` in `network.md`'s Lua API findings. This confirms
a general convention in this codebase's scripting/interface-lookup layer: when a script or system requests an
interface (`IStellarForge`, `ILocationInformation`, etc.) that isn't available on the current object, the error
message embeds the literal interface name. `GetBodysiteInfo`/`GetBodysiteID` (referenced only from the 49-function
Lua API table documented earlier) still have no separate dedicated implementation locatable by string xref — this
remains a dead end for finding their actual logic; the Lua API table is a dispatch table whose targets are resolved
through a different, not-yet-found mechanism (consistent with the hash-dispatcher dead ends recorded elsewhere in
this doc set).

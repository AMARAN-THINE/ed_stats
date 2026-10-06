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

**UPDATE — now substantially confirmed via `GetStellarForgeBodyInfo`'s real implementation (`FUN_1429e8d30`),
decompiled later in this same investigation (see the full section below for how it was found).** That function:
```c
if ((*(ulonglong *)(*(longlong *)(param_1 + 0x10) + 0x20) & 0x7fffffffffffff) !=
    (*param_4 & 0x7fffffffffffff)) {
    error("Cannot get stellarforge body info for a body from another system. "
          "Requested body system: %llu Script System: %llu");
    ...
}
(**(code**)(**(longlong**)(param_1+0x60) + 0x168))(...);           // resolve current level/world object
FUN_143ce8660(local_200, &local_1f0, param_4);                     // THE SAME lookup/hash-table function
// local_1f0 now has fields BodyType, StellarMass, Radius, SurfaceTemperature, SpectralClassification, Sequence
```
This explicitly: (a) validates that `param_4`'s low 55 bits match the **script's own `SystemAddress`**
(`(param_1+0x10)+0x20`, the exact same field/mask already confirmed as real `SystemAddress` via the decompiled
`GetSystemAddress` binding below), (b) then passes the **full, unmasked** `param_4` into `FUN_143ce8660` — the
identical Wang-hash-based lookup function documented above — and (c) gets back an object with real per-body
stellar fields (confirming the lookup returns one specific *body*, not a system container). This means:

- `param_4` (the body ID argument a script passes to `GetStellarForgeBodyInfo`) is a **composite 64-bit key**:
  low 55 bits = `SystemAddress`-equivalent (shared by all bodies in a system, which is exactly what the
  same-system validation checks), high ~9 bits = a body-within-system discriminator.
- This composite key is exactly what `FUN_143ce8660`'s Wang-hash table is keyed by — the same lookup
  infrastructure reached from `FUN_1439168e0` (via `FUN_143cd0400`) for the terrain-seed builder.
- `body_object+0x18` (the Wang-hash input for the `Seed` field) is therefore extremely likely this same
  composite `SystemAddress`+body-index key, cached redundantly on the body object itself (explaining why
  `FUN_1439168e0` re-hashes it — it's re-deriving the exact same hash already used to locate the object).

**Remaining honest caveat:** this traces the *lookup key's* structure and confirms it's `SystemAddress`-rooted
with high confidence; it does not independently re-verify that `body_object+0x18`'s bytes, read directly in
`FUN_1439168e0`, are bit-identical to this composite key rather than some derived/re-encoded copy — that would
need one more direct trace (confirm `body_object` in both call sites is the same object/offset), not done here.
Treated as "substantially confirmed, one direct-identity trace short of airtight," not asserted as settled fact.

**One more direct trace completed on the *key's source side* (not the body-object side):** disassembled
`FUN_143cd0400`'s actual call to `FUN_143ce8660` at the machine-instruction level (the decompiled C had silently
dropped the 3rd argument). The call sets up `RCX` = the hash-table object and `RDX` = the output pointer
immediately before the `CALL`, but the 3rd argument register (`R8`, the key pointer per Microsoft x64 calling
convention) is **not freshly loaded there** — it was set earlier, at `R8 = LEA [RDI + 0x80]` (`RDI` = `param_1`,
the task object itself), i.e. the key pointer is `&(task_object + 0x80)`. That field is the exact one the
earlier-documented state-1 logic keeps synchronized with `task_object + 0x78` via a dirty-check/copy
(`if (*plVar8 == *plVar3) {...} else {*plVar8 = *plVar3; *state = 1;}`). So the composite key's ultimate source,
on the *producer* side, is a field the async task stores on itself — consistent with "which body was this task
asked to build Stellar Forge data for," set once when the task is created/queued, exactly as expected for a
request-processing state machine. This confirms the key-sourcing mechanism all the way back to the task object,
but — as the caveat above already notes — still doesn't independently confirm `body_object+0x18` (read inside
`FUN_1439168e0`, on the *object the lookup returns*, not the task that requested it) holds this identical value
rather than a derived copy stored on the body object during its own construction/caching. That specific link
(tracing the body object's constructor) remains the one open step for full closure.

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

**One suggestive (not conclusive) data point found along the way:** a different caller of the same lookup
infrastructure, `FUN_143ce8740`, masks its 64-bit key to its low 55 bits (`key & 0x7fffffffffffff`) before a
*separate* shard lookup (`FUN_143cea1e0`), then — only if that shard resolves and a type-tag check passes — calls
`FUN_143ce8660` again with the **original, unmasked** key against that shard's own table. This is a two-level
sharded-cache shape (top 9 bits select a shard/region, bottom 55 bits are the in-shard key), which is at least
consistent with a packed spatial identifier in the `SystemAddress` family (sharding a cache by galaxy
region/sector is a natural design). This is a different call site than the one feeding `FUN_1439168e0`, so it
does **not** directly confirm what `body_object+0x18` holds — it's offered only as suggestive context for the
hypothesis, not as evidence for this specific field.
Neither angle resolved it by itself. The semantic identity of `body_object+0x18` remains **unconfirmed** — treated
as an open question, not fact, consistent with the caveat above.

**Strong corroborating evidence found via a third angle: the real `GetSystemAddress` Lua binding, decompiled.**
The Lua API table (`stellar-forge.md`) lists `GetSystemAddress` by name only; its actual implementation was
located by finding the single reference to the literal string `"GetSystemAddress"` (at `0x1453056c0`), which
leads straight to its registration in the master Lua-binding function `FUN_1429d5990`
(`FUN_14078b4f0(&local_res8, "GetSystemAddress", FUN_1429eacb0, 0xffffffff)`), confirming the real implementation
is `FUN_1429eacb0`. Decompiled:
```c
plVar5 = FUN_140792670(param_1, 1);       // resolve Lua arg 1 ("self"/location object)
lVar6 = *plVar5;
lVar1 = *(longlong *)(lVar6 + 0x10);
cVar3 = FUN_1408beea0(lVar1 + 0x20);      // flag check on the field at +0x20
uVar2 = *(undefined8 *)(*(longlong *)(lVar6 + 8) + 0x10);
if (cVar3 == '\0') {
    FUN_140787440(local_res8, uVar2);                                    // path A: no mask
} else {
    FUN_1407873f0(local_res8, uVar2, *(ulonglong *)(lVar1 + 0x20) & 0x7fffffffffffff);  // path B: masked
}
```
**This is the same exact `& 0x7fffffffffffff` (low-55-bit) mask found independently in the unrelated hash-table
sharding code (`FUN_143ce8740`, documented above) — not a coincidence this time, since this is the real,
by-name-confirmed `GetSystemAddress` accessor itself.** This substantially strengthens (without yet being 100%
conclusive, since the two call sites are still on different objects) the case that the 55-bit-masked hash-table
sharding scheme documented above is specifically operating on `SystemAddress`-family values, and that real
`SystemAddress` values on this "location object" (at `lVar1+0x20`, gated by a flag byte for whether to apply the
mask) do get the same bit-masking treatment.

**Still not fully closed:** this confirms a struct offset (`+0x20` on a *different* object than `body_object` in
`FUN_1439168e0`) for `SystemAddress` itself, and confirms the 55-bit mask is specifically applied to
`SystemAddress`-class values elsewhere in the engine — but it does not yet trace whether this `lVar1+0x20` field
and the terrain-seed's `body_object+0x18` field are the same value, the same object, or merely related/sibling
objects in the same location hierarchy. Tracing that connection (what object is `lVar1`, and is it reachable from
or identical to the body object `FUN_1439168e0` operates on) is the next concrete step, not yet done here.

**`GetBodysiteID` (the named `BodyID` Lua accessor) decompiled too, confirming it shares the same "self" object:**
found the same way, via its registration in `FUN_1429d5990` (`FUN_14078b4f0(&local_res8, "GetBodysiteID",
FUN_1429e5240, 0xffffffff)`), real implementation `FUN_1429e5240`:
```c
lVar3 = *FUN_140792670(param_1, 1);                      // same "self" resolution as GetSystemAddress
if (*(longlong *)(*(longlong *)(lVar3 + 0x10) + 0xc0) == -1) {
    FUN_140787440(local_res8, *(undefined8 *)(*(longlong *)(lVar3 + 8) + 0x10));   // BodyID value
} else {
    FUN_1407873f0();   // different/invalid-state path, not traced further
}
```
This confirms `GetSystemAddress` and `GetBodysiteID` both operate on the **same Lua "self" object** (`lVar3`/
`lVar6` are the same resolve), just reading different sub-pointers off it: `SystemAddress` comes from the
sub-object at `+0x10` (field `+0x20`, mask-gated), `BodyID` from the sub-object at `+8` (field `+0x10`,
gated by a *different* sentinel check — `subobject(+0x10)+0xc0 == -1` — on the first sub-object, not the second).
So `SystemAddress` and `BodyID` live on two different sub-objects hanging off the same parent, which is a
sensible "location" object shape (e.g. a `StarSystem` pointer and a `Body` pointer bundled together).

`FUN_1408beea0` (the flag check gating `SystemAddress`'s masked path) was also decompiled: it is **not**
SystemAddress-specific. It's a generic coordinate/position-validity check — testing roughly a dozen `double`
fields (at various offsets on its argument) against a NaN-like sentinel bit pattern (`value | 0x800fffffffffffff
!= 0xffffffffffffffff`), consistent with validating a 3D position (or several nested positions) hasn't been
resolved/is sentinel-valued yet. This means the earlier "flag check" framing was imprecise: what gates whether
`GetSystemAddress` returns the masked value is really "has this location's position data been resolved," not a
SystemAddress-specific flag bit.

None of this closes the original `body_object+0x18` question, but it now gives verified, by-name-confirmed struct
offsets for where real `SystemAddress` (`subobject+0x20`) and `BodyID` (`subobject+0x10`) values live on the Lua
location-binding object — useful ground truth for comparing against `body_object` in `FUN_1439168e0` if that
object's own constructor/type is identified in a future pass.

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
Lua API table documented earlier) had no separate dedicated implementation locatable by string xref *at the time
this note was written* — **superseded below**: a later pass found the Lua API table's registration site directly
(`FUN_1429d5990`, the master binding function, found via the xref to the `"GetSystemAddress"` name string) and
decompiled `GetBodysiteID`'s real implementation (`FUN_1429e5240`) along with `GetSystemAddress`'s
(`FUN_1429eacb0`) — see the "Seed derivation located" section near the top of this file for both. The earlier
"dead end" framing was about not having found the registration mechanism yet, not about the functions being
permanently unlocatable; they were locatable once the actual registration call (not an error-tag string) was
used as the search anchor.

**`GetBodysiteInfo` decompiled too — reveals "Bodysite" means ground settlement, not generic celestial body.**
`FUN_1429e52f0` (the registered implementation) delegates straight to `FUN_1429e5380`, which:
- Confirms `*(longlong*)(*(longlong*)(param_1+0x10)+0xc0)` (the same sentinel field gating `GetBodysiteID`'s
  path) **is** the `BodyID` value itself, not just a validity flag — it's passed directly as a lookup key
  (`FUN_1429e08f0(lVar5, local_68, local_res18)`, `local_res18[0] = that field`) into what looks like a
  ground-settlement data cache (`lVar5 = lVar7 + 0xb8`, off a "current level/world" object).
- Returns a key/value record with real field names found as literals: **`BodysiteID`**, **`ScenarioCSMState`**,
  **`SettlementDifficulty`**, **`ConflictZoneIntensity`**, **`IsThargoidDangerState`** (the last computed as
  `(enum_value - 0x22) < 3`, i.e. a 3-value enum range check, not a simple boolean flag read).

## GetStellarForgeBodyInfo decompiled: capstone finding tying SystemAddress to the terrain-seed hash table

Found the same way as the others: its Lua-table registration entry (`FUN_14078b4f0(&local_res8,
"GetStellarForgeBodyInfo", &LAB_1429e8bc0, 0xffffffff)`) pointed at `0x1429e8bc0`, which turned out to be a
`LAB_`-prefixed address: a real instruction with no `Function` object covering it (Ghidra's auto-analysis never
created one there, for reasons not investigated). Forcing a function to be created at that address
(`CreateFunctionCmd`) and decompiling it worked: it's a thin Lua-argument-marshalling wrapper (self object plus
optional numeric arg plus optional bool arg) that immediately delegates to `FUN_1429e8d30`, the real ~800-instruction
implementation. See the "Seed derivation located" section above for the finding itself (the same-system
validation plus `FUN_143ce8660` lookup, confirming the lookup's composite key is SystemAddress-rooted).

This pass also confirmed several more fields as live literals on the looked-up body object: `BodyType`,
`StellarMass`, `Radius`, `SurfaceTemperature`, `SpectralClassification` (via a sub-lookup, `FUN_143c56d60`, keyed
by a small integer field at `plVar9[0x89]`), and `Sequence` (the star's luminosity/evolutionary-sequence class,
same sub-lookup pattern) -- real fields on the per-body object returned by the SystemAddress-rooted
composite-key lookup, distinct from (and in addition to) the StellarForgeInput struct fields documented via the
serializer earlier in this file.
- This settlement-specific field set (`SettlementDifficulty`, `ConflictZoneIntensity`, `IsThargoidDangerState`)
  confirms "Bodysite" in this API is a **ground settlement on a planet's surface**, not the general celestial
  body/location object used elsewhere. This explains why it's a structurally separate accessor family from
  `GetSystemAddress`/`GetStarSystemInfo` despite superficially similar names, and means `GetBodysiteID` is a
  settlement-ID lookup, likely unrelated to the terrain-seed's `body_object` in `FUN_1439168e0` (which is about
  planetary terrain generation, not settlement placement) — a useful negative result narrowing the search rather
  than a positive link.

## A second, distinct tagged variable-width masking scheme found nearby (separate from the SystemAddress mask)

Checking the handful of functions in the same address neighborhood as the Wang-hash lookup (`0x143ce8000`–
`0x143cea000`, only 8 functions total) for anything else relevant, `FUN_143ce8800` turned up a **different**
masking scheme from the constant `& 0x7fffffffffffff` (55-bit) mask already confirmed for `SystemAddress`:
```c
local_res8[0] = (1L << (((byte)param_2 & 7) * -3 + 0x2c & 0x3f)) - 1U & param_2;
```
This derives a **variable** bit-width mask from `param_2`'s own low 3 bits (a 0–7 tag value), then masks `param_2`
down to that many low bits. The widths for tag values 0–7 work out to **44, 41, 38, 35, 32, 29, 26, 23 bits**
(each 3 less than the last) — a tagged/categorized ID scheme where 3 low bits select a category and the
remaining bits (shrinking by 3 per category) hold an index, feeding a **two-level nested hash-map lookup**: the
masked value is Wang-hashed into a first table (`param_1+0x40`/`+0x48`) to get a sub-table `lVar3`, then the
**original, unmasked** `param_2` is Wang-hashed again into that sub-table (`lVar3+0x10`/`+0x18`) to get the final
value via `FUN_1405c0c00`.

**This is explicitly flagged as a separate, not-yet-connected finding** — it's structurally similar (same Wang
hash, same two-level nested-table shape as the `SystemAddress`-rooted lookup documented above) but uses a
different masking formula entirely, so it should not be assumed to be the same ID namespace as `SystemAddress`/
`BodyID` without further tracing of what calls `FUN_143ce8800` and what `param_2` represents there. Recorded here
as a real, verified algorithm (the shifting-width tag scheme is unambiguous from the decompiled constants) for
future reference, not folded into the `SystemAddress` conclusions above.

## Both remaining identity-trace attempts dead-end on the same obstacle: virtual dispatch, no RTTI

Two follow-ups were tried to close the last gaps (confirming `body_object+0x18`'s identity, and identifying
`FUN_143ce8800`'s `param_2`):
1. Looked for direct callers of `FUN_143cd0400` (the async task whose `Update`-style method builds the terrain
   seed) to find where the task — and its key field at `+0x78` — gets constructed/queued. All references found
   are **data references from vtables**, not call instructions: this function is a virtual method, invoked only
   through indirect/polymorphic dispatch, so there is no direct call site to trace back to a constructor this way.
2. The same pattern repeats for `FUN_143ce8800`: its only references are two more data/vtable entries, confirming
   it's also a virtual method (likely shared, inherited, unoverridden behavior across multiple otherwise-distinct
   subclasses, which is why multiple unrelated vtable slots point at the same implementation).

Both dead-end on the same underlying obstacle: this binary's RTTI is almost entirely stripped (only ~24 RTTI
structures exist in the whole binary, found and checked in an earlier pass — none matching these classes), so
there's no practical way to enumerate "which vtables point here" or reconstruct the owning class's layout without
a full manual data-segment sweep for vtable arrays (scanning for contiguous runs of code pointers and
cross-checking each slot) — a substantially larger undertaking than this pass, and a reasonable stopping point
for this specific sub-investigation. The `SystemAddress`-rooted seed-derivation conclusion stands as
"substantially confirmed" (per the capstone `GetStellarForgeBodyInfo` finding above); full bit-for-bit identity
of `body_object+0x18` remains the one open item, now understood to require vtable/RTTI reconstruction work
rather than more call-chain tracing to close.

## Wang hash confirmed as the engine's general-purpose default integer hash: found a 4th occurrence

Decompiled `GetRandomGenerator`'s real implementation too (`FUN_1429e7bb0`, found via its Lua registration entry
`&LAB_1429e7bb0` — another `LAB_`-prefixed address needing `CreateFunctionCmd`, same as `GetStellarForgeBodyInfo`).
When called with no explicit seed argument, it:
```c
puVar3 = FUN_14054d670(&uStack_18, 0);         // fills {seconds, nanoseconds} from the wall clock
uVar4 = *puVar3 * 0x40000 + ~*puVar3;          // the exact same Wang 64-to-32 hash, applied to the seconds value
uVar4 = (uVar4 >> 0x1f ^ uVar4) * 0x15;
uVar4 = (uVar4 >> 0xb  ^ uVar4) * 0x41;
uVar5 = (uint)(uVar4 >> 0x16) ^ (uint)uVar4;   // -> default RNG seed
```
`FUN_14054d670` was also decompiled: it's a `GetSystemTimeAsFileTime`-based wall-clock reader, normalizing the
Windows `FILETIME` into a `{seconds, nanoseconds}` pair (a `std::chrono::system_clock`-style timespec
conversion) — i.e. this is the engine's equivalent of `srand(time(NULL))`, except hashing the raw timestamp
through Wang's hash instead of using it directly.

This is the **fourth** confirmed occurrence of the identical Wang-hash sequence in this binary (terrain seed,
the generic ID-keyed hash-table bucket function, and now the default Lua RNG seed), on top of the second,
differently-masked scheme found separately. This settles any doubt about whether the terrain-seed's use of Wang
hash was a special, Stellar-Forge-specific algorithm — it's clearly a shared, general-purpose default-hash
utility (very likely a single inlined header function) used throughout the engine wherever an arbitrary 64-bit
value needs decorrelating into a 32-bit value, consistent with (not a coincidence weakening) the terrain-seed
conclusion: using this same utility on `SystemAddress`-rooted input is exactly what this codebase does by
convention, everywhere.

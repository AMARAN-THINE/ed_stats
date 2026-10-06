# Stellar Forge terrain noise — implementation spec (as reverse-engineered)

Consolidated, implementation-oriented extract of the findings in `gpu-terrain-shaders.md`. This is **not** a
drop-in replacement for the game — several pieces are unconfirmed or only partially traced (marked below) — but it
is a concrete starting point for an independent reimplementation, built entirely from disassembled/decoded shader
bytecode, cross-validated across 2 shader files.

## Confidence key
- **Confirmed**: extracted directly from bytecode (opcode + operand + constant), cross-validated across 2 files.
- **Probable**: structure is clear from bytecode; exact numeric role inferred, not independently verified.
- **Unresolved**: flagged gap, not guessed.

## 1. Grid setup — Confirmed structure, Probable exact roles
```
cellIndex      = dispatchThreadID + cb0[0]
(gridX, gridY) = divmod(cellIndex, cb4.x)          // cb4.x = grid width
worldPos       = float(gridX, gridY) * cb4.zw + cb4.y
```

## 2. Per-corner hash — Confirmed
For each of 4 corners (loop bound `counter >= 4`), given integer axis coordinate `c` and seed `s = cb2[0]`:
```
h = c * AXIS_CONST[axis]            // AXIS_CONST ∈ {3635633, 15452791}, Probable: per-axis, not fully enumerated
h = h * 11710013 + h
h = s  * 13953839 + h
h ^= h >> 15
h  = h * 374761393                  // = XXH_PRIME32_5 (public xxHash32 constant) — Confirmed
h ^= h >> 13
// second avalanche pass (same shape) observed chained — Probable: full xxHash32 round, not independently verified
gradientIndex = h % 12
```

## 3. Gradient table — Confirmed, extracted directly from shader ICB data
```
GRADIENTS_3D = [
  ( 1, 1, 0), (-1, 1, 0), ( 1,-1, 0), (-1,-1, 0),
  ( 1, 0, 1), (-1, 0, 1), ( 1, 0,-1), (-1, 0,-1),
  ( 0, 1, 1), ( 0,-1, 1), ( 0, 1,-1), ( 0,-1,-1),
]
```
This is the standard public 12-edge Perlin gradient set (not Frontier-original).

## 4. Corner weight — Confirmed shape, Probable exact constant
```
d = dot(offset, offset)      // offset = sample position - corner position
t = max(0, d + 0.5)          // Probable: sign/constant not independently re-derived from first principles
t = t * t * t * t             // t^4 — classic simplex-noise falloff
contribution = t * dot(GRADIENTS_3D[gradientIndex], offset)
```

## 5. Combine corners — Confirmed opcode (DP4), Unresolved exact weight vector construction
```
noise = dot4(weights, contributions)   // weights = [t0^4, t1^4, t2^4, t3^4] per corner, Probable
```

## 6. Octave loop — Confirmed
```
octaveCount = cb1[80]              // data-driven, read from the large per-planet parameter buffer
sum = 0
for i in range(octaveCount):
    octaveParam = cb3[0] * cb1[i]  // Probable: frequency/amplitude multiplier, exact semantics unresolved
    sample      = worldPos * cb2[0] + octaveParam   // Probable
    sum += evaluate_noise(sample)  // steps 2–5 above, re-evaluated per octave
```

## 7. Post-noise remapping — Confirmed (re-traced from raw bytecode; supersedes the earlier guessed formula)

Two separate remap sites exist, both keyed on the same `*77.0` normalization constant.

**Single-octave pre-loop correction:**
```
raw  = dot4(weights, contributions)     // single-octave DP4 combine, step 5
n    = raw * 77.0                       // normalize into ~[-1, 1]
t    = n * 0.5 + 0.5                    // -> [0, 1]
s    = t * 0.8 + 0.2                    // -> [0.2, 1.0] for in-range t; goes negative only if n < -1.0
if 0 < s:
    n = n * 2.0                         // double amplitude when the normalized value is in-range
```

**Final post-octave-loop shaping (genuine smoothstep):**
```
total = sum * 77.0                      // sum = accumulated multi-octave DP4 total, step 6
t     = (total + 1.0) * 0.5             // -> [0, 1]
curveA = t*t * (3.0 - 2.0*t)            // = 3t^2 - 2t^3, canonical smoothstep(t)
curveB = <second, differently-weighted smoothstep-shaped term, same t>  // Probable, see below
result = (curveA + curveB) * CB[3][21]  // CB[3][21]: per-call runtime scale constant
```
`curveB` uses constants `0.1`, `0.6667` (`2/3`), `0.3333` (`1/3`) over the same normalized `t`/derived values —
clearly a second cubic/Hermite-family term blended with `curveA`, but its exact closed form and purpose (most
likely a separate channel such as material blend or a secondary height-curve weight) were not fully isolated in
this pass.

The earlier `38.5`/`1/60`/`1/120` constants reported in a prior pass were a misread of an ephemeral,
not-saved disassembly run and do not appear in this re-traced, saved instruction sequence — this entry
supersedes that one.

## 8. Output — Probable (revised once)
A single double-precision value (height), written as two 32-bit halves to a structured UAV at byte offsets 0 and 16
of the output record.

## What's needed to go further
1. Isolate `curveB`'s exact closed form in step 7's final shaping (the second smoothstep-like term blended with
   `curveA`) and its purpose — most likely a second output channel (material/biome weight) rather than a height
   correction, given it's blended additively before the single `CB[3][21]` scale rather than branched on.
2. Confirm step 5's weight-vector construction (`TEMP9`'s role across all 4 corners, not just one).
3. Determine `AXIS_CONST` assignment per axis (x/y/z) definitively — only 2 constants (`3635633`, `15452791`) were
   found directly; a search for a third distinct per-axis constant this session instead found `30798437` recurring
   identically across multiple hash computations (so it's a general finalization-round constant, not axis-specific)
   and `3184315597` used in an unrelated threshold comparison (`CB[1][12]`) with nothing to do with the hash. The
   third axis constant, if one exists, was not found.
4. Apply this same tracing to the large (~200K-instruction) permutations to find per-planet-class branches (basin,
   mountain, crater features documented in `stellar-forge-struct.md` presumably select different code paths or
   parameter sets not present in this smallest/simplest permutation).
5. Separately: the CPU-side `SystemAddress`/`BodyID` → seed derivation remains unlocated (see `codex-journal.md`/
   `stellar-forge-struct.md` for the dead-end log) — without it, this spec can evaluate noise for an arbitrary seed,
   but not derive the correct seed for a given real system.

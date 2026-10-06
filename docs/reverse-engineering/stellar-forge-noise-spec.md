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

## 2. Per-corner hash — Confirmed, including AXIS_CONST resolution
For each of 4 corners (loop bound `counter >= 4`), given an integer 2-component coordinate `(cx, cy)` and seed
`s = cb2[0]`:
```
(hx, hy) = (cx, cy) * (3635633, 15452791)   // single SIMD IMUL, both constants applied as two lanes of one
                                              // vector op — not two separately-selected per-axis constants
h = hx + hy                                  // IADD combines both lanes into scalar h
h = h * 11710013 + h
h = s  * 13953839 + h
h ^= h >> 15
h  = h * 374761393                  // = XXH_PRIME32_5 (public xxHash32 constant) — Confirmed
h ^= h >> 13
// second avalanche pass (same shape) observed chained — Probable: full xxHash32 round, not independently verified
gradientIndex = h % 12
```
**`AXIS_CONST` resolved:** there is no missing third axis constant. The `IMUL` instruction producing this hash
input uses a single 4-component immediate `(3635633, 15452791, 0, 0)` applied in one op to a 2-component integer
coordinate — consistent with step 1's grid setup, which is already `(gridX, gridY)` only. This confirms the
lattice this kernel evaluates is genuinely 2D (a heightfield), not a 3D volumetric noise field; a third axis
constant was never missing, it simply doesn't exist for this kernel.

## 3. Gradient table — Confirmed, extracted directly from shader ICB data
```
GRADIENTS_3D = [
  ( 1, 1, 0), (-1, 1, 0), ( 1,-1, 0), (-1,-1, 0),
  ( 1, 0, 1), (-1, 0, 1), ( 1, 0,-1), (-1, 0,-1),
  ( 0, 1, 1), ( 0,-1, 1), ( 0, 1,-1), ( 0,-1,-1),
]
```
This is the standard public 12-edge Perlin gradient set (not Frontier-original).

## 4. Corner weight — Confirmed, register-traced in full (dword offset 428–561)
```
offset[4 corners] = TEMP4, TEMP6, TEMP8, TEMP9   // one 3-component offset vector per corner
d[i] = dot(offset[i], offset[i])                 // DP3, one per corner, all written into TEMP10's 4 lanes
t[i] = max(0, d[i] + 0.5)
t[i] = t[i]^2
t[i] = t[i]^2            // t^4 total — classic simplex-noise quartic falloff, now confirmed per-corner in TEMP10
contribution[i] = dot(IMM_CBUFFER[gradientIndex[i]], offset[i])   // DP3, one per corner, all written into TEMP5
```

## 5. Combine corners — Confirmed opcode and operands, fully resolved
```
noise = dot4(TEMP10, TEMP5)   // TEMP10 = [t0^4..t3^4] weight vector, TEMP5 = [contribution0..3] gradient dot products
```
(Corrects the earlier "Unresolved exact weight vector construction" / "TEMP9's role" note: `TEMP9` is just the
4th corner's offset vector, not the weight accumulator — `TEMP10` holds the weight vector, confirmed by tracing
all 4 `DP3` writes into it before the final `DP4`.)

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

**Final post-octave-loop shaping (genuine smoothstep) — fully confirmed by register-level trace:**
```
total  = sum * 77.0                      // sum = accumulated multi-octave DP4 total, step 6
t      = (total + 1.0) * 0.5             // -> [0, 1]
A      = t*t * (3.0 - 2.0*t)             // = 3t^2 - 2t^3, canonical smoothstep(t)
result = 0.1*A + (0.1*A + 1.0)*(0.1*A + 1.0)
result = result * CB[3][21]              // CB[3][21]: per-call runtime scale constant
```
A separate `0.5`/`0.6667`(`2/3`)-weighted quartic block (computed from the pre-squared `(3-2t)` term) was traced
in parallel and found to be **dead code**: its result is written to the same register the line above overwrites
before any instruction reads it. This was reported as a "second blended smoothstep term" in an earlier pass of
this file — that was wrong; corrected here after tracing every subsequent read of the register in question. Most
likely a compiler/shader-permutation-template artifact, not a real second term.

## 8. Output — Probable (revised once)
A single double-precision value (height), written as two 32-bit halves to a structured UAV at byte offsets 0 and 16
of the output record.

## What's needed to go further
1. ~~Apply this same tracing to the large permutations to find per-planet-class branches~~ — **attempted,
   inconclusive but informative.** Scanned the large Nvidia-variant permutation's full operand-decoded output
   (`terrain_nv_operands_full3.txt`, 1,794 `IF`/`ENDIF` pairs) for comparisons feeding branch conditions. Every one
   found is a comparison between `TEMP` registers (intermediate, computed values) and small integer literals
   (`0`, `1.0`), never a direct `CB[n][m]` constant-buffer read. This is the opposite shape of what a discrete
   "planet class selector" branch would look like (which would compare directly against a class/feature-flag
   constant from the per-planet parameter buffer). The more likely explanation, consistent with this file already
   containing multiple separately-compiled DXBC chunks of wildly different sizes (28KB to 5.9MB, documented in
   `gpu-terrain-shaders.md`), is that **planet-class/feature specialization happens via CPU-side shader-variant
   selection** (dispatching a different compiled permutation entirely) rather than via internal runtime branches
   in one shader — the 1,794 `IF`s observed are far more likely numerical edge-case handling from aggressive loop
   unrolling (e.g. degenerate corner cases, divide-by-zero guards) than class dispatch. Not proven, but this is
   the evidence-backed working hypothesis; a full per-branch trace to rule out any class-selector shape entirely
   would need far more register tracing than this pass did.
2. Separately: the CPU-side `SystemAddress`/`BodyID` → seed derivation is now substantially resolved — see
   `stellar-forge-struct.md`'s "Seed derivation located" section: the seed is a Thomas Wang 64-to-32 hash of a
   64-bit body-object field, confirmed by an exact struct-offset match. A capstone finding via
   `GetStellarForgeBodyInfo`'s real implementation confirmed the same hash-table lookup used to build the seed
   is keyed by a composite 64-bit value whose low 55 bits are explicitly validated as `SystemAddress` (with the
   remaining ~9 bits a body-within-system index) — so `Seed = WangHash64to32(SystemAddress | bodyIndex<<55)` is
   now a well-evidenced, near-conclusive formula, one direct identity trace short of fully airtight (see
   `stellar-forge-struct.md` for the exact remaining caveat).

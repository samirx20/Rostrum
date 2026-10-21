# rostrum2d-stamp: the painting kit's dabs, native

A small library (`rostrum2d_stamp.dll`, `.dylib` on the Mac) that lays a planned brush stroke into a paint layer with
**the same pixels as the painting kit's numpy engine, bit for bit**, about ten times faster. The kit
(`shared/painting-kit`, Team Sam's) plans each stroke as before (the path, the random draws, the tip profiles, every
dab's numbers: `brush.plan`) and hands the dabs to this library through its `native.py` (ctypes). Because the pixels
are identical, the kit's replay, undo and pixel cache stay exact whether a machine has the library or not.

## How it stays identical

numpy mixes float32 and float64: an f32 array with a Python number stays f32, an f32 array with an f64 array or a NumPy
scalar becomes f64 (NEP 50). Every step here is written in the precision numpy uses for it, in the same order, never
fused or reordered (Rust doesn't contract `a * b + c`). Things whose result depends on a maths library (cos, sin, hypot,
powers) are computed in Python by the plan and passed in. One detail decides the wet reservoir: numpy takes it up in
f32 when the take-up amount is a Python number and in f64 when it is a NumPy scalar, which depends on the dab; the plan
says which (`take_weak`).

| File | Job |
|---|---|
| `src/lib.rs` | the C entry `rostrum2d_stamp_dabs`, the layout of the numbers it reads (`LAYOUT`, `P_*`, `DAB`) |
| `src/stroke.rs` | a stroke's dabs in order, the wet reservoir |
| `src/tip.rs` | one pixel's coverage per tip (round, bristle, chalk, flat, block, line), grain, mask |
| `src/paint.rs` | paint meets the layer (normal, multiply, erase, screen, add) |

## Build

```
pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "<team>: stamp build" build ^
  cargo build --manifest-path apps\2d\engine\Cargo.toml --release -j 4 -p rostrum2d-stamp
```

No dependencies; builds in seconds. The kit looks for it at `ROSTRUM_STAMP_LIB`, else
`apps\2d\engine\target\agent\rostrum2d_stamp.dll` in the same checkout. `--release` is ~20 % faster than the agent build.

## Measured (H8)

1080p layer, 20 bristle strokes 8–40 px each, stamping only, numpy vs native; every layer byte-identical
(`C:\Users\Sam\.rostrum\waves\results\stage2\2d-engine\native-stamp-vs-numpy-h8.json`, driver
`proofs/2d-native-stamp/judge.py`):

| Batch | numpy | native | |
|---|---|---|---|
| short pen strokes (~250 px) | 0.63 s | **0.06 s** | 10× |
| long sweeps (~3,500 px) | 9.6 s | **0.85 s** | 11× |
| long wet sweeps (smudge, half picking up) | 47.4 s | **4.0 s** | 12× |

What is left in the native time: about a quarter is the plan in Python (path resampling, random draws); the rest is
the dabs. Wet strokes lay three times as many dabs, each also reading and updating the brush's reservoir.

## Judged

`proofs/2d-native-stamp/judge.py`: 53 strokes (every tip in every mode, wet, picking up the layers below, grain, a
mask, off both edges, a dot, a fixed angle, jitter, pressure) onto one evolving layer three ways: the kit as on main,
the patched kit's numpy, the native stamper. Every coverage and every layer byte equal. The kit's own tests (replay,
undo, landed, script re-run) pass with the native stamper on, plus the kit test the patch adds (`test_native.py`).

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
powers) are computed in Python by the plan and passed in, except in the spacing walk below. One detail decides the wet reservoir: numpy takes it up in
f32 when the take-up amount is a Python number and in f64 when it is a NumPy scalar, which depends on the dab; the plan
says which (`take_weak`).

| File | Job |
|---|---|
| `src/lib.rs` | the C entries `rostrum2d_stamp_dabs` and `rostrum2d_stamp_straight8` (premultiplied float -> straight RGBA8 for a box, `compose.straight8`'s bytes), `rostrum2d_stamp_spacing` and `rostrum2d_stamp_fill` (below), the layout of the numbers it reads (`LAYOUT`, `P_*`, `DAB`) |
| `src/stroke.rs` | a stroke's dabs in order, the wet reservoir (on a seamless canvas it picks up across the joined edges, and a dab's other parts reuse its pick-up: the kit's `wrap.py`); the fast paths below |
| `src/tip.rs` | one pixel's coverage per tip (round, bristle, chalk, flat, block, line), grain, mask; `reach`, the columns of a row the tip's shape can cover |
| `src/paint.rs` | paint meets the layer (normal, multiply, erase, screen, add) |

## A stroke in pieces (layout 5)

The kit lays a live stroke a piece at a time (`brush.stamp_stroke`'s `piece`): each call gets only that piece's dabs,
and the wet reservoir as the last piece left it (`res`, D×D×4, with `P_RES_IN`); it is written back after the last
dab. The stroke's ends (a block's ragged ends) come from the whole stroke in `P_R0`, `P_RL`, `P_LENGTH`, not from the
piece's first and last dab.

## The spacing walk and the fill

Two per-dab and per-pixel loops of the kit's Python, here because a look at a big hand-painted piece spent seconds in
them (production round, 2026-10-27): `rostrum2d_stamp_spacing` is `brush._spacing` (where a stroke's dabs go: a
step per dab, its taper's `shape.step_scale`), in f64 like Python's floats, its ties broken as Python's `max` / `min`
break them; `rostrum2d_stamp_fill` is `marks.apply_paint` for a fill (normal, from no coverage), in numpy's f32 steps.
The taper's sine and power are the C library's here, as Python's `math.sin` and `**` are; the kit's tests compare the
walk with the Python on hundreds of strokes (`tests/test_native.py`), so a library that rounds differently shows
there. They came after layout 5 without changing its calls: an older build lacks them and the kit uses its Python
(`native.walks()`), the same numbers.

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

## Big brushes: the same pixels, less work

A 260 px brush lays dabs of ~70,000 px, and a hard one lays 1,200 of them a stroke. Three things make that fast
without changing a pixel (`stroke.rs`):

- **Only the tip's shape.** A row's pixels outside the ellipse round the tip's shape (`tip::reach`: the circle of a
  round tip, the bristle's own narrow ellipse) get coverage 0, which leaves the pixel as it is: skipped. Not for the
  modes where coverage 0 still rounds the pixel (multiply and screen over coverage already laid, add).
- **Nothing to add.** A dry dab in a mode that steps by the coverage's growth (normal, erase, overlay, soft light,
  colour) leaves a pixel the stroke already covers at least as much as the dab can (its strength × tip picture ×
  mask; 1 with grain) as it is: skipped without working out the coverage. Dense dabs change only a thin crescent.
- **Threads.** A stroke with enough work (64k px, dabs over 2k px) is laid by up to 8 threads, each owning every
  T-th band of 4 rows: a pixel's result depends only on itself, so dry dabs never wait; a wet dab's pick-up, laying
  and take-up wait for each other (a short spin, twice a dab).

`shared/painting-kit/tests/test_native.py` checks big overlapping dabs (threads, both skips) against numpy byte for
byte. One stroke of 100 points across a 2560 × 768 layer, stamping only:

| Brush | before | after |
|---|---|---|
| hard round 260 px (1,205 dabs) | 2,084 ms | 44–60 ms |
| wet bristle 260 px (287 dabs) | 684 ms | 78–90 ms |
| soft round 260 px | 207 ms | 26–30 ms |
| hard round 40 px | 180 ms | 30 ms |

## Judged

`proofs/2d-native-stamp/judge.py`: 53 strokes (every tip in every mode, wet, picking up the layers below, grain, a
mask, off both edges, a dot, a fixed angle, jitter, pressure) onto one evolving layer three ways: the kit as on main,
the patched kit's numpy, the native stamper. Every coverage and every layer byte equal. The kit's own tests (replay,
undo, landed, script re-run) pass with the native stamper on, plus the kit test the patch adds (`test_native.py`).

# rostrum-color

Rostrum's one colour library (pure Rust, no runtime deps). It holds the CPU reference for every colour
path: transfer functions, gamuts and CATs, `convert(src, dst)`, `.cube` LUTs, and the view transforms.
Design: `docs/phase0/COLOUR_PIPELINE.md`, `docs/phase0/COLOUR_WAVE_B.md`. Oracle contract: `ORACLE.md`.
Third-party notices (the views are ports): `NOTICE`.

## Modules
| module | what |
|---|---|
| `tf` | `Curve`: linear ↔ code for sRGB, Rec.709, BT.1886, PQ (`pq` 1.0 = 10 000 nits, `pq100` 1.0 = 100 nits), HLG, ACEScc, ACEScct, S-Log3, LogC3 (EI 800), LogC4, Log3G10, BMD Film Gen5, Canon Log 2 / 3, V-Log and Apple Log. Each curve cites its source document. |
| `matrix` | 3×3 maths, RGB → XYZ from primaries, `Cat` (Bradford, CAT02, von Kries) |
| `spaces` | `Gamut` and `Space` registries. Ids follow ORACLE.md. Each gamut adapts to the ACES white with OCIO's CAT for it. |
| `convert` | `convert(src, dst) -> Transform` (decode → matrix → encode), plus `inverse()` and `apply_all()` |
| `lut` | `Lut1d` / `Lut3d` (linear; trilinear or tetrahedral), `bake`, the one `.cube` reader and writer |
| `view` | `View::get(id)` / `resolve(id, target)`: `forward(acescg, target)` → display linear in the target's primaries (1.0 = 100 nits), `inverse(display, target)` → ACEScg, `forward_all` / `inverse_all`; `Target::{Sdr, Hdr1000}` |
| `grade` | the one grade (C7): `Grade { ops, mix }` on ACEScg; `apply` / `apply_all` (CPU reference), `sksl()` + `uniforms()` + `lut_images()` (compositor colour filter), `bake(size, in, out, view?)` → `.cube` |
| `scope` | scopes (G2): `Frame` in a `Domain` (display after the view, ACEScg, ACEScct), `measure` → the §7.2 JSON (under 3 KB: luma percentiles and zones, clipped, balance with castRG / castBY, parade, vectorscope numbers and the skin line, bands, warnings, optional histogram), `compare::diff` (+ ΔE2000), `draw` the pictures (waveform, parade, vectorscope with Rec.709 targets, histogram, CIE chromaticity, false colour, a sheet) with our own 5×7 font; `Region` (a rectangle in frame fractions; `Mask` is the seam for G4 window shapes) |

## The grade
Operations, in the caller's order (definitions and maths in `src/grade/mod.rs`): **linear ACEScg**: `Exposure`
(stops), `WhiteBalance { kelvin, tint }` (CAT02 from the light's white, Krystek 1985 Planckian + tint / 3000 Duv, to
6500 K; 6500 / 0 is the identity; + kelvin warms, + tint goes magenta), `Offset`; **ACEScct**: `LiftGammaGain` (rgb +
master, between black / white codes, default linear 0 and 1.0), `Contrast { contrast, pivot }`, `Saturation`
(AP1 luminance or Rec.709 luma weights), `Curves` (master, r, g, b tables over code 0 … 1, slope 1 beyond); **LUT
nodes** (`LutNode::new(lut, interp, in, out)`: ACEScg → `in`, the table, `out` → ACEScg); then `mix` over the
ungraded light. Runs of ACEScct operations share one encode / decode.

- **SkSL**: one colour filter on premultiplied ACEScg; parameters are uniforms (`grade[]`, `curves[]`), so the code
  only changes with the structure; LUTs are `uniform shader lut<i>` children (float images, raw and nearest);
  curve tables are read with loops (ES2), M iterations per pixel for M curve samples. Every `tf` curve has an SkSL
  encode / decode (`Curve::sksl`) for the LUT nodes' spaces. Untested here (no Skia); the parity test lives in
  `rostrum-motion`.
- **Bake**: `bake(33 | 65, "acescct", out, Some((view, target)))` writes `in:` / `out:` / `view:` in the header
  comments. Exact on the grid nodes; between them the 3D interpolation error over plausible pictures (tests/grade.rs,
  `--nocapture`): the grade alone ≤ 0.003 ACEScct code (33³), 0.002 (65³); with a view the error is the view's own
  near display black and at the gamut edge (a minor channel of ACEScg → display swept across a 0.55-stop cell),
  tens to a few hundred 10-bit codes there at 33³, about half at 65³, as for any 3D LUT of a gamut change sampled in log.

## Views
| id | targets | method and source | inverse |
|---|---|---|---|
| `neutral` (default) | sdr, hdr1000 | Khronos PBR Neutral (Apache-2.0), bit-identical to `rostrum-3d`'s. hdr1000: BT.2408 style, graphics white = 203 nits, the curve scaled to an asymptote of 1000/203 graphics whites (identity below 761 nits). | closed form; display at or above half a 10-bit code below the peak is capped there (SDR white → scene ≈ 49.7, HDR 1000 nits → ≈ 66). Exact for scenes with no negative Rec.709 channel; bright saturated displays (and in HDR, colours outside Rec.709) are unreachable. |
| `aces2` | sdr (Rec.709-limited, 100 nits), hdr1000 (P3-D65-limited, 1000 nits, Rec.2020 container) | ACES 2.0 output transform, ported from OpenColorIO 2.5.2's implementation (BSD-3) of the Academy CTL (`aces-aswf/aces-output`, Apache-2.0); f32 in OCIO's operation order; per-hue tables built once per target (`OnceLock`) | OCIO's analytic inverse |
| `agx` | sdr | Filament's matrices and log2 range (Apache-2.0) with three.js's sigmoid polynomial (MIT); bit-identical to `rostrum-3d`'s `agx`. Filament's own 7th-degree polynomial is not monotonic on [0, 1] and differs by up to 17 sRGB codes, so it is not used. | analytic, Newton (f64) on the polynomial; exact where no forward clamp acts (inset channels within 2^−12.47 … 2^4.03, display within [0, 1]); greys above ≈ 0.997 are unreachable |
| `standard` | sdr | ACEScg → Rec.709, clip to [0, 1] | the matrix (no clip) |
| `aces-legacy` | sdr | three.js's ACES filmic fit (MIT), bit-identical to `rostrum-3d`'s `aces` | closed form (quadratic per channel); white inverts to a finite scene |

A target a view lacks is a loud error naming the views that have one (`View::resolve` / `check`; `forward` panics).

**SkSL** (`View::sksl_inverse(target)` / `sksl_forward`, for the compositor): each view as a colour filter
`half4 main(half4 c)`, premultiplied in and out, generated from the same constants as the CPU code; ACES 2.0 also
returns its five 363-float uniform tables. Untested here (no Skia in this crate). Skia's runtime effects are
ES2-strict, so ACES 2.0 reads its tables with full loops (~730 iterations per pixel): correct, not fast; an image
child for the tables is the faster follow-up.

ACES 2.0 against the oracle (OCIO 2.5.2, F32), in 10-bit codes: BT.1886 2.4 for sdr, PQ for hdr1000, inverse outputs as
ACEScct codes. 20 000 samples per case (`golden.py --measure`; sample sets in ORACLE.md §View cases). Targets were
forward ≤ 0.25 and round trip ≤ 0.5.

| target | forward max / p99.9 / mean | inverse max / p99.9 / mean | round trip (display → inverse → forward) max |
|---|---|---|---|
| sdr | 0.027 / 0.012 / 0.0003 | 0.009 / 0.005 / 0.0003 | 0.18 over the display cube (19 978 of 20 000 below the cap); 0.057 over the forward's image |
| hdr1000 | 0.012 / 0.003 / 0.0001 | 0.069 / 0.012 / 0.0004 | 0.025 over P3 ≤ 1000 nits (19 987 of 20 000; the other 13 need a negative AP1 scene, which the inverse clamps, and OCIO's own round trip misses them by the same up to 3.5 codes); 0.017 over the forward's image |

Round trips of the other views (same sample sets): neutral 0.006 (sdr) / 0.0004 (hdr1000) codes inside its range,
0.002 over the forward's image; agx 0.009, standard 0.004, aces-legacy 0.002 over the forward's image.
Code differences of display values below 0.01 nit are not counted (f32 noise there is several PQ codes).

Speed, release, one thread, best of 3 over 2^20 pixels (`speed`, ns per pixel, forward / inverse): neutral 17 / 63 (sdr),
27 / 101 (hdr1000); aces2 443 / 464 (sdr), 470 / 490 (hdr1000); agx 90 / 338; standard 5 / 4; aces-legacy 12 / 33.
ACES 2.0 is dominated by ~18 `powf` per pixel (the model's cone compression, tonescale and hull), as in OCIO.

## Behaviour worth knowing
- **CAT per gamut:** OCIO's ACES studio config uses Bradford for display and working gamuts, RED RWG and Panasonic V-Gamut. It uses CAT02 for Sony, ARRI, Blackmagic and Canon. Every conversion goes through the D60 hub, so any pair matches OCIO.
- **sRGB / Rec.709** are evaluated as OCIO's moncurve: the power is fixed, and the linear toe is chosen to meet it in value and slope. The Rec.709 toe slope is therefore 4.5138 with its break at code 0.081, not the spec's rounded 4.5 and 0.018. Above the break both use 1.099·L^0.45 − 0.099. On the toe the code is 0.3 % higher (up to 2.5e-4 near the break), and that gap grows with |x| on negatives. Negatives continue the toe.
- **BT.1886** is a pure 2.4 power. Negatives pass through unchanged (OCIO `pass_thru`: −0.01 stays −0.01, not clamped to 0, not mirrored).
- **Clamps:** ACEScc has a floor at linear ≤ 0 and caps decode at 65504. Apple Log encodes 0 below R0. PQ and HLG mirror negatives. NaN propagates through every curve. ±inf never produces NaN.
- **Views:** ACES 2.0 follows OCIO: NaN renders black (OCIO's clamps map NaN to 0), input is clamped to AP1 [0, 8·r_hit]. Neutral, AgX and the legacy fit keep their published NaN behaviour.
- **LUTs:** input outside the domain clamps to its edges. `Cube::write` is canonical (shortest round-trip floats), so read → write → read is byte-stable.

## Tests and tolerances
`cargo test --release -p rostrum-color` (in `native/`):
- `tests/golden.rs` runs every case in `tests/fixtures/golden.json` and prints a max abs / rel table.
  - Analytic transforms are held to 1e-5; `view.aces2.*` to 0.25 / 1023 of a code.
  - `measure_views` (ignored) prints the ACES 2.0 table above from `golden.py --measure`.
- `tests/roundtrip.rs`: curve and space round trips, special floats, and every view's display → inverse → forward
  (the display cube, and the forward's image), in 10-bit codes with display linear below 0.01 nit not counted.
- `tests/views.rs`: the API, Neutral against `rostrum-3d` and its HDR shape; `speed` (ignored) prints ns/px.
- `tests/views_ref.rs`: AgX and the legacy fit against `rostrum-3d`, three.js and Filament values.
- `tests/cube.rs` covers `.cube` stability and errors, and bake → apply.
- `tests/grade.rs`: grade identities, white-balance directions, mix and curves, the SkSL structure and uniform
  layout, LUT images, and grade bake → apply (plus `.cube` byte stability); `grade.*` oracle cases run in `golden.rs`.

## Regenerating the oracle
The oracle is dev-only, never shipped. See `scripts/color-oracle/README.md`. In a venv outside the repo, run `pip install -r requirements.txt`, then `python -I -B golden.py` (and `notice.py` for `NOTICE`). That rewrites `tests/fixtures/`. Never edit those by hand. A mismatch is fixed in the maths here, never by loosening a tolerance.

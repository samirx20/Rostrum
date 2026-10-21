# rostrum-color ↔ oracle contract (Phase 0, C0 / C1 / C2)

The oracle (`scripts/color-oracle/`, dev-only Python, PyOpenColorIO + colour-science in a venv outside the
repo, never shipped) writes the files below. The crate's tests read them. Design: `docs/phase0/COLOUR_PIPELINE.md`.

## Files
| File | What |
|---|---|
| `tests/fixtures/golden.json` | golden vectors (≤ 200 KB) |
| `tests/fixtures/lut3d_17.cube`, `lut1d_1024.cube` | test `.cube` files with OCIO's own evaluation in `golden.json` |
| `NOTICE` | third-party notices of the code the views are ported from (`notice.py`) |
| `data/charts.json` | reference chart values (ColorChecker 24, ramps, primaries, bars), see §Charts |

## Conventions
- Linear values are scene- or display-linear, **1.0 = 100 nits** for display light, except PQ (`tf.pq.*`),
  whose linear side is ST 2084 absolute: 1.0 = 10 000 nits.
- Space ids: `acescg` (AP1, D60), `aces2065` (AP0, D60), `lin_rec709`, `lin_rec2020`, `lin_p3d65`, `xyz_d65`,
  and camera gamuts `sgamut3`, `sgamut3cine`, `awg3`, `awg4`, `rwg`, `bmd_wg5`, `cinema_gamut`, `vgamut` (Apple Wide Gamut exists only in OCIO 2.6 / config v5; Apple Log is covered by `tf.applelog` and `cs.applelog_rec2020.acescg`).
- White-point adaptation between D65 and D60 uses whatever the ACES studio config uses; the cases
  `cat.*` pin it down (the crate must reproduce `cs.*` within tolerance).

## golden.json
```json
{ "generator": { "ocio": "2.5.x", "config": "<builtin config URI>", "colour_science": "x.y", "date": "…" },
  "cases": [ { "id": "tf.srgb.encode", "kind": "tf|matrix|cs|view|lut", "src": "…", "dst": "…",
               "tol_abs": 1e-5, "tol_rel": 1e-5, "note": "OCIO name(s) used",
               "matrix": [[…],[…],[…]],
               "in": [[r,g,b], …], "out": [[r,g,b], …] } ] }
```
- A value passes when `|ours − out| ≤ max(tol_abs, tol_rel·|out|)`. `matrix` only on `kind: "matrix"`.
- Special floats are strings `"nan"`, `"inf"`, `"-inf"`. Every `tf.*` case includes negatives, 0, tiny,
  mid, 1 and values above 1 (up to 65504 where the curve allows it).
- Evaluation: OCIO 2.5.2, config `ocio://studio-config-v4.0.0_aces-v2.0_ocio-v2.5`, CPU processor at F32 with
  `OPTIMIZATION_NONE`. `tf.*` cases use the curve op alone (gamut matrices dropped); where OCIO uses a LUT or a
  rescale (`acescc`, `clog2`, `clog3`, `pq`, `hlg`) the values come from colour-science in float64 (said in `note`).

### Case ids
- `tf.<curve>.encode` / `.decode` (linear → code / code → linear), curves: `srgb` (IEC 61966-2-1 piecewise),
  `rec709` (BT.709 OETF), `bt1886` (pure 2.4, Lw 1, Lb 0), `pq`, `hlg` (BT.2100 OETF, scene 0..1),
  `acescc`, `acescct`, `slog3`, `logc3` (EI 800), `logc4`, `log3g10`, `bmdfilm5`, `clog2`, `clog3`, `vlog`, `applelog`.
- `matrix.<src>.<dst>` for every gamut above to `acescg` and `xyz_d65`, plus `acescg.aces2065`,
  `acescg.lin_rec709`, `acescg.lin_rec2020`, `acescg.lin_p3d65`.
- `cat.<method>.d65.d60` for `bradford`, `cat02`, `vonkries` (colour-science), as matrices.
- `cs.<input>.acescg`: full input transforms (OCIO colour spaces), e.g. `cs.srgb_tex.acescg`,
  `cs.rec709_display.acescg` (Rec.1886 Rec.709 display), `cs.slog3_sgamut3cine.acescg`, `cs.logc4_awg4.acescg` …,
  and `cs.acescg.<output>` for `srgb_display`, `rec1886_rec709`, `p3d65_display`, `st2084_p3d65_display`.
- `view.aces2.<target>` / `view.aces2.<target>.inv` (`sdr`, `hdr1000`): the true OCIO ACES 2.0 view, §View cases.
- `lut.cube3d_17.tetra` and `lut.cube1d_1024.linear`: OCIO `FileTransform` on the fixture `.cube` files.
- `grade.*` (`kind: "grade"`, ACEScg in and out, 1e-5): the one grade, §Grade.

## Grade (`cases_grade.py`)
Each case carries `"grade": {"ops": [{"op": "exposure", "stops": …}, …], "mix": m}`; `tests/golden.rs` builds the
crate's `Grade` from it. Op JSON: `exposure {stops}`, `white_balance {kelvin, tint}`, `offset {rgb}`,
`lgg {lift, gamma, gain ([r, g, b, master]), black, white}`, `contrast {contrast, pivot}`,
`saturation {saturation, luma: "ap1" | "rec709"}`, `curves {master?, r?, g?, b?}`,
`lut {file, interp, in, out}` (a fixture `.cube`, rostrum-color space ids).

| case | oracle |
|---|---|
| `grade.exposure` | OCIO `ExposureContrastTransform` (LINEAR style, contrast 1) |
| `grade.offset` | OCIO `CDLTransform` (`CDL_NO_CLAMP`, slope 1, power 1) |
| `grade.white_balance.3200`, `.9000_tint` | colour-science float64: `CCT_to_uv_Krystek1985`, the locus normal by central difference, `UCS_uv_to_xy`, `matrix_chromatic_adaptation_VonKries(…, "CAT02")` from the light's white to 6500 K, tint 0, in ACEScg |
| `grade.lgg` | float64 on colour-science ACEScct codes (definition below) |
| `grade.contrast` | OCIO `GradingPrimaryTransform` LOG style between ACEScg ↔ ACEScct `ColorSpaceTransform`s (OCIO's LOG pivot p is the code 0.5 + 0.5 p) |
| `grade.saturation.rec709` | the same OCIO LOG style, saturation (OCIO uses Rec.709 luma) |
| `grade.saturation.ap1` | float64, AP1 luminance weights (colour-science's ACEScg Y row) |
| `grade.curves` | float64 `np.interp` over 17-sample tables, slope 1 beyond code 0 … 1 |
| `grade.lut.creative` | OCIO ACEScg → `Rec.1886 Rec.709 - Display`, `FileTransform` lut3d_17.cube tetrahedral, back |
| `grade.lut.camera` | OCIO ACEScg → `S-Log3 S-Gamut3.Cine`, `FileTransform` trilinear, `Rec.1886 Rec.709 - Display` → ACEScg |
| `grade.full` | every operation in order and mix 0.8: the OCIO pieces above for exposure, offset and the LUT, float64 for the rest |

Lift / gamma / gain (OCIO's `GRADING_VIDEO` differs: its lift is scaled by 1 / (1 + lift) and its gamma pivots on
white, so it is not used): `t = (v − black) / (white − black)`, `t' = lift + (gain − lift) · sign(t)·|t|^(1/gamma)`,
`v' = black + t' · (white − black)`, with lift = rgb + master, gamma = max(rgb × master, 0.01), gain = rgb × master.

## View cases (`cases_view.py`)
The crate's views are analytic (no baked tables). The oracle covers ACES 2.0 only: it is the one view OCIO
defines. Neutral, AgX, Standard and the legacy ACES fit are checked against their published code in
`tests/views.rs` and `tests/views_ref.rs`. No OCIO AgX definition carries a licence (sobotka/AgX and its
forks have none; Blender's is GPL).

| case | `in` | `out` | tol |
|---|---|---|---|
| `view.aces2.sdr` | ACEScg | `bt1886` code (pure 2.4) of Rec.709 display linear | 0.25 / 1023 |
| `view.aces2.sdr.inv` | `bt1886` code | `acescct` code of ACEScg | 0.25 / 1023 |
| `view.aces2.hdr1000` | ACEScg | `pq100` code of Rec.2020 display linear (P3-limited, 1000 nits) | 0.25 / 1023 |
| `view.aces2.hdr1000.inv` | `pq100` code | `acescct` code of ACEScg | 0.25 / 1023 |

- Chain: the config's ACEScg → ACES2065-1, then the ops of the built-in `ACES-OUTPUT - ACES2065-1_to_CIE-XYZ-D65 -
  {SDR-100nit-REC709, HDR-1000nit-P3-D65}_2.0` (AP0 → AP1, clamp [0, 8·r_hit], AP1 → AP0, `ACES2_OutputTransform`,
  clamp [0, peak]) without its final limiting-RGB → XYZ matrix, so no XYZ round trip adds f32 noise. The HDR
  limiting RGB (P3-D65) goes to Rec.2020 with OCIO's matrix in float64. Inverses: the same group with
  `TRANSFORM_DIR_INVERSE`. Codes are encoded in float64.
- Forward samples (280 + 21 specials per target): half plausible content (the target's display gamut, −6 … +4 stops),
  a quarter the AP1 cube (−8 … +10 stops), a quarter out-of-gamut / negative mixtures (×2^±4), then specials
  (black, greys, 65504 per channel, primaries at 1 and 16, negatives, NaN).
- Inverse samples (180 + 10 specials per target): SDR, the display cube uniform in code; HDR, the P3-D65 cube up
  to 1000 nits (half uniform, half dark-weighted u³) in Rec.2020 PQ; specials (black, peak, primaries, above
  peak, negative, NaN).
- `python -I -B golden.py --measure DIR` writes the same cases with 20 000 samples each to `DIR/view_measure.json`
  (outside the repo) for the error table in `README.md` (`measure_views`, an ignored test).

## Charts (`data/charts.json`)
ColorChecker 24 (reference values with their source cited: Lab D50, plus sRGB display code and ACEScg
linear, derived with colour-science), primaries and secondaries at 100 % and 75 %, a 0–16 linear exposure
ramp in stops, a grey ramp, an S-Log3 / PQ ramp, and SMPTE RP 219 bar values (8- and 10-bit, 709 and 601,
limited and full range). The images themselves are generated on demand outside the repo (see the oracle README).

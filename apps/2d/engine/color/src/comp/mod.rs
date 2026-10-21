//! The comp's programs (docs/phase2/COMP_CORE.md §1, §2.1, §4, §6): the merge operators, the matte programs and the
//! keyer, each as SkSL for the compositor and as its CPU twin here. One compositor: a comp compiles into the grade's SVG
//! filter graph (gradeProgram.ts `specStep`), and these programs are its `<feshader>` primitives, run by the native
//! renderer as Skia image filters on F16 premultiplied surfaces in the edit's working space. Our own maths, no libraries.
//!
//! Every program takes premultiplied colour in the working space and reads `uniform float rostrumWorking` (the renderer
//! sets it: 0 display values, sRGB-encoded Rec.709; 1 linear Rec.709; 2 ACEScg) when it needs ACEScg or display
//! values. Two shapes (anyrender_skia `runtime_shader_filter`):
//! - **colour** `half4 main(half4 c)`: one input (`in`);
//! - **blender** `half4 main(half4 m, half4 c)`: `m` = the SVG primitive's `in`, `c` = its `in2`.
//!
//! The rules the compiler applies (COMP_CORE §1): buffers are premultiplied, and a program that changes colour divides
//! by alpha, works and multiplies back (alpha 0 leaves the colour as is); a **matte** between nodes is an opaque grey
//! picture `(v, v, v, 1)`; blurs and morphology run on premultiplied pictures or on those mattes (spatial.rs is their
//! CPU twin), and a blurred matte is renormalised (`norm`); the keyer works in linear ACEScg whatever the working space.
//!
//! | module | programs |
//! |---|---|
//! | merge.rs | `merge` (the 23 `MERGE_OPS`) |
//! | matte.rs | `matteFrom`, `matteCombine`, `matteLevels`, `norm`, `matteApply`, `threshold` |
//! | keyer.rs | `screenWeight`, `screenFill`, `keyAlpha`, `diffDistance`, `diffAlpha`, `despill`, `spill`, `edgeWeight`, `edgeExtend`, `wrapBand`, `lightWrap` |
//! | aov.rs, defocus.rs, vblur.rs | the AOV tools (extra programs): `fog`, `position`, `relight`, `defocus`, `vectorBlur` |
//! | key.rs, run.rs | `Key` (the §4 JSON) and `Key::run`, the CPU reference of the whole key chain (what `matte.read` measures) |
mod aov;
pub mod compress;
#[cfg(test)]
mod premult_tests;
mod defocus;
mod grain;
pub mod guided;
mod key;
mod keyer;
mod matte;
mod relight;
mod merge;
pub mod morph;
mod run;
pub mod spatial;
mod vblur;
mod warp;

pub use key::{AutoCore, Blend, Channel, Despill, Difference, Edge, Key, LightWrap, Local, LocalMode, MatteKey, Method, Replace, ScreenKey, View};
pub use grain::{amplitude as grain_amplitude, noise as grain_noise};
pub use aov::{fog, position};
pub use relight::{Light, MAX_LIGHTS, relight_pixel};
pub use defocus::{Defocus, coc_radius, defocus_pixel};
pub use keyer::Screen;
pub use vblur::{VBlur, vector_blur_pixel};
pub use warp::{Warp, quad_matte, warp_pixel};
pub use merge::{FIRST_DISPLAY_OP, MERGE_OPS, merge};
pub use run::{KeyInputs, KeyOut};

use crate::Curve;
use crate::convert::gamut_matrix;
use crate::pipeline::Working;

/// One program as the host gets it (`rostrum-motion sksl comp`): its SkSL and the uniforms the host sets, by name
/// (`rostrumWorking` is the renderer's own and is not listed).
pub struct Program {
    pub name: &'static str,
    pub blender: bool,
    pub code: String,
    pub uniforms: &'static [&'static str],
}

/// Every program of COMP_CORE §6, in its table order.
pub fn programs() -> Vec<Program> {
    let mut all = vec![merge::program()];
    all.extend(matte::programs());
    all.extend(keyer::programs());
    all
}

/// Programs of the Editor's added looks (the plate's grain): listed by `rostrum-motion sksl comp` with the others, outside `programs()` (the CPU twin's chart test covers merge, matte and keyer).
pub fn extra_programs() -> Vec<Program> {
    let mut all = vec![morph::program(), grain::program(), compress::program(), warp::warp(), warp::quad_matte_program(), aov::fog_program(), aov::position_program(), relight::program(), defocus::program(), vblur::program()];
    all.extend(guided::programs());
    all
}

/// Uniform values by name, as a test or the host passes them (missing ones are 0).
pub type Uniforms<'a> = &'a [(&'a str, Vec<f32>)];

pub(crate) fn uf(u: Uniforms, name: &str) -> f32 {
    u.iter().find(|(n, _)| *n == name).and_then(|(_, v)| v.first().copied()).unwrap_or(0.0)
}

pub(crate) fn u3(u: Uniforms, name: &str) -> [f32; 3] {
    u.iter().find(|(n, _)| *n == name).map(|(_, v)| [v[0], v[1], v[2]]).unwrap_or([0.0; 3])
}

/// The CPU twin of program `name` on one pixel: `m` the blender's source (ignored by colour programs), `c` the input.
pub fn eval(name: &str, u: Uniforms, working: Working, m: [f32; 4], c: [f32; 4]) -> Result<[f32; 4], String> {
    if name == "merge" {
        return Ok(merge(uf(u, "op") as usize, m, c, uf(u, "amount"), uf(u, "display") > 0.5, working));
    }
    matte::eval(name, u, working, m, c).or_else(|| keyer::eval(name, u, working, m, c)).ok_or_else(|| {
        format!("unknown comp program `{name}` ({})", programs().iter().map(|p| p.name).collect::<Vec<_>>().join(", "))
    })
}

/// The working space as `rostrumWorking` reads it.
pub fn working_kind(w: Working) -> f32 {
    match w {
        Working::Display => 0.0,
        Working::LinearDisplay => 1.0,
        Working::AcesCg => 2.0,
    }
}

type M3 = [[f32; 3]; 3];

fn m3(a: &str, b: &str) -> M3 {
    gamut_matrix(a, b).expect("registered gamuts").map(|r| r.map(|v| v as f32))
}

fn mul(m: &M3, v: [f32; 3]) -> [f32; 3] {
    std::array::from_fn(|r| m[r][0] * v[0] + m[r][1] * v[1] + m[r][2] * v[2])
}

/// AP1 luminance weights (ACEScg's Y row): the keyer's `keepLuma` and `matteFrom`'s luma.
pub fn ap1_y() -> [f32; 3] {
    crate::Gamut::get("acescg").expect("acescg").to_xyz()[1].map(|v| v as f32)
}

/// Straight working-space colour → linear ACEScg.
pub fn to_cg(w: Working, x: [f32; 3]) -> [f32; 3] {
    match w {
        Working::Display => mul(&m3("lin_rec709", "acescg"), x.map(|v| Curve::Srgb.decode(v))),
        Working::LinearDisplay => mul(&m3("lin_rec709", "acescg"), x),
        Working::AcesCg => x,
    }
}

/// Linear ACEScg → straight working-space colour.
pub fn from_cg(w: Working, x: [f32; 3]) -> [f32; 3] {
    match w {
        Working::Display => mul(&m3("acescg", "lin_rec709"), x).map(|v| Curve::Srgb.encode(v)),
        Working::LinearDisplay => mul(&m3("acescg", "lin_rec709"), x),
        Working::AcesCg => x,
    }
}

/// Straight working-space colour → display-encoded (sRGB curve, Rec.709 primaries).
pub fn to_display(w: Working, x: [f32; 3]) -> [f32; 3] {
    match w {
        Working::Display => x,
        Working::LinearDisplay => x.map(|v| Curve::Srgb.encode(v)),
        Working::AcesCg => mul(&m3("acescg", "lin_rec709"), x).map(|v| Curve::Srgb.encode(v)),
    }
}

/// Display-encoded → straight working-space colour.
pub fn from_display(w: Working, x: [f32; 3]) -> [f32; 3] {
    match w {
        Working::Display => x,
        Working::LinearDisplay => x.map(|v| Curve::Srgb.decode(v)),
        Working::AcesCg => mul(&m3("lin_rec709", "acescg"), x.map(|v| Curve::Srgb.decode(v))),
    }
}

/// Premultiplied → straight (alpha 0: colour 0).
pub fn unpre(c: [f32; 4]) -> [f32; 4] {
    if c[3] > 0.0 { [c[0] / c[3], c[1] / c[3], c[2] / c[3], c[3]] } else { [0.0; 4] }
}

pub fn pre(x: [f32; 3], a: f32) -> [f32; 4] {
    [x[0] * a, x[1] * a, x[2] * a, a]
}

pub fn grey(v: f32) -> [f32; 4] {
    [v, v, v, 1.0]
}

/// The SkSL every program starts with: `rostrumWorking`, the sRGB curve and the conversions above (`toCg`, `fromCg`,
/// `toDisp`, `fromDisp`, `unpre`), generated from the same matrices and curve as the CPU twins.
pub(crate) fn prelude() -> String {
    let mat = |a: &str, b: &str| crate::view::sksl::mat(&m3(a, b));
    let (d, e) = (Curve::Srgb.sksl_name(false), Curve::Srgb.sksl_name(true));
    format!(
        "uniform float rostrumWorking;
{dec}{enc}float3 decS(float3 x) {{ return float3({d}(x.r), {d}(x.g), {d}(x.b)); }}
float3 encS(float3 x) {{ return float3({e}(x.r), {e}(x.g), {e}(x.b)); }}
float3 toCg(float3 x) {{ if (rostrumWorking > 1.5) {{ return x; }} return {to} * (rostrumWorking < 0.5 ? decS(x) : x); }}
float3 fromCg(float3 x) {{ if (rostrumWorking > 1.5) {{ return x; }} float3 l = {from} * x; return rostrumWorking < 0.5 ? encS(l) : l; }}
float3 toDisp(float3 x) {{ if (rostrumWorking < 0.5) {{ return x; }} return encS(rostrumWorking < 1.5 ? x : {from} * x); }}
float3 fromDisp(float3 x) {{ if (rostrumWorking < 0.5) {{ return x; }} float3 l = decS(x); return rostrumWorking < 1.5 ? l : {to} * l; }}
float4 unpre(float4 c) {{ return c.a > 0.0 ? float4(c.rgb / c.a, c.a) : float4(0.0); }}
float4 grey(float v) {{ return float4(v, v, v, 1.0); }}
",
        dec = Curve::Srgb.sksl(false),
        enc = Curve::Srgb.sksl(true),
        to = mat("lin_rec709", "acescg"),
        from = mat("acescg", "lin_rec709"),
    )
}

/// An f32 as an SkSL literal.
pub(crate) fn lit(x: f32) -> String {
    crate::view::sksl::f(x)
}

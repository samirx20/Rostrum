//! The grade as an SkSL colour filter `half4 main(half4 c)` on premultiplied ACEScg, generated from the same
//! constants as the CPU reference. The code depends only on the grade's structure (which operations, in which
//! order, the saturation weights, curve lengths, the LUT and hue / lum / sat tables, the layers' sources and
//! combines); every parameter is a uniform, so an animated grade refreshes `uniforms()` without recompiling.
//!
//! Uniforms (the host fills them from the document's grade, or takes `Grade::uniforms()`):
//! - `uniform float grade[N]`: each operation's slots, depth first (a layer's slot, then its operations'), then
//!   `mix` last. Slots per operation: Exposure `[stops]`; WhiteBalance `[kelvin, tint]`; Offset `[r, g, b]`;
//!   LiftGammaGain `[lift r, g, b, m, gamma r, g, b, m, gain r, g, b, m, black, white]`; Contrast `[contrast,
//!   pivot]`; Saturation `[saturation]`; Hue `[degrees]`; Boost `[amount]`; OffsetCct `[r, g, b, m]`; Log
//!   `[shadow r, g, b, m, mid r, g, b, m, high r, g, b, m, shadowEnd, highStart, softness]`; Layer `[mix]`; Curves,
//!   HslCurves and Lut none.
//! - `uniform float curves[M]` (only when there are curves): every table, in operation order and within an
//!   operation master, r, g, b. ES2 rules allow uniform arrays indexed by loop indices only, so each table is
//!   read with one loop over its samples (a hat-weighted sum, equal to linear interpolation): M iterations
//!   per pixel in all, fine for 64-sample curves, correct but slower for 256.
//! - `uniform shader lut0, lut1, …`: one child per LUT node and per hue / lum / sat curves operation, depth first,
//!   the table as an RGBA float image (`lut_images()`; texel reads at pixel centres, so give Skia a raw,
//!   nearest-sampled shader of an F16 / F32 image: no colour conversion, no filtering; layouts in lut_sksl.rs).
use super::lut_sksl::{LutImage, hsl_code, hsl_image, lut_code, lut_image};
use super::{Combine, Grade, Layer, Op, Section, Source, hsl, matte, walk, white};
use crate::matrix::Mat3;
use crate::view::Sksl;
use crate::view::sksl::{f, mat};
use crate::Curve;
use std::fmt::Write;

pub(super) fn m3(m: &Mat3) -> String {
    mat(&m.map(|r| r.map(|v| v as f32)))
}
pub(super) fn v3(v: [f64; 3]) -> String {
    format!("float3({}, {}, {})", f(v[0] as f32), f(v[1] as f32), f(v[2] as f32))
}

/// The operation's own slots in `grade[]` (a layer's operations follow its slot).
fn params(o: &Op) -> Vec<f32> {
    match o {
        Op::Exposure(s) => vec![*s],
        Op::WhiteBalance { kelvin, tint } => vec![*kelvin, *tint],
        Op::Offset(o) => o.to_vec(),
        Op::LiftGammaGain(g) => [&g.lift[..], &g.gamma, &g.gain, &[g.black, g.white]].concat(),
        Op::Contrast { contrast, pivot } => vec![*contrast, *pivot],
        Op::Saturation { saturation, .. } => vec![*saturation],
        Op::Hue(d) => vec![*d],
        Op::Boost(a) => vec![*a],
        Op::OffsetCct(o) => o.to_vec(),
        Op::Log(w) => [&w.shadow[..], &w.mid, &w.high, &[w.shadow_end, w.high_start, w.softness]].concat(),
        Op::Layer(l) => [&[l.mix][..], &l.matte.as_ref().map(|m| m.slots().to_vec()).unwrap_or_default()].concat(),
        Op::Curves(_) | Op::HslCurves(_) | Op::Lut(_) => vec![],
    }
}

fn curve_values(o: &Op) -> Vec<f32> {
    match o {
        Op::Curves(c) => c.tables().flat_map(|(_, t)| t.iter().copied()).collect(),
        _ => vec![],
    }
}

pub(super) fn per_channel(name: &str, v: &str) -> String {
    format!("float3({name}({v}.r), {name}({v}.g), {name}({v}.b))")
}

fn wb_code() -> String {
    let (a, ai, reference) = white::basis();
    let (u, v) = (white::KU.map(|k| f(k as f32)), white::KV.map(|k| f(k as f32)));
    let (lo, hi) = white::KELVIN_RANGE;
    format!(
        "const float3x3 WB_A = {}; const float3x3 WB_AI = {}; const float3 WB_REF = {};\nconst float3x3 CAT02 = {};\n\
         float3 wbCone(float kelvin, float tint) {{\n    float t = clamp(kelvin, {}, {});\n    \
         float pu = {} + {} * t + {} * t * t; float qu = 1.0 + {} * t + {} * t * t;\n    \
         float pv = {} + {} * t + {} * t * t; float qv = 1.0 + {} * t + {} * t * t;\n    \
         float du = (({u1} + 2.0 * {u2} * t) * qu - pu * ({u3} + 2.0 * {u4} * t)) / (qu * qu);\n    \
         float dv = (({v1} + 2.0 * {v2} * t) * qv - pv * ({v3} + 2.0 * {v4} * t)) / (qv * qv);\n    \
         float d = tint / {} / sqrt(du * du + dv * dv);\n    float u = pu / qu + d * dv; float v = pv / qv - d * du;\n    \
         float w = 2.0 * u - 8.0 * v + 4.0; float xx = 3.0 * u / w; float yy = 2.0 * v / w;\n    \
         return CAT02 * float3(xx / yy, 1.0, (1.0 - xx - yy) / yy);\n}}\n",
        m3(&a), m3(&ai), v3(reference), m3(&crate::Cat::Cat02.cone()), f(lo as f32), f(hi as f32),
        u[0], u[1], u[2], u[3], u[4], v[0], v[1], v[2], v[3], v[4], f(white::TINT_SCALE as f32),
        u1 = u[1], u2 = u[2], u3 = u[3], u4 = u[4], v1 = v[1], v2 = v[2], v3 = v[3], v4 = v[4]
    )
}

const SPOW: &str = "float spow(float x, float p) { return x < 0.0 ? -pow(-x, p) : pow(x, p); }\n";
const SCREEN: &str = "float screen1(float a, float b) { return a <= 1.0 && b <= 1.0 ? a + b - a * b : max(a, b); }\n\
    float3 screen3(float3 a, float3 b) { return float3(screen1(a.r, b.r), screen1(a.g, b.g), screen1(a.b, b.b)); }\n";

/// The code generator's running state (slots, curve offsets and child images are consumed depth first).
#[derive(Default)]
struct Gen {
    curves: Vec<(Curve, bool)>,
    helpers: String,
    slot: usize,
    coff: usize,
    luts: usize,
    wb: bool,
    lgg: bool,
    hsl: bool,
    screen: bool,
    matte: bool,
    /// The (qualifier, windows) channel of each matted layer (`Grade::channel_plan`) and how many layers were met.
    plan: Vec<(Option<usize>, Option<usize>)>,
    met: usize,
    /// The layer whose coverage the program returns instead of the grade (`Grade::sksl_matte_view`).
    view: Option<String>,
    /// `Grade::data`: no ACEScct encoding around the ACEScct operations.
    data: bool,
}

impl Gen {
    /// A run of operations from linear `x` back to linear, as body lines.
    fn ops(&mut self, ops: &[Op], depth: usize) -> String {
        let mut body = String::new();
        let mut cct = false;
        for o in ops {
            let want = o.section() == Section::Cct && !self.data;
            if want != cct {
                self.curves.push((Curve::AcesCct, want));
                let _ = writeln!(body, "    x = {};", per_channel(&Curve::AcesCct.sksl_name(want), "x"));
                cct = want;
            }
            let slot = self.slot;
            let g = |k: usize| format!("grade[{}]", slot + k);
            self.slot += params(o).len();
            let line = match o {
                Op::Exposure(_) => format!("x *= exp2({});", g(0)),
                Op::WhiteBalance { .. } => {
                    self.wb = true;
                    format!("x = WB_AI * ((WB_REF / wbCone({}, {})) * (WB_A * x));", g(0), g(1))
                }
                Op::Offset(_) => format!("x += float3({}, {}, {});", g(0), g(1), g(2)),
                Op::LiftGammaGain(_) => {
                    self.lgg = true;
                    format!(
                        "{{ float bk = {}; float wt = {}; float3 lift = float3({}, {}, {}) + {};\n      \
                         float3 gm = 1.0 / max(float3({}, {}, {}) * {}, 0.01); float3 t = (x - bk) / (wt - bk);\n      \
                         t = lift + (float3({}, {}, {}) * {} - lift) * float3(spow(t.r, gm.r), spow(t.g, gm.g), spow(t.b, gm.b));\n      \
                         x = bk + t * (wt - bk); }}",
                        g(12), g(13), g(0), g(1), g(2), g(3), g(4), g(5), g(6), g(7), g(8), g(9), g(10), g(11)
                    )
                }
                Op::Contrast { .. } => format!("x = (x - {p}) * {} + {p};", g(0), p = g(1)),
                Op::Saturation { luma, .. } => format!("{{ float l = dot(x, {}); x = l + {} * (x - l); }}", v3(luma.weights()), g(0)),
                Op::Hue(_) => {
                    self.hsl = true;
                    format!("x = hueRotate(x, {});", g(0))
                }
                Op::Boost(_) => {
                    self.hsl = true;
                    format!("{{ float3 h = hslOf(x); x = h.z + (1.0 + {} * (1.0 - h.y)) * (x - h.z); }}", g(0))
                }
                Op::OffsetCct(_) => format!("x += float3({}, {}, {}) + {};", g(0), g(1), g(2), g(3)),
                Op::Log(_) => {
                    self.hsl = true;
                    let wheel = |k: usize| format!("(float3({}, {}, {}) + {})", g(k), g(k + 1), g(k + 2), g(k + 3));
                    format!(
                        "{{ float l = luma709(x); float k = max({}, 1e-6);\n      \
                         float ws = 1.0 - smoothstep({e} - k, {e} + k, l); float wh = smoothstep({h} - k, {h} + k, l); float wm = max(1.0 - ws - wh, 0.0);\n      \
                         x += ws * {} + wm * {} + wh * {}; }}",
                        g(14), wheel(0), wheel(4), wheel(8), e = g(12), h = g(13)
                    )
                }
                Op::Curves(c) => {
                    let mut s = String::new();
                    for (ch, t) in c.tables() {
                        let (ty, v) = match ch {
                            None => ("float3", "x".to_string()),
                            Some(k) => ("float", format!("x.{}", ["r", "g", "b"][k])),
                        };
                        let _ = write!(
                            s,
                            "{{ {ty} cl = clamp({v}, 0.0, 1.0); {ty} p = cl * {}; {ty} acc = {ty}(0.0);\n      \
                             for (int k = 0; k < {}; k++) {{ acc += curves[{} + k] * max(1.0 - abs(p - float(k)), 0.0); }}\n      \
                             {v} = acc + ({v} - cl); }}\n    ",
                            f((t.len() - 1) as f32), t.len(), self.coff
                        );
                        self.coff += t.len();
                    }
                    s.trim_end().to_string()
                }
                Op::HslCurves(c) => {
                    self.hsl = true;
                    let i = self.luts;
                    self.helpers += &hsl_code(i);
                    self.luts += 1;
                    let mut at = std::collections::HashMap::new();
                    for (row, (k, t)) in c.tables().enumerate() {
                        let x = if k.periodic() { "h.x" } else if k == super::HslCurve::LumSat { "h.z" } else { "h.y" };
                        at.insert(k, format!("hslTable{i}({x}, {}, {})", f(row as f32), f(t.len() as f32)));
                    }
                    use super::HslCurve as K;
                    let mul = |k: K| at.get(&k).map(|e| format!(" * (1.0 + {e})")).unwrap_or_default();
                    let hue_lum = at.get(&K::HueLum).map_or("1.0".into(), |e| format!("(1.0 + {e} * h.y)"));
                    let rot = at.get(&K::HueHue).map(|e| format!(" x = hueRotate(x, {e});")).unwrap_or_default();
                    format!(
                        "{{ float3 h = hslOf(x); float ks = 1.0{}{}{}; float kl = {hue_lum}{};{rot}\n      \
                         x = h.z + ks * (x - h.z) + (kl - 1.0) * h.z; }}",
                        mul(K::HueSat), mul(K::LumSat), mul(K::SatSat), mul(K::SatLum)
                    )
                }
                Op::Lut(n) => {
                    self.curves.extend([(n.to_in.encode, true), (n.from_out.decode, false)]);
                    self.helpers += &lut_code(self.luts, n);
                    self.luts += 1;
                    format!("x = lutNode{}(x);", self.luts - 1)
                }
                Op::Layer(l) => {
                    let d = depth;
                    // The coverage first: spatial mattes are numbered depth first, the layer before its operations.
                    let cov = self.coverage(l, d, &g);
                    let inner = self.ops(&l.ops, depth + 1);
                    let from = if l.from == Source::Input { " x = src;" } else { "" };
                    let blend = match l.combine {
                        Combine::Over => format!("cur{d} + w{d} * (x - cur{d})"),
                        Combine::Add => format!("cur{d} + w{d} * x"),
                        Combine::Multiply => format!("cur{d} * (1.0 + w{d} * (x - 1.0))"),
                        Combine::Screen => {
                            self.screen = true;
                            format!("cur{d} + w{d} * (screen3(cur{d}, x) - cur{d})")
                        }
                    };
                    // `cov`: the layer's matte coverage (1 with no matte; mod.rs doc "Mattes").
                    let view = if self.view.as_deref() == Some(l.id.as_str()) { format!(" viewCov = cov{d};") } else { String::new() };
                    format!(
                        "{{ float3 cur{d} = x;{from}\n    {cov}{view}\n{inner}    float w{d} = {} * cov{d};\n    x = {blend}; }}",
                        g(0)
                    )
                }
            };
            let _ = writeln!(body, "    {line}");
        }
        if cct {
            self.curves.push((Curve::AcesCct, false));
            let _ = writeln!(body, "    x = {};", per_channel(&Curve::AcesCct.sksl_name(false), "x"));
        }
        body
    }
}

impl Gen {
    /// The declaration of `cov{d}`, the layer's matte coverage, as a body line (mod.rs doc "Mattes"): the qualifier's
    /// key of the stack's input `src` (or, for a spatial qualifier, the filtered key read from its channel of the matte
    /// image `pk`) through clean and invert, times the windows' coverage (their channel of `pk`), then the matte's own invert. Its
    /// slots follow the layer's mix: the key's 11, clean black and white, the qualifier's invert, the matte's invert (matte.rs `Matte::slots`).
    fn coverage(&mut self, l: &Layer, d: usize, g: &dyn Fn(usize) -> String) -> String {
        let Some(m) = &l.matte else { return format!("float cov{d} = 1.0;") };
        let (qch, wch) = self.plan[self.met];
        self.met += 1;
        let ch = |c: usize| format!("pk.{}", ["r", "g", "b"][c.min(2)]);
        let mut decl = String::new();
        let key = match (&m.qualify, qch) {
            (None, _) => "1.0".to_string(),
            (Some(q), spatial) => {
                self.matte = true;
                self.hsl = true;
                let key = match spatial {
                    Some(c) => ch(c),
                    None => {
                        self.curves.push((Curve::AcesCct, true));
                        decl = format!("float3 t{d} = {}; ", per_channel(&Curve::AcesCct.sksl_name(true), "src"));
                        q.key_expr(&format!("t{d}"), &|k| g(1 + k))
                    }
                };
                format!("qFinish({key}, {}, {}, {})", g(12), g(13), g(14))
            }
        };
        let win = wch.map(|c| format!(" * {}", ch(c))).unwrap_or_default();
        format!("{decl}float cov{d} = {key}{win}; cov{d} = {} > 0.5 ? 1.0 - cov{d} : cov{d};", g(15))
    }
}

/// One spatial matte as the compositor runs it (mod.rs "The matte seam"): the key stage, the filters, the channel it
/// is packed into.
pub struct MatteStage {
    /// The layer's id.
    pub layer: String,
    /// The channel (0 r, 1 g, 2 b) of the matte image the grade reads.
    pub channel: usize,
    /// A colour filter on premultiplied ACEScg (`half4 main(half4 c)`): the raw key times the channel's mask, alpha 1. For a
    /// window stage (`shader`): an image-filter shader `half4 main(float2 p)` with `uniform shader src` and `box`, the windows'
    /// coverage in the channel (window_sksl.rs); it has no further filters.
    pub key: Sksl,
    /// `key` is a window shader, not a colour filter.
    pub shader: bool,
    /// The denoise: an image-filter shader (`uniform shader src`; its `radius` uniform in px) and the radius.
    pub denoise: Option<Sksl>,
    pub shrink: f32,
    pub grow: f32,
    pub blur: f32,
    /// A colour filter that divides out the alpha filters leave at the picture's border (blur, erode): `half4 main(half4 c)`.
    pub norm: String,
}

/// The renormalising colour filter of a matte stage.
const NORM: &str = "half4 main(half4 c) { float a = float(c.a); return a > 1e-4 ? half4(half3(float3(c.rgb) / a), 1.0) : half4(0.0, 0.0, 0.0, 1.0); }\n";

impl Grade {
    /// The matte stages (a spatial qualifier's, a layer's windows'), in channel order (empty when no matte needs a stage).
    pub fn matte_stages(&self) -> Result<Vec<MatteStage>, String> {
        self.check()?;
        let mut out = vec![];
        let mask = |c: usize| ["float3(1.0, 0.0, 0.0)", "float3(0.0, 1.0, 0.0)", "float3(0.0, 0.0, 1.0)"][c];
        for ((l, m), (qch, wch)) in self.mattes().into_iter().zip(self.channel_plan()) {
            if let (Some(channel), Some(q)) = (qch, m.qualify.as_ref()) {
                let enc = Curve::AcesCct;
                let code = format!(
                    "uniform float qual[11];
{}{}{}float qualKey(float3 x) {{
    float3 t = {};
    return {};
}}
                     half4 main(half4 c) {{
    float a = float(c.a);
    float3 x = a > 0.0 ? float3(c.rgb) / a : float3(0.0);
                         return half4(half3(qualKey(x) * {}), 1.0);
}}
",
                    enc.sksl(true),
                    hsl::sksl(),
                    matte::sksl_helpers(),
                    per_channel(&enc.sksl_name(true), "x"),
                    q.key_expr("t", &|k| format!("qual[{k}]")),
                    mask(channel)
                );
                let denoise = (q.denoise > 0.0).then(|| Sksl { code: matte::denoise_sksl(), uniforms: vec![("radius", vec![q.denoise])] });
                out.push(MatteStage {
                    layer: l.id.clone(),
                    channel,
                    key: Sksl { code, uniforms: vec![("qual", q.key_slots().to_vec())] },
                    shader: false,
                    denoise,
                    shrink: q.shrink,
                    grow: q.grow,
                    blur: q.blur,
                    norm: NORM.into(),
                });
            }
            if let Some(channel) = wch {
                let key = super::window_sksl::window_shader(&m.windows, mask(channel));
                out.push(MatteStage { layer: l.id.clone(), channel, key, shader: true, denoise: None, shrink: 0.0, grow: 0.0, blur: 0.0, norm: NORM.into() });
            }
        }
        Ok(out)
    }
}

impl Grade {
    /// The uniform values, in the layout the code declares (`grade`, then `curves` when there are curves).
    pub fn uniforms(&self) -> Vec<(&'static str, Vec<f32>)> {
        let (mut g, mut c) = (vec![], vec![]);
        walk(&self.ops, &mut |o| {
            g.extend(params(o));
            c.extend(curve_values(o));
        });
        g.push(self.mix);
        let mut u = vec![("grade", g)];
        if !c.is_empty() {
            u.push(("curves", c));
        }
        u
    }

    /// The child images, in `lut0, lut1, …` order (LUT nodes and hue / lum / sat curves, depth first).
    pub fn lut_images(&self) -> Vec<LutImage> {
        let mut out = vec![];
        walk(&self.ops, &mut |o| match o {
            Op::Lut(n) => out.push(lut_image(n)),
            Op::HslCurves(c) => out.push(hsl_image(c)),
            _ => {}
        });
        out
    }

    /// The grade's program on premultiplied ACEScg and its uniforms. Without spatial mattes it is a colour filter
    /// `half4 main(half4 c)`; with them (`matte_channels() > 0`) it is a runtime BLENDER
    /// `half4 main(half4 m, half4 c)`: `c` the picture (the blender's destination), `m` the packed matte image the
    /// matte stages made (the source; one spatial matte per channel). mod.rs "The matte seam".
    pub fn sksl(&self) -> Result<Sksl, String> {
        self.build(None)
    }

    /// The same program returning the coverage of layer `id`'s matte as a grey picture instead of the grade (to see the matte).
    pub fn sksl_matte_view(&self, id: &str) -> Result<Sksl, String> {
        self.build(Some(id))
    }

    fn build(&self, view: Option<&str>) -> Result<Sksl, String> {
        self.check()?;
        if let Some(id) = view {
            if !self.mattes().iter().any(|(l, _)| l.id == id) {
                let ids: Vec<&str> = self.mattes().iter().map(|(l, _)| l.id.as_str()).collect();
                return Err(format!("no layer `{id}` has a matte to show (matted layers: {})", if ids.is_empty() { "none".into() } else { ids.join(", ") }));
            }
        }
        let uniforms = self.uniforms();
        let mut head = format!("uniform float grade[{}];\n", uniforms[0].1.len());
        if let Some((_, c)) = uniforms.get(1) {
            let _ = writeln!(head, "uniform float curves[{}];", c.len());
        }
        let mut cg = Gen { view: view.map(String::from), plan: self.channel_plan(), data: self.data, ..Gen::default() };
        let body = cg.ops(&self.ops, 0);
        (0..cg.luts).for_each(|i| _ = writeln!(head, "uniform shader lut{i};"));
        let mut fns = String::new();
        for (i, (c, e)) in cg.curves.iter().enumerate() {
            if !cg.curves[..i].contains(&(*c, *e)) {
                fns += &c.sksl(*e);
            }
        }
        let spatial = self.matte_channels() > 0;
        let result = if view.is_some() { "float3(viewCov)".to_string() } else { format!("src + grade[{}] * (x - src)", cg.slot) };
        let (sig, call, entry) = if spatial {
            (
                "float3 gradeMain(float3 x, float3 pk)",
                "gradeMain(x, float3(m.rgb))",
                "half4 main(half4 m, half4 c)",
            )
        } else {
            ("float3 gradeMain(float3 x)", "gradeMain(x)", "half4 main(half4 c)")
        };
        let code = format!(
            "{head}{fns}{}{}{}{}{}{}{sig} {{\n    float3 src = x; float viewCov = 0.0;\n{body}    return {result};\n}}\n\
             {entry} {{\n    float a = float(c.a);\n    float3 x = a > 0.0 ? float3(c.rgb) / a : float3(0.0);\n    \
             return half4(half3({call} * a), c.a);\n}}\n",
            if cg.lgg { SPOW } else { "" },
            if cg.wb { wb_code() } else { String::new() },
            if cg.hsl { hsl::sksl() } else { String::new() },
            if cg.matte { matte::sksl_helpers() } else { "" },
            if cg.screen { SCREEN } else { "" },
            cg.helpers,
        );
        Ok(Sksl { code, uniforms })
    }
}

//! A grade from its JSON spec (the document's grade as operations; the host writes it: src/engine/video/
//! gradeProgram.ts). Two forms:
//! - one list: `{ "ops": [op, …], "mix"? }`;
//! - layers: `{ "layers": [{ "id"?, "ops": [op, …], "mix"?, "from"?: "previous" | "input", "combine"?: "over" | "add" |
//!   "multiply" | "screen", "matte"?: { "qualify": {…}, "invert"? } | null }], "mix"? }`, top to bottom (mod.rs `Layer`). A layer that is plain
//!   serial work (from previous, over, mix 1, no matte) is its operations inline, so the one-list form and its
//!   one-layer migration are the same grade, value for value.
//!
//! Operations (`"op"` plus its fields; every field optional with the neutral default; `null` = absent):
//! `exposure {stops}`, `white {kelvin, tint}`, `warmth {temperature, tint}`, `contrast {contrast, pivot}` (pivot an
//! ACEScct code, default 18 % grey), `saturation {saturation, luma: "rec709" | "ap1"}` (default rec709), `hue
//! {degrees}`, `boost {amount}`, `luma_mix {amount}` (the identity: mod.rs doc), `offset_cct {rgbm: [r, g, b, m]}`,
//! `lgg {lift, gamma, gain}` (each `[r, g, b, m]` or `[r, g, b]`), `log {shadow, mid, high: [r, g, b, m], shadowEnd,
//! highStart, softness}`, `curves {master, r, g, b}` (tables), `hsl_curves {hueHue, hueSat, hueLum, lumSat, satSat,
//! satLum}` (tables, mod.rs doc), `lut {file, interp: "tetrahedral" | "trilinear", in, out}`. Operations apply in
//! list order. Unknown operations, unknown fields and wrongly typed values are errors.
//!
//! `warmth` is the old grades' temperature / tint (channel gains on grey: R ×(1+0.1t), G ×(1+0.1ti), B ×(1−0.1t)),
//! fitted to the white balance that gives grey the same gains.
use super::{Window, Combine, Curves, Grade, HslCurve, HslCurves, HueRange, Layer, Lgg, LogWheels, Luma, LutNode, Matte, Op, Qualify, Range, Source, grey_pivot, wb_matrix};
use crate::{Cube, Interp};
use serde_json::{Map, Value};

/// Grey's Rec.709 channel gains under a white balance.
fn gains(kelvin: f64, tint: f64) -> [f64; 3] {
    let m = crate::matrix::mul(&crate::convert::gamut_matrix("acescg", "lin_rec709").unwrap(), &wb_matrix(kelvin, tint));
    let g = crate::matrix::apply(&m, crate::matrix::apply(&crate::convert::gamut_matrix("lin_rec709", "acescg").unwrap(), [1.0; 3]));
    [g[0] / g[1], 1.0, g[2] / g[1]]
}

/// The white balance whose grey gains match the old grade's temperature / tint (R ×(1+0.1t), G ×(1+0.1ti),
/// B ×(1−0.1t)): Newton on (log R/G, log B/G) over (kelvin, tint).
pub fn warmth(temperature: f64, tint: f64) -> (f32, f32) {
    let want = [((1.0 + 0.1 * temperature) / (1.0 + 0.1 * tint)).ln(), ((1.0 - 0.1 * temperature) / (1.0 + 0.1 * tint)).ln()];
    let f = |k: f64, t: f64| {
        let g = gains(k, t);
        [g[0].ln() - want[0], g[2].ln() - want[1]]
    };
    let (mut k, mut t) = (6500.0, 0.0);
    for _ in 0..30 {
        let r = f(k, t);
        let (dk, dt) = (1.0, 0.01);
        let (a, b) = (f(k + dk, t), f(k, t + dt));
        let j = [[(a[0] - r[0]) / dk, (b[0] - r[0]) / dt], [(a[1] - r[1]) / dk, (b[1] - r[1]) / dt]];
        let det = j[0][0] * j[1][1] - j[0][1] * j[1][0];
        if det.abs() < 1e-14 {
            break;
        }
        k = (k - (j[1][1] * r[0] - j[0][1] * r[1]) / det).clamp(1000.0, 15000.0);
        t -= (-j[1][0] * r[0] + j[0][0] * r[1]) / det;
    }
    (k as f32, t as f32)
}

impl Grade {
    /// The grade a spec describes (module doc); a loud error for an unknown op or field, a bad value or a bad LUT.
    pub fn from_spec(spec: &Value) -> Result<Grade, String> {
        parse(spec)
    }
}

/// An object's fields, every one of them in `allowed` (`what` names it in errors).
pub(super) fn fields<'a>(v: &'a Value, what: &str, allowed: &[&str]) -> Result<&'a Map<String, Value>, String> {
    let o = v.as_object().ok_or_else(|| format!("{what} is an object; got {v}"))?;
    if let Some(k) = o.keys().find(|k| !allowed.contains(&k.as_str())) {
        return Err(format!("{what}: unknown field `{k}` (fields: {})", allowed.join(", ")));
    }
    Ok(o)
}

/// A field present and not null.
pub(super) fn get<'a>(o: &'a Map<String, Value>, k: &str) -> Option<&'a Value> {
    o.get(k).filter(|v| !v.is_null())
}

pub(super) struct Obj<'a> {
    pub(super) o: &'a Map<String, Value>,
    pub(super) what: String,
}

impl Obj<'_> {
    pub(super) fn num(&self, k: &str, d: f32) -> Result<f32, String> {
        match get(self.o, k) {
            None => Ok(d),
            Some(v) => v.as_f64().map(|x| x as f32).ok_or_else(|| format!("{}: `{k}` is a number; got {v}", self.what)),
        }
    }
    pub(super) fn list(&self, k: &str) -> Result<Option<Vec<f32>>, String> {
        let Some(v) = get(self.o, k) else { return Ok(None) };
        let a = v.as_array().ok_or_else(|| format!("{}: `{k}` is a list of numbers; got {v}", self.what))?;
        a.iter().map(|x| x.as_f64().map(|x| x as f32).ok_or_else(|| format!("{}: `{k}` is a list of numbers; got {x} in it", self.what))).collect::<Result<_, _>>().map(Some)
    }
    /// `[r, g, b, m]` (or `[r, g, b]`, master `d`).
    pub(super) fn rgbm(&self, k: &str, d: f32) -> Result<[f32; 4], String> {
        match self.list(k)? {
            None => Ok([d; 4]),
            Some(a) if a.len() == 4 => Ok([a[0], a[1], a[2], a[3]]),
            Some(a) if a.len() == 3 => Ok([a[0], a[1], a[2], d]),
            Some(a) => Err(format!("{}: `{k}` is [r, g, b, m]; got {} numbers", self.what, a.len())),
        }
    }
    pub(super) fn word<'b>(&self, k: &str, options: &[&'b str]) -> Result<Option<&'b str>, String> {
        let Some(v) = get(self.o, k) else { return Ok(None) };
        let s = v.as_str().unwrap_or("");
        options.iter().find(|o| **o == s).map(|o| Some(*o)).ok_or_else(|| format!("{}: `{k}` is one of {}; got {v}", self.what, options.join(", ")))
    }
}

fn op(v: &Value, at: &str) -> Result<Option<Op>, String> {
    let name = v.get("op").and_then(Value::as_str).ok_or_else(|| format!("{at}: a grade op names its `op`; got {v}"))?;
    let allowed: &[&str] = match name {
        "exposure" => &["stops"],
        "white" => &["kelvin", "tint"],
        "warmth" => &["temperature", "tint"],
        "contrast" => &["contrast", "pivot"],
        "saturation" => &["saturation", "luma"],
        "hue" => &["degrees"],
        "boost" => &["amount"],
        "luma_mix" => &["amount"],
        "offset_cct" => &["rgbm"],
        "lgg" => &["lift", "gamma", "gain"],
        "log" => &["shadow", "mid", "high", "shadowEnd", "highStart", "softness"],
        "curves" => &["master", "r", "g", "b"],
        "hsl_curves" => &["hueHue", "hueSat", "hueLum", "lumSat", "satSat", "satLum"],
        "lut" => &["file", "interp", "in", "out"],
        other => return Err(format!("{at}: unknown grade op `{other}`")),
    };
    let what = format!("{at}: grade op `{name}`");
    let o = Obj { o: fields(v, &what, &[&["op"], allowed].concat())?, what };
    Ok(Some(match name {
        "exposure" => Op::Exposure(o.num("stops", 0.0)?),
        "white" => Op::WhiteBalance { kelvin: o.num("kelvin", 6500.0)?, tint: o.num("tint", 0.0)? },
        "warmth" => {
            let (kelvin, tint) = warmth(o.num("temperature", 0.0)? as f64, o.num("tint", 0.0)? as f64);
            Op::WhiteBalance { kelvin, tint }
        }
        "contrast" => Op::Contrast { contrast: o.num("contrast", 1.0)?, pivot: o.num("pivot", grey_pivot())? },
        "saturation" => {
            let luma = if o.word("luma", &["rec709", "ap1"])? == Some("ap1") { Luma::Ap1 } else { Luma::Rec709 };
            Op::Saturation { saturation: o.num("saturation", 1.0)?, luma }
        }
        "hue" => Op::Hue(o.num("degrees", 0.0)?),
        "boost" => Op::Boost(o.num("amount", 0.0)?),
        "luma_mix" => {
            o.num("amount", 0.0)?;
            return Ok(None);
        }
        "offset_cct" => Op::OffsetCct(o.rgbm("rgbm", 0.0)?),
        "lgg" => Op::LiftGammaGain(Lgg { lift: o.rgbm("lift", 0.0)?, gamma: o.rgbm("gamma", 1.0)?, gain: o.rgbm("gain", 1.0)?, ..Lgg::default() }),
        "log" => Op::Log(LogWheels {
            shadow: o.rgbm("shadow", 0.0)?,
            mid: o.rgbm("mid", 0.0)?,
            high: o.rgbm("high", 0.0)?,
            shadow_end: o.num("shadowEnd", super::LOG_SHADOW_END)?,
            high_start: o.num("highStart", super::LOG_HIGH_START)?,
            softness: o.num("softness", super::LOG_SOFTNESS)?,
        }),
        "curves" => Op::Curves(Curves { master: o.list("master")?, r: o.list("r")?, g: o.list("g")?, b: o.list("b")? }),
        "hsl_curves" => {
            let mut c = HslCurves::default();
            for k in HslCurve::ALL {
                *c.slot(k) = o.list(k.key())?;
            }
            Op::HslCurves(c)
        }
        "lut" => {
            let file = get(o.o, "file").and_then(Value::as_str).ok_or_else(|| format!("{}: names its `file`", o.what))?;
            let cube = Cube::parse(&std::fs::read_to_string(file).map_err(|e| format!("{file}: {e}"))?).map_err(|e| format!("{file}: {e}"))?;
            let interp = if o.word("interp", &["tetrahedral", "trilinear"])? == Some("trilinear") { Interp::Trilinear } else { Interp::Tetrahedral };
            let space = |k: &str| match get(o.o, k) {
                None => Ok("srgb_display"),
                Some(v) => v.as_str().ok_or_else(|| format!("{}: `{k}` is a space id; got {v}", o.what)),
            };
            Op::Lut(Box::new(LutNode::new(cube.lut, interp, space("in")?, space("out")?)?))
        }
        _ => unreachable!(),
    }))
}

fn ops(v: Option<&Value>, at: &str) -> Result<Vec<Op>, String> {
    let list = v.and_then(Value::as_array).ok_or_else(|| format!("{at} has `ops`, a list"))?;
    let mut out = vec![];
    for (i, o) in list.iter().enumerate() {
        out.extend(op(o, &format!("{at} op {i}"))?);
    }
    Ok(out)
}

fn layer(v: &Value, i: usize) -> Result<Vec<Op>, String> {
    let at = match v.get("id").and_then(Value::as_str) {
        Some(id) => format!("grade layer `{id}`"),
        None => format!("grade layer {i}"),
    };
    let o = Obj { o: fields(v, &at, &["id", "ops", "mix", "from", "combine", "matte"])?, what: at.clone() };
    let id = match get(o.o, "id") {
        None => String::new(),
        Some(v) => v.as_str().ok_or_else(|| format!("{at}: `id` is a string; got {v}"))?.to_string(),
    };
    let from = if o.word("from", &["previous", "input"])? == Some("input") { Source::Input } else { Source::Previous };
    let combine = match o.word("combine", &["over", "add", "multiply", "screen"])? {
        Some("add") => Combine::Add,
        Some("multiply") => Combine::Multiply,
        Some("screen") => Combine::Screen,
        _ => Combine::Over,
    };
    let matte = get(o.o, "matte").map(|m| matte(m, &at)).transpose()?;
    let l = Layer { id, ops: ops(o.o.get("ops"), &at)?, mix: o.num("mix", 1.0)?, from, combine, matte };
    // Plain serial work is its operations inline (module doc).
    if l.from == Source::Previous && l.combine == Combine::Over && l.mix == 1.0 && l.matte.is_none() {
        return Ok(l.ops);
    }
    Ok(vec![Op::Layer(Box::new(l))])
}

fn parse(spec: &Value) -> Result<Grade, String> {
    let o = Obj { o: fields(spec, "a grade spec", &["ops", "layers", "mix", "data"])?, what: "a grade spec".into() };
    let ops = match (o.o.get("ops"), o.o.get("layers")) {
        (Some(_), Some(_)) => return Err("a grade spec has `ops` or `layers`, not both".into()),
        (None, Some(l)) => {
            let list = l.as_array().ok_or("a grade spec's `layers` is a list")?;
            let mut out = vec![];
            for (i, l) in list.iter().enumerate() {
                out.extend(layer(l, i)?);
            }
            out
        }
        (o, None) => ops(o, "a grade spec")?,
    };
    let data = match o.o.get("data") {
        None | Some(Value::Null) => false,
        Some(Value::Bool(b)) => *b,
        Some(v) => return Err(format!("a grade spec's `data` is true or false, not {v}")),
    };
    let mut g = Grade { ops, mix: o.num("mix", 1.0)?, data };
    if data {
        on_plain_numbers(&mut g.ops);
    }
    g.check()?;
    Ok(g)
}

/// A data grade's ACEScct operations on plain numbers: lift / gamma / gain between 0 and 1, the default contrast pivot 0.18.
fn on_plain_numbers(ops: &mut [Op]) {
    for o in ops {
        match o {
            Op::LiftGammaGain(g) => (g.black, g.white) = (0.0, 1.0),
            Op::Contrast { pivot, .. } if *pivot == grey_pivot() => *pivot = 0.18,
            Op::Layer(l) => on_plain_numbers(&mut l.ops),
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn warmth_matches_the_old_channel_gains() {
        for (t, ti) in [(0.0, 0.0), (0.5, 0.0), (-0.8, 0.3), (1.0, -1.0)] {
            let (k, tint) = super::warmth(t, ti);
            let g = super::gains(k as f64, tint as f64);
            let want = [(1.0 + 0.1 * t) / (1.0 + 0.1 * ti), (1.0 - 0.1 * t) / (1.0 + 0.1 * ti)];
            assert!((g[0] - want[0]).abs() < 1e-3 && (g[2] - want[1]).abs() < 1e-3, "{t} {ti}: {k} K tint {tint}: {g:?} vs {want:?}");
        }
    }
    #[test]
    fn a_data_grade_gains_the_plain_numbers() {
        let spec = |data: bool| serde_json::json!({ "ops": [{ "op": "lgg", "gain": [1.0, 1.0, 1.0, 0.1] }], "data": data });
        let data = super::Grade::from_spec(&spec(true)).unwrap();
        let [z, ..] = data.apply([5.0, 5.0, 5.0]);
        assert!((z - 0.5).abs() < 1e-5, "depth 5 m × gain 0.1: {z}");
        // On light, gain works on ACEScct codes: the same numbers fall almost to black (what a depth layer showed).
        let [l, ..] = super::Grade::from_spec(&spec(false)).unwrap().apply([5.0, 5.0, 5.0]);
        assert!(l < 0.01, "{l}");
        assert!(super::Grade::from_spec(&serde_json::json!({ "ops": [], "data": 1 })).is_err());
    }
}

/// A matte from its spec: `{ "qualify"?: { hue?: { centre, width, soft }, sat?: { lo, hi, softLo, softHi }, lum?: { … },
/// invert?, clean?: { black, white }, blur?, shrink?, grow?, denoise? }, "windows"?: [window], "invert"? }` (matte.rs; the window
/// forms are window_spec.rs's). A matte has a qualifier, windows, or both.
fn matte(v: &Value, at: &str) -> Result<Matte, String> {
    let what = format!("{at} matte");
    let o = fields(v, &what, &["qualify", "windows", "invert"])?;
    let invert = match get(o, "invert") {
        None => false,
        Some(v) => v.as_bool().ok_or_else(|| format!("{what}: `invert` is true or false; got {v}"))?,
    };
    let windows = match get(o, "windows") {
        None => vec![],
        Some(w) => w.as_array().ok_or_else(|| format!("{what}: `windows` is a list"))?.iter().enumerate().map(|(i, w)| Window::from_spec(w, &format!("{what} window {}", i + 1))).collect::<Result<Vec<_>, _>>()?,
    };
    let Some(q) = get(o, "qualify") else {
        if windows.is_empty() {
            return Err(format!("{what}: has neither `qualify` nor `windows`"));
        }
        return Ok(Matte { qualify: None, windows, invert });
    };
    let qat = format!("{what} qualify");
    let qo = fields(q, &qat, &["hue", "sat", "lum", "invert", "clean", "blur", "shrink", "grow", "denoise"])?;
    let q = Obj { o: qo, what: qat.clone() };
    let sub = |k: &str, allowed: &[&str]| -> Result<Option<Obj<'_>>, String> {
        match get(qo, k) {
            None => Ok(None),
            Some(v) => {
                let what = format!("{qat}: `{k}`");
                Ok(Some(Obj { o: fields(v, &what, allowed)?, what }))
            }
        }
    };
    let hue = match sub("hue", &["centre", "width", "soft"])? {
        None => None,
        Some(h) => {
            for k in ["centre", "width"] {
                if get(h.o, k).is_none() {
                    return Err(format!("{}: names its `{k}` (degrees)", h.what));
                }
            }
            Some(HueRange { centre: h.num("centre", 0.0)?, width: h.num("width", 360.0)?, soft: h.num("soft", 0.0)? })
        }
    };
    let range = |k: &str| -> Result<Option<Range>, String> {
        Ok(match sub(k, &["lo", "hi", "softLo", "softHi"])? {
            None => None,
            Some(r) => Some(Range { lo: r.num("lo", 0.0)?, hi: r.num("hi", 1.0)?, soft_lo: r.num("softLo", 0.0)?, soft_hi: r.num("softHi", 0.0)? }),
        })
    };
    let clean = match sub("clean", &["black", "white"])? {
        None => None,
        Some(c) => Some([c.num("black", 0.0)?, c.num("white", 1.0)?]),
    };
    let qi = match get(qo, "invert") {
        None => false,
        Some(v) => v.as_bool().ok_or_else(|| format!("{qat}: `invert` is true or false; got {v}"))?,
    };
    let qualify = Qualify { hue, sat: range("sat")?, lum: range("lum")?, invert: qi, clean, denoise: q.num("denoise", 0.0)?, shrink: q.num("shrink", 0.0)?, grow: q.num("grow", 0.0)?, blur: q.num("blur", 0.0)? };
    Ok(Matte { qualify: Some(qualify), windows, invert })
}

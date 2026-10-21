//! `layer.key` (COMP_CORE §4) as data: parsed from the host's JSON, every field defaulted as the contract says, and an
//! unknown field or value is an error naming the choices. `core.matte` and `garbage` are §3 matte objects, kept as JSON
//! here (the compiler builds them; `Key::run` takes their pictures as inputs).

use serde_json::{Map, Value};

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Channel {
    G,
    B,
}

impl Channel {
    /// The `channel` uniform: the colour index.
    pub fn index(self) -> usize {
        match self {
            Channel::G => 1,
            Channel::B => 2,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LocalMode {
    None,
    Blur,
    Plate,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Method {
    Weighted,
    Average,
    Limit,
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Replace {
    None,
    Color([f32; 3]),
    Background,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Blend {
    Add,
    Screen,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum View {
    Result,
    Matte,
    Despill,
    Screen,
    Core,
    Edge,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Local {
    pub mode: LocalMode,
    pub blur: f32,
    pub threshold: f32,
    pub plate: Option<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ScreenKey {
    pub color: [f32; 3],
    pub channel: Channel,
    pub balance: f32,
    pub gain: f32,
    pub local: Local,
}

#[derive(Clone, Debug, PartialEq)]
pub struct MatteKey {
    pub black: f32,
    pub white: f32,
    pub gamma: f32,
    pub despot_black: f32,
    pub despot_white: f32,
    pub erode: f32,
    pub soft: f32,
}

#[derive(Clone, Debug, PartialEq)]
pub struct AutoCore {
    pub threshold: f32,
    pub erode: f32,
    pub soft: f32,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Despill {
    pub method: Method,
    pub amount: f32,
    pub replace: Replace,
    pub keep_luma: bool,
    pub from: Option<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Edge {
    pub width: f32,
    pub amount: f32,
    pub solid: f32,
    /// px inside the solid's rim whose colour edge extend also repaints (0: off).
    pub inset: f32,
    /// 0…1: the repainted colour keeps the pixel's own brightness (0: the fill's flat colour).
    pub keep_luma: f32,
}

impl Edge {
    /// `edge.inset` px as the share of solid within the edge blur's reach (σ = width) below which a near-opaque pixel is
    /// still rim: ½ + 0.4 · inset / width (the Gaussian's CDF near its middle), at most 0.99; 0 when off.
    pub fn core(&self) -> f32 {
        if self.inset <= 0.0 || self.width <= 0.0 { 0.0 } else { (0.5 + 0.4 * self.inset / self.width).min(0.99) }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct LightWrap {
    pub from: Option<String>,
    pub width: f32,
    pub amount: f32,
    pub blend: Blend,
}

/// Difference matting (KEYING_ROTO "As built R19"): the plate keyed against a clean plate (the shot without the subject). The
/// matte is the per-pixel weighted colour distance between the two in linear ACEScg, blurred by `blur` px, ramped from
/// `threshold` (alpha 0) to `threshold + softness` (alpha 1); then the matte's levels and cleanup as for a colour key.
/// The clean plate is a file (`plate`) or an earlier comp layer (`layer`: a `{ plate }` layer clean.plate made, another clip, a held frame).
#[derive(Clone, Debug, PartialEq)]
pub struct Difference {
    pub threshold: f32,
    pub softness: f32,
    /// Per-channel weights of the distance (r, g, b of ACEScg); the distance is normalised by their sum.
    pub weights: [f32; 3],
    pub blur: f32,
    pub plate: Option<String>,
    pub layer: Option<String>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Key {
    pub screen: ScreenKey,
    /// A difference key: alpha from the clean plate instead of the screen colour; no despill (there is no screen).
    pub difference: Option<Difference>,
    pub matte: MatteKey,
    pub core_auto: Option<AutoCore>,
    pub core_matte: Option<Value>,
    pub garbage: Option<Value>,
    pub despill: Despill,
    pub edge: Edge,
    pub light_wrap: LightWrap,
    pub view: View,
}

/// An object at `path` whose fields are all among `allowed` (absent or null: empty).
fn obj<'a>(v: Option<&'a Value>, path: &str, allowed: &[&str]) -> Result<Option<&'a Map<String, Value>>, String> {
    let Some(v) = v.filter(|v| !v.is_null()) else { return Ok(None) };
    let o = v.as_object().ok_or_else(|| format!("{path} is an object; got {v}"))?;
    if let Some(k) = o.keys().find(|k| !allowed.contains(&k.as_str())) {
        return Err(format!("{path}: unknown field `{k}` ({})", allowed.join(", ")));
    }
    Ok(Some(o))
}

fn num(o: Option<&Map<String, Value>>, path: &str, name: &str, default: f32) -> Result<f32, String> {
    match o.and_then(|o| o.get(name)).filter(|v| !v.is_null()) {
        None => Ok(default),
        Some(v) => v.as_f64().map(|n| n as f32).ok_or_else(|| format!("{path}.{name} is a number; got {v}")),
    }
}

fn choice<T: Copy>(o: Option<&Map<String, Value>>, path: &str, name: &str, choices: &[(&str, T)], default: T) -> Result<T, String> {
    let Some(v) = o.and_then(|o| o.get(name)).filter(|v| !v.is_null()) else { return Ok(default) };
    let names = || choices.iter().map(|c| format!("\"{}\"", c.0)).collect::<Vec<_>>().join(" | ");
    let s = v.as_str().ok_or_else(|| format!("{path}.{name} is {}; got {v}", names()))?;
    choices.iter().find(|c| c.0 == s).map(|c| c.1).ok_or_else(|| format!("{path}.{name} is {}; got \"{s}\"", names()))
}

fn rgb(v: &Value, path: &str) -> Result<[f32; 3], String> {
    match v.as_array().map(|a| a.iter().filter_map(Value::as_f64).map(|n| n as f32).collect::<Vec<_>>()) {
        Some(c) if c.len() == 3 => Ok([c[0], c[1], c[2]]),
        _ => Err(format!("{path} is [r, g, b] (linear ACEScg); got {v}")),
    }
}

fn text(o: Option<&Map<String, Value>>, path: &str, name: &str) -> Result<Option<String>, String> {
    match o.and_then(|o| o.get(name)).filter(|v| !v.is_null()) {
        None => Ok(None),
        Some(v) => v.as_str().map(|s| Some(s.to_string())).ok_or_else(|| format!("{path}.{name} is a string; got {v}")),
    }
}

impl Key {
    pub fn from_json(v: &Value) -> Result<Key, String> {
        let k = obj(Some(v), "key", &["screen", "difference", "matte", "core", "garbage", "despill", "edge", "lightWrap", "view"])?;
        let field = |name: &str| k.and_then(|k| k.get(name));
        let df = obj(field("difference"), "key.difference", &["threshold", "softness", "weights", "blur", "plate", "layer"])?;
        let difference = match df {
            None => None,
            Some(o) => {
                let weights = match o.get("weights").filter(|v| !v.is_null()) {
                    None => [1.0; 3],
                    Some(v) => rgb(v, "key.difference.weights")?,
                };
                if weights.iter().any(|&w| w < 0.0) || weights.iter().sum::<f32>() <= 0.0 {
                    return Err(format!("key.difference.weights are three numbers ≥ 0, not all 0; got {weights:?}"));
                }
                let d = Difference {
                    threshold: num(df, "key.difference", "threshold", 0.02)?,
                    softness: num(df, "key.difference", "softness", 0.1)?,
                    weights,
                    blur: num(df, "key.difference", "blur", 1.0)?,
                    plate: text(df, "key.difference", "plate")?,
                    layer: text(df, "key.difference", "layer")?,
                };
                if d.plate.is_some() == d.layer.is_some() {
                    return Err("key.difference needs one clean plate: plate (an image file) or layer (an earlier comp layer's id), not both".into());
                }
                if d.threshold < 0.0 || d.softness < 0.0 || d.blur < 0.0 {
                    return Err("key.difference: threshold, softness and blur are ≥ 0".into());
                }
                Some(d)
            }
        };
        let s = obj(field("screen"), "key.screen", &["color", "channel", "balance", "gain", "local"])?;
        // A difference key needs no screen colour; it keeps the colour key's default for the screen uniforms it never reads.
        let color = match s.and_then(|s| s.get("color")).filter(|v| !v.is_null()) {
            Some(c) => rgb(c, "key.screen.color")?,
            None if difference.is_some() => [0.02, 0.16, 0.03],
            None => return Err("key.screen.color is required (key.pick writes it): [r, g, b] linear ACEScg".into()),
        };
        let wider = if color[2] > color[1] { Channel::B } else { Channel::G };
        let l = obj(s.and_then(|s| s.get("local")), "key.screen.local", &["mode", "blur", "threshold", "plate"])?;
        let local = Local {
            mode: choice(l, "key.screen.local", "mode", &[("none", LocalMode::None), ("blur", LocalMode::Blur), ("plate", LocalMode::Plate)], LocalMode::None)?,
            blur: num(l, "key.screen.local", "blur", 24.0)?,
            threshold: num(l, "key.screen.local", "threshold", 0.1)?,
            plate: text(l, "key.screen.local", "plate")?,
        };
        if local.mode == LocalMode::Plate && local.plate.is_none() {
            return Err("key.screen.local.mode \"plate\" needs key.screen.local.plate (the clean plate's file)".into());
        }
        let screen = ScreenKey {
            color,
            channel: choice(s, "key.screen", "channel", &[("g", Channel::G), ("b", Channel::B)], wider)?,
            balance: num(s, "key.screen", "balance", 0.5)?,
            gain: num(s, "key.screen", "gain", 1.0)?,
            local,
        };
        let m = obj(field("matte"), "key.matte", &["black", "white", "gamma", "despot", "erode", "soft"])?;
        let d = obj(m.and_then(|m| m.get("despot")), "key.matte.despot", &["black", "white"])?;
        let matte = MatteKey {
            black: num(m, "key.matte", "black", 0.0)?,
            white: num(m, "key.matte", "white", 1.0)?,
            gamma: num(m, "key.matte", "gamma", 1.0)?,
            despot_black: num(d, "key.matte.despot", "black", 0.0)?,
            despot_white: num(d, "key.matte.despot", "white", 0.0)?,
            erode: num(m, "key.matte", "erode", 0.0)?,
            soft: num(m, "key.matte", "soft", 0.0)?,
        };
        let c = obj(field("core"), "key.core", &["auto", "matte"])?;
        let a = obj(c.and_then(|c| c.get("auto")), "key.core.auto", &["threshold", "erode", "soft"])?;
        let core_auto = match a {
            None => None,
            Some(_) => Some(AutoCore { threshold: num(a, "key.core.auto", "threshold", 0.98)?, erode: num(a, "key.core.auto", "erode", 2.0)?, soft: num(a, "key.core.auto", "soft", 1.0)? }),
        };
        let ds = obj(field("despill"), "key.despill", &["method", "amount", "replace", "keepLuma", "from"])?;
        let replace = match ds.and_then(|d| d.get("replace")).filter(|v| !v.is_null()) {
            None => Replace::None,
            Some(Value::String(s)) if s == "none" => Replace::None,
            Some(Value::String(s)) if s == "background" => Replace::Background,
            Some(v @ Value::Array(_)) => Replace::Color(rgb(v, "key.despill.replace")?),
            Some(v) => return Err(format!("key.despill.replace is \"none\" | [r, g, b] (ACEScg) | \"background\"; got {v}")),
        };
        let keep_luma = match ds.and_then(|d| d.get("keepLuma")).filter(|v| !v.is_null()) {
            None => false,
            Some(v) => v.as_bool().ok_or_else(|| format!("key.despill.keepLuma is true | false; got {v}"))?,
        };
        let despill = Despill {
            method: choice(ds, "key.despill", "method", &[("weighted", Method::Weighted), ("average", Method::Average), ("limit", Method::Limit)], Method::Weighted)?,
            amount: num(ds, "key.despill", "amount", 1.0)?,
            replace,
            keep_luma,
            from: text(ds, "key.despill", "from")?,
        };
        let e = obj(field("edge"), "key.edge", &["width", "amount", "solid", "inset", "keepLuma"])?;
        let edge = Edge { width: num(e, "key.edge", "width", 0.0)?, amount: num(e, "key.edge", "amount", 1.0)?, solid: num(e, "key.edge", "solid", 0.95)?, inset: num(e, "key.edge", "inset", 0.0)?, keep_luma: num(e, "key.edge", "keepLuma", 0.0)?.clamp(0.0, 1.0) };
        let w = obj(field("lightWrap"), "key.lightWrap", &["from", "width", "amount", "blend"])?;
        let light_wrap = LightWrap {
            from: text(w, "key.lightWrap", "from")?,
            width: num(w, "key.lightWrap", "width", 0.0)?,
            amount: num(w, "key.lightWrap", "amount", 0.0)?,
            blend: choice(w, "key.lightWrap", "blend", &[("add", Blend::Add), ("screen", Blend::Screen)], Blend::Add)?,
        };
        if despill.replace == Replace::Background && despill.from.is_none() && light_wrap.from.is_none() {
            return Err("key.despill.replace \"background\" needs a background: key.despill.from or key.lightWrap.from".into());
        }
        let views = [("result", View::Result), ("matte", View::Matte), ("despill", View::Despill), ("screen", View::Screen), ("core", View::Core), ("edge", View::Edge)];
        Ok(Key {
            screen,
            difference,
            matte,
            core_auto,
            core_matte: c.and_then(|c| c.get("matte")).filter(|v| !v.is_null()).cloned(),
            garbage: field("garbage").filter(|v| !v.is_null()).cloned(),
            despill,
            edge,
            light_wrap,
            view: choice(k, "key", "view", &views, View::Result)?,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn defaults_and_errors() {
        let k = Key::from_json(&json!({ "screen": { "color": [0.02, 0.16, 0.03] } })).unwrap();
        assert_eq!((k.screen.channel, k.screen.balance, k.matte.white, k.edge.solid, k.view), (Channel::G, 0.5, 1.0, 0.95, View::Result));
        assert_eq!(Key::from_json(&json!({ "screen": { "color": [0.02, 0.1, 0.4] } })).unwrap().screen.channel, Channel::B);
        let k = Key::from_json(&json!({ "screen": { "color": [0.0, 0.2, 0.0] }, "core": { "auto": {} }, "despill": { "replace": [1, 0.5, 0.2] } })).unwrap();
        assert_eq!(k.core_auto.unwrap().erode, 2.0);
        assert_eq!(k.despill.replace, Replace::Color([1.0, 0.5, 0.2]));
        let err = |v: Value| Key::from_json(&v).unwrap_err();
        assert!(err(json!({ "screen": { "color": [0, 1, 0], "hue": 3 } })).contains("unknown field `hue` (color, channel, balance, gain, local)"));
        assert!(err(json!({ "screen": { "color": [0, 1, 0] }, "despill": { "method": "fast" } })).contains("\"weighted\" | \"average\" | \"limit\""));
        assert!(err(json!({ "screen": {} })).contains("key.screen.color is required"));
        assert!(err(json!({ "screen": { "color": [0, 1, 0] }, "despill": { "replace": "background" } })).contains("lightWrap.from"));
    }

    #[test]
    fn a_difference_key_needs_one_clean_plate_and_no_screen_colour() {
        let k = Key::from_json(&json!({ "difference": { "plate": "clean.png" } })).unwrap();
        let d = k.difference.unwrap();
        assert_eq!((d.threshold, d.softness, d.weights, d.blur), (0.02, 0.1, [1.0; 3], 1.0));
        let err = |v: Value| Key::from_json(&v).unwrap_err();
        assert!(err(json!({ "difference": {} })).contains("one clean plate"));
        assert!(err(json!({ "difference": { "plate": "a.png", "layer": "bg" } })).contains("one clean plate"));
        assert!(err(json!({ "difference": { "layer": "bg", "weights": [0, 0, 0] } })).contains("not all 0"));
    }
}

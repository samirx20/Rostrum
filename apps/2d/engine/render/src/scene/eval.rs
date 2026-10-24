//! The one animation model (ENGINE_CONTRACT.md § 3), ported from `apps/2d/python/rostrum2d/evaluate.py` and
//! `scene.py` `frame_at`: a field with keys is decided by its keys alone; between key a and key b,
//! p = ease_a((t − a.t) / (b.t − a.t)) and the value is a + (b − a)·p (bent by spatial handles: `between`); before the first key and after the last the
//! value holds. Colours mix in linear light; a path's shape blends point by point (morph.rs). A layer outside start ≤ t < end is left out.

use serde_json::{Map, Value};

use super::fields::Role;
use super::{Key, KeyValue, Node};

/// One item at one time: every field's value, and its children that are showing.
#[derive(Clone, Debug)]
pub struct Item<'a> {
    pub id: &'a str,
    /// The item it was evaluated from, and the time (a text animated letter by letter re-evaluates it per letter).
    pub node: &'a Node,
    pub t: f64,
    pub kind: &'static str,
    pub props: Map<String, Value>,
    pub effects: Vec<Item<'a>>,
    pub masks: Vec<Item<'a>>,
    pub layers: Vec<Item<'a>>,
    /// A gradient's colour stops.
    pub stops: Vec<Item<'a>>,
}

impl Item<'_> {
    pub fn num(&self, f: &str) -> f64 {
        self.props.get(f).and_then(Value::as_f64).unwrap_or_else(|| panic!("{}.{f}: not a number (the scene was checked when it loaded)", self.id))
    }

    pub fn str(&self, f: &str) -> &str {
        self.props.get(f).and_then(Value::as_str).unwrap_or_else(|| panic!("{}.{f}: not text (the scene was checked when it loaded)", self.id))
    }

    pub fn on(&self, f: &str) -> bool {
        self.props.get(f).and_then(Value::as_bool).unwrap_or_else(|| panic!("{}.{f}: not a toggle (the scene was checked when it loaded)", self.id))
    }
}

/// `comp` at time `t`; None for a layer that isn't showing.
pub fn at(comp: &Node, t: f64) -> Option<Item<'_>> {
    eval(comp, t, false, fps(comp))
}

/// `comp` at time `t` with every layer kept, showing or not (the stage written from it checks the whole scene).
pub fn whole(comp: &Node, t: f64) -> Item<'_> {
    eval(comp, t, true, fps(comp)).unwrap()
}

fn fps(comp: &Node) -> f64 {
    comp.props.get("fps").and_then(Value::as_f64).unwrap_or(30.0)
}

/// The picture of the drawing showing at time `t`: the last with at ≤ floor(t·fps); "" before the first
/// (rostrum2d/drawing.py `frame_at`, `frame_number`).
/// The same rule picks an element's paint (`paint`).
fn drawing_src(frames: &[(i64, String)], t: f64, fps: f64) -> &str {
    let n = (t * fps + 1e-6).floor() as i64;
    frames.iter().take_while(|f| f.0 <= n).last().map_or("", |f| f.1.as_str())
}

fn eval(node: &Node, t: f64, all: bool, fps: f64) -> Option<Item<'_>> {
    let mut props = props_at(node, t);
    if node.kind == "drawing" {
        props.insert("src".into(), Value::from(drawing_src(&node.frames, t, fps)));
    }
    if !node.paint.is_empty() {
        // Paint on an element (stage_paint.rs): the picture showing now ("" before its first drawing).
        props.insert("paintSrc".into(), Value::from(drawing_src(&node.paint, t, fps)));
        props.insert("paintInside".into(), Value::from(node.paint_inside));
    }
    if !node.fill_frames.is_empty() {
        // A painted fill (stage_raster.rs): the painting's drawing showing now is the fill's picture.
        props.insert("fillPicture".into(), Value::from(drawing_src(&node.fill_frames, t, fps)));
    }
    if node.kind == "grain" {
        props.insert("frame".into(), Value::from((t * fps + 1e-6).floor()));
    }
    if node.kind == "video" {
        props.insert("picture".into(), Value::from(super::stage_fx::video_picture(node, t, fps)));
    }
    let mut item = Item {
        id: &node.id,
        node,
        t,
        kind: node.kind,
        effects: node.effects.iter().filter_map(|c| eval(c, t, all, fps)).collect(),
        masks: node.masks.iter().filter_map(|c| eval(c, t, all, fps)).collect(),
        layers: node.layers.iter().filter_map(|c| eval(c, t, all, fps)).collect(),
        stops: node.stops.iter().filter_map(|c| eval(c, t, all, fps)).collect(),
        props,
    };
    super::follow::resolve(node, &mut item.layers, t);
    if node.kind == "rig" {
        crate::rig::pose(&mut item);
    }
    // A layer outside start ≤ t < end is left out; the frame (a `camera`) has no start or end: it always shows.
    if !all && node.role == Role::Layer && node.kind != "camera" && !(item.num("start") <= t && t < item.num("end")) {
        return None;
    }
    Some(item)
}

/// A node's own field values at time `t` (its still values, keyed fields decided by their keys). While a
/// motion-blurred frame's sub-frames are built (`shutter_at`), each field is read on its own side of a jump.
pub fn props_at(node: &Node, t: f64) -> Map<String, Value> {
    let mut props = node.props.clone();
    let centre = CENTRE.with(|c| c.get());
    for (field, keys) in &node.anim {
        let at = centre.map_or(t, |c| near_side(keys, c, t));
        props.insert(field.clone(), track_value(keys, at));
    }
    props
}

thread_local! {
    /// The time of the frame whose shutter is open (crate::motion), while its sub-frames are evaluated.
    static CENTRE: std::cell::Cell<Option<f64>> = const { std::cell::Cell::new(None) };
}

/// `f` evaluated as a sub-frame of the frame at `centre`: no field's value crosses a jump (a key after a hold key)
/// between the frame's time and the sub-frame's, so a cut never smears two shots (MOTION.md › Motion blur).
pub fn shutter_at<T>(centre: f64, f: impl FnOnce() -> T) -> T {
    CENTRE.with(|c| c.set(Some(centre)));
    let out = f();
    CENTRE.with(|c| c.set(None));
    out
}

/// The time to read a track at for a sub-frame at `t` of the frame at `centre`: `t`, or the near side of the first
/// jump between them (just before a jump after the frame; the jump itself before it).
pub fn near_side(keys: &[Key], centre: f64, t: f64) -> f64 {
    let jumps = keys.windows(2).filter(|w| matches!(w[0].ease, super::ease::Ease::Hold)).map(|w| w[1].t);
    let mut at = t;
    for j in jumps {
        if centre < j && j <= at {
            at = j - 1e-9;
        } else if at < j && j <= centre {
            at = j;
        }
    }
    at
}

/// The value of a sorted, non-empty list of keys at time `t`.
pub fn track_value(keys: &[Key], t: f64) -> Value {
    let first = &keys[0];
    if t <= first.t {
        return first.value.as_json();
    }
    for pair in keys.windows(2) {
        let (k0, k1) = (&pair[0], &pair[1]);
        if t < k1.t {
            let p = k0.ease.at((t - k0.t) / (k1.t - k0.t));
            return match (&k0.value, &k1.value) {
                (KeyValue::Color(_, a), KeyValue::Color(_, b)) => Value::String(mix(a, b, p.clamp(0.0, 1.0))),
                (KeyValue::Number(a), KeyValue::Number(b)) => Value::from(between(*a, *b, k0.out, k1.inn, p)),
                (KeyValue::Path(a), KeyValue::Path(b)) => Value::String(super::morph::blend("path", a, b, p).unwrap_or_else(|e| panic!("{e} (checked at load)"))),
                (KeyValue::Profile(_, a), KeyValue::Profile(_, b)) => Value::String(super::width_profile::write(&super::width_profile::blend(a, b, p))),
                _ => unreachable!("a field's keys are all numbers, all colours, all shapes or all width profiles (checked at load)"),
            };
        }
    }
    keys[keys.len() - 1].value.as_json()
}

/// A number between key a and key b at eased progress p (rostrum_core/keys/spatial.py `between`): straight without
/// handles (a's `out`, b's `in`), bit for bit as before; with either, the cubic Bézier a, a + out, b + in, b at p (a
/// missing handle is a third of the way along the straight line). Speed along the curve follows p, not arc length.
pub fn between(a: f64, b: f64, out: Option<f64>, inn: Option<f64>, p: f64) -> f64 {
    if out.is_none() && inn.is_none() {
        return a + (b - a) * p;
    }
    let c1 = a + out.unwrap_or((b - a) / 3.0);
    let c2 = b + inn.unwrap_or(-(b - a) / 3.0);
    let q = 1.0 - p;
    q * q * q * a + 3.0 * q * q * p * c1 + 3.0 * q * p * p * c2 + p * p * p * b
}

impl KeyValue {
    fn as_json(&self) -> Value {
        match self {
            KeyValue::Number(v) => Value::from(*v),
            KeyValue::Color(written, _) | KeyValue::Path(written) | KeyValue::Profile(written, _) => Value::String(written.clone()),
        }
    }
}

fn lin(c: f64) -> f64 {
    if c <= 0.04045 { c / 12.92 } else { ((c + 0.055) / 1.055).powf(2.4) }
}

fn srgb(c: f64) -> f64 {
    let c = c.clamp(0.0, 1.0);
    if c <= 0.0031308 { c * 12.92 } else { 1.055 * c.powf(1.0 / 2.4) - 0.055 }
}

/// `#rrggbb` or `#rrggbbaa` decoded: red, green, blue in linear light, then alpha (1 when left out); None if it isn't one.
pub fn parse_hex(s: &str) -> Option<[f64; 4]> {
    let b = s.as_bytes();
    if !matches!(b.len(), 7 | 9) || b[0] != b'#' || !s[1..].bytes().all(|c| c.is_ascii_hexdigit()) {
        return None;
    }
    let byte = |i: usize| u8::from_str_radix(&s[i..i + 2], 16).ok().map(|v| v as f64 / 255.0);
    let a = if b.len() == 9 { byte(7)? } else { 1.0 };
    Some([lin(byte(1)?), lin(byte(3)?), lin(byte(5)?), a])
}

/// Two colours mixed in linear light (alpha straight), written `#rrggbb`, or `#rrggbbaa` while it is see-through
/// (rounded half to even, as Python's `round`).
fn mix(a: &[f64; 4], b: &[f64; 4], p: f64) -> String {
    let mut s = String::from("#");
    for i in 0..3 {
        let v = (srgb(a[i] + (b[i] - a[i]) * p) * 255.0).round_ties_even() as u8;
        s += &format!("{v:02x}");
    }
    let alpha = ((a[3] + (b[3] - a[3]) * p).clamp(0.0, 1.0) * 255.0).round_ties_even() as u8;
    if alpha < 255 {
        s += &format!("{alpha:02x}");
    }
    s
}

/// A solid fill's opacity (`fillOpacity`, 0 … 1; a scene without the field is 1) from an item's props, at its own time.
pub fn fill_opacity(props: &Map<String, Value>) -> f64 {
    props.get("fillOpacity").and_then(Value::as_f64).unwrap_or(1.0).clamp(0.0, 1.0)
}

/// `hex` (`#rrggbb` or `#rrggbbaa`) with its alpha times `opacity`, written `#rrggbbaa` while it is see-through.
pub fn faded(hex: &str, opacity: f64) -> String {
    if opacity >= 1.0 || parse_hex(hex).is_none() {
        return hex.to_string();
    }
    let (rgb, a) = split_alpha(hex);
    format!("{rgb}{:02x}", ((a * opacity).clamp(0.0, 1.0) * 255.0).round_ties_even() as u8)
}

/// A colour split into `#rrggbb` and its alpha (1 for `#rrggbb`), for what draws the two apart (gradient stops).
pub fn split_alpha(hex: &str) -> (&str, f64) {
    match hex.len() {
        9 => (&hex[..7], u8::from_str_radix(&hex[7..9], 16).map_or(1.0, |v| v as f64 / 255.0)),
        _ => (hex, 1.0),
    }
}

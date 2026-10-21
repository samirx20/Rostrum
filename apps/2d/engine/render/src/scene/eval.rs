//! The one animation model (ENGINE_CONTRACT.md § 3), ported from `apps/2d/python/rostrum2d/evaluate.py` and
//! `scene.py` `frame_at`: a field with keys is decided by its keys alone; between key a and key b,
//! p = ease_a((t − a.t) / (b.t − a.t)) and the value is a + (b − a)·p; before the first key and after the last the
//! value holds. Colours mix in linear light. A layer outside start ≤ t < end is left out.

use serde_json::{Map, Value};

use super::fields::Role;
use super::{Key, KeyValue, Node};

/// One item at one time: every field's value, and its children that are showing.
#[derive(Debug)]
pub struct Item<'a> {
    pub id: &'a str,
    pub kind: &'static str,
    pub props: Map<String, Value>,
    pub effects: Vec<Item<'a>>,
    pub masks: Vec<Item<'a>>,
    pub layers: Vec<Item<'a>>,
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

/// `node` at time `t`; None for a layer that isn't showing.
pub fn at(node: &Node, t: f64) -> Option<Item<'_>> {
    eval(node, t, false)
}

/// `node` at time `t` with every layer kept, showing or not (the stage written from it checks the whole scene).
pub fn whole(node: &Node, t: f64) -> Item<'_> {
    eval(node, t, true).unwrap()
}

fn eval(node: &Node, t: f64, all: bool) -> Option<Item<'_>> {
    let mut props = node.props.clone();
    for (field, keys) in &node.anim {
        props.insert(field.clone(), track_value(keys, t));
    }
    let item = Item {
        id: &node.id,
        kind: node.kind,
        effects: node.effects.iter().filter_map(|c| eval(c, t, all)).collect(),
        masks: node.masks.iter().filter_map(|c| eval(c, t, all)).collect(),
        layers: node.layers.iter().filter_map(|c| eval(c, t, all)).collect(),
        props,
    };
    if !all && node.role == Role::Layer && !(item.num("start") <= t && t < item.num("end")) {
        return None;
    }
    Some(item)
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
                (KeyValue::Number(a), KeyValue::Number(b)) => Value::from(a + (b - a) * p),
                _ => unreachable!("a field's keys are all numbers or all colours (checked at load)"),
            };
        }
    }
    keys[keys.len() - 1].value.as_json()
}

impl KeyValue {
    fn as_json(&self) -> Value {
        match self {
            KeyValue::Number(v) => Value::from(*v),
            KeyValue::Color(written, _) => Value::String(written.clone()),
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

/// `#rrggbb` decoded to linear light; None if it isn't one.
pub fn parse_hex(s: &str) -> Option<[f64; 3]> {
    let b = s.as_bytes();
    if b.len() != 7 || b[0] != b'#' || !s[1..].bytes().all(|c| c.is_ascii_hexdigit()) {
        return None;
    }
    let ch = |i: usize| u8::from_str_radix(&s[i..i + 2], 16).ok().map(|v| lin(v as f64 / 255.0));
    Some([ch(1)?, ch(3)?, ch(5)?])
}

/// Two colours mixed in linear light, written `#rrggbb` (rounded half to even, as Python's `round`).
fn mix(a: &[f64; 3], b: &[f64; 3], p: f64) -> String {
    let mut s = String::from("#");
    for i in 0..3 {
        let v = (srgb(a[i] + (b[i] - a[i]) * p) * 255.0).round_ties_even() as u8;
        s += &format!("{v:02x}");
    }
    s
}

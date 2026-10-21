//! The scene description (ENGINE_CONTRACT.md v1): loaded and checked whole (anything unknown is refused, naming
//! the item and field), then evaluated per frame (eval.rs) and written as the stage the renderer draws (stage.rs).
//! serve's `scene`, `frame {t}`, `export` and `edit` requests are in scene_serve.rs.

pub mod ease;
pub mod eval;
pub mod fields;
pub mod fonts;
pub mod letters;
pub mod stage;
pub mod stage_type;
pub mod stage_fx;
pub mod type_font;
#[cfg(test)]
mod tests;

use std::collections::HashSet;

use serde_json::{Map, Value};

use ease::Ease;
use fields::{Kind, Role};

pub const FORMAT: &str = "rostrum-2d-scene";
pub const VERSION: u64 = 1;

/// One key: its time, its value (a number, or a colour kept as written and in linear light) and the ease of
/// the stretch it starts.
#[derive(Clone, Debug)]
pub struct Key {
    pub t: f64,
    pub value: KeyValue,
    pub ease: Ease,
}

#[derive(Clone, Debug)]
pub enum KeyValue {
    Number(f64),
    Color(String, [f64; 3]),
}

/// One item of the scene: still values (`props`, every field present), keys per animated field (sorted by time),
/// and its children.
#[derive(Clone, Debug)]
pub struct Node {
    pub id: String,
    pub kind: &'static str,
    pub role: Role,
    pub props: Map<String, Value>,
    pub anim: Vec<(String, Vec<Key>)>,
    pub effects: Vec<Node>,
    pub masks: Vec<Node>,
    pub layers: Vec<Node>,
    /// A drawing layer's drawings: (frame number it appears at, its picture), sorted by frame (contract § 2).
    pub frames: Vec<(i64, String)>,
    /// A rig's bones, iks and binds (crate::rig; RIG.md).
    pub rig: Vec<Node>,
}

#[derive(Clone, Debug)]
pub struct Scene {
    pub comp: Node,
    /// The fonts its text can name (fonts.rs): the scene's own `fonts`, then the app's.
    pub fonts: Vec<fonts::Font>,
}

impl Scene {
    pub fn load(v: &Value) -> Result<Scene, String> {
        if v["format"] != FORMAT {
            return Err(format!("not a scene description: format {} (expected \"{FORMAT}\")", v["format"]));
        }
        match v["version"].as_u64() {
            Some(VERSION) => {}
            other => return Err(format!("scene version {}; this engine reads {VERSION}", other.map_or(v["version"].to_string(), |n| n.to_string()))),
        }
        let comp = node(&v["comp"], "scene")?;
        if comp.role != Role::Comp {
            return Err(format!("{}: the scene's top item is a {}, not a comp", comp.id, comp.kind));
        }
        let mut seen = HashSet::new();
        comp.walk(&mut |n| if seen.insert(n.id.clone()) { Ok(()) } else { Err(format!("{}: the id is used twice", n.id)) })?;
        crate::rig::check(&comp)?;
        let fonts = fonts::list(&v["fonts"])?;
        type_font::register(&fonts);
        Ok(Scene { comp, fonts })
    }

    pub fn width(&self) -> u32 {
        self.comp.props["width"].as_f64().unwrap_or(0.0) as u32
    }

    pub fn height(&self) -> u32 {
        self.comp.props["height"].as_f64().unwrap_or(0.0) as u32
    }

    pub fn fps(&self) -> f64 {
        self.comp.props["fps"].as_f64().unwrap_or(30.0)
    }

    pub fn duration(&self) -> f64 {
        self.comp.props["duration"].as_f64().unwrap_or(0.0)
    }

    /// `edit` (a drag, a typed value): `[{"id", "props"?: {field: value}, "anim"?: {field: [keys] | null}}, …]`,
    /// checked whole before any of it is applied.
    pub fn edit(&mut self, edits: &Value) -> Result<usize, String> {
        let list = edits.as_array().ok_or("edit takes a list of {id, props?, anim?}")?;
        let mut next = self.comp.clone();
        for e in list {
            let id = e["id"].as_str().ok_or("an edit needs an id")?;
            let n = next.find_mut(id).ok_or_else(|| format!("{id}: no such item in the scene"))?;
            let fields = fields::of(n.kind).unwrap().1;
            for (name, value) in e["props"].as_object().into_iter().flatten() {
                let f = fields.iter().find(|f| f.0 == name).ok_or_else(|| unknown_field(id, n.kind, name, &fields))?;
                check_value(id, f, value)?;
                n.props.insert(name.clone(), value.clone());
            }
            for (name, keys) in e["anim"].as_object().into_iter().flatten() {
                n.anim.retain(|(p, _)| p != name);
                if !keys.is_null() {
                    let f = fields.iter().find(|f| f.0 == name).ok_or_else(|| unknown_field(id, n.kind, name, &fields))?;
                    n.anim.push((name.clone(), track(id, n.kind, f, keys)?));
                }
            }
            n.anim.sort_by(|a, b| a.0.cmp(&b.0));
        }
        crate::rig::check(&next)?;
        self.comp = next;
        Ok(list.len())
    }
}

impl Node {
    pub fn walk(&self, f: &mut impl FnMut(&Node) -> Result<(), String>) -> Result<(), String> {
        f(self)?;
        self.effects.iter().chain(&self.masks).chain(&self.layers).chain(&self.rig).try_for_each(|c| c.walk(f))
    }

    fn find_mut(&mut self, id: &str) -> Option<&mut Node> {
        if self.id == id {
            return Some(self);
        }
        self.effects.iter_mut().chain(&mut self.masks).chain(&mut self.layers).chain(&mut self.rig).find_map(|c| c.find_mut(id))
    }
}

fn unknown_field(id: &str, kind: &str, name: &str, fields: &[fields::Field]) -> String {
    format!("{id}: a {kind} has no field \"{name}\"; it has: {}", fields.iter().map(|f| f.0).collect::<Vec<_>>().join(", "))
}

/// One item, checked: its type known, every field present with a value of the right kind, nothing unknown,
/// children only where its role allows them.
fn node(v: &Value, parent: &str) -> Result<Node, String> {
    let obj = v.as_object().ok_or_else(|| format!("{parent}: an item must be an object"))?;
    let id = v["id"].as_str().ok_or_else(|| format!("{parent}: an item without an id"))?.to_string();
    let ty = v["type"].as_str().ok_or_else(|| format!("{id}: no type"))?;
    let kind = fields::TYPES.iter().copied().find(|t| *t == ty).ok_or_else(|| format!("{id}: unknown item type \"{ty}\"; this engine draws: {}", fields::TYPES.join(", ")))?;
    let (role, fields) = fields::of(kind).unwrap();
    for k in obj.keys() {
        if !matches!(k.as_str(), "id" | "type" | "props" | "anim" | "effects" | "masks" | "layers") && !(k == "frames" && matches!(kind, "drawing" | "video")) && !(k == "rig" && kind == "rig") {
            return Err(format!("{id}: unknown part \"{k}\" (an item has id, type, props, anim, effects, masks, layers; a drawing or video also frames; a rig also rig)"));
        }
    }
    let props = v["props"].as_object().ok_or_else(|| format!("{id}: no props"))?.clone();
    for name in props.keys() {
        if !fields.iter().any(|f| f.0 == name) {
            return Err(unknown_field(&id, kind, name, &fields));
        }
    }
    for f in &fields {
        check_value(&id, f, props.get(f.0).ok_or_else(|| format!("{id}: field \"{}\" is missing (the scene carries every field)", f.0))?)?;
    }
    let mut anim = vec![];
    for (name, keys) in v["anim"].as_object().into_iter().flatten() {
        let f = fields.iter().find(|f| f.0 == name).ok_or_else(|| unknown_field(&id, kind, name, &fields))?;
        anim.push((name.clone(), track(&id, kind, f, keys)?));
    }
    let kids = |part: &str, allowed: bool, want: &[Role]| -> Result<Vec<Node>, String> {
        let Some(list) = v.get(part) else { return Ok(vec![]) };
        if !allowed {
            return Err(format!("{id}: a {kind} has no {part}"));
        }
        let list = list.as_array().ok_or_else(|| format!("{id}: {part} must be a list"))?;
        let out = list.iter().map(|c| node(c, &id)).collect::<Result<Vec<_>, _>>()?;
        match out.iter().find(|c| !want.contains(&c.role)) {
            Some(c) => Err(format!("{}: a {} can't be in {id}'s {part}", c.id, c.kind)),
            None => Ok(out),
        }
    };
    let layer = role == Role::Layer;
    Ok(Node {
        effects: kids("effects", layer, &[Role::Effect])?,
        masks: kids("masks", layer, &[Role::Mask])?,
        layers: kids("layers", role == Role::Comp || matches!(kind, "group" | "rig"), &[Role::Layer])?,
        rig: kids("rig", kind == "rig", &[Role::Rig])?,
        frames: if matches!(kind, "drawing" | "video") { drawings(&id, &v["frames"])? } else { vec![] },
        id, kind, role, props, anim,
    })
}

/// A drawing's `frames: [{"at": n, "src": "…png"}, …]`, sorted by `at`; every picture must exist.
fn drawings(id: &str, v: &Value) -> Result<Vec<(i64, String)>, String> {
    let list = v.as_array().ok_or_else(|| format!("{id}: a drawing needs frames: [{{at, src}}, …]"))?;
    let mut out = vec![];
    for f in list {
        let at = f["at"].as_i64().ok_or_else(|| format!("{id}.frames: a drawing without a whole frame number at"))?;
        let src = f["src"].as_str().ok_or_else(|| format!("{id}.frames: the drawing at frame {at} has no src"))?;
        if !std::path::Path::new(src).is_file() {
            return Err(format!("{id}.frames: the picture of the drawing at frame {at} is missing: {src}"));
        }
        out.push((at, src.to_string()));
    }
    out.sort_by_key(|f| f.0);
    Ok(out)
}

fn check_value(id: &str, f: &fields::Field, v: &Value) -> Result<(), String> {
    let ok = match f.1 {
        Kind::Number => v.is_number(),
        Kind::Toggle => v.is_boolean(),
        Kind::Text => v.is_string(),
        Kind::Color => v.as_str().is_some_and(|s| eval::parse_hex(s).is_some()),
        Kind::Choice(options) => v.as_str().is_some_and(|s| options.contains(&s)),
    };
    if ok {
        return Ok(());
    }
    let want = match f.1 {
        Kind::Number => "a number".to_string(),
        Kind::Toggle => "true or false".to_string(),
        Kind::Text => "text".to_string(),
        Kind::Color => "a colour #rrggbb".to_string(),
        Kind::Choice(o) => format!("one of {}", o.join(", ")),
    };
    Err(format!("{id}.{}: {v} is not {want}", f.0))
}

/// A field's keys, checked and sorted by time (stable, as Python's `sorted`).
fn track(id: &str, kind: &str, f: &fields::Field, keys: &Value) -> Result<Vec<Key>, String> {
    let name = f.0;
    if !fields::animatable(kind, f) {
        return Err(format!("{id}.{name}: this field can't be animated"));
    }
    let list = keys.as_array().filter(|l| !l.is_empty()).ok_or_else(|| format!("{id}.{name}: anim must be a non-empty list of keys"))?;
    let mut out = vec![];
    for k in list {
        let obj = k.as_object().ok_or_else(|| format!("{id}.{name}: a key must be an object"))?;
        if let Some(bad) = obj.keys().find(|k| !matches!(k.as_str(), "t" | "v" | "c" | "ease" | "x1" | "y1" | "x2" | "y2" | "stiffness" | "damping")) {
            return Err(format!("{id}.{name}: a key has no field \"{bad}\""));
        }
        let t = k["t"].as_f64().ok_or_else(|| format!("{id}.{name}: a key without a time t"))?;
        let value = match f.1 {
            Kind::Color => {
                let c = k["c"].as_str().ok_or_else(|| format!("{id}.{name}: a colour key needs c (#rrggbb) at t={t}"))?;
                KeyValue::Color(c.to_string(), eval::parse_hex(c).ok_or_else(|| format!("{id}.{name}: {c} is not a colour #rrggbb"))?)
            }
            _ => KeyValue::Number(k["v"].as_f64().ok_or_else(|| format!("{id}.{name}: a number key needs v at t={t}"))?),
        };
        let ease_name = match &k["ease"] {
            Value::Null => "smooth",
            e => e.as_str().ok_or_else(|| format!("{id}.{name}: ease must be a name"))?,
        };
        let ease = Ease::parse(ease_name, |p| k[p].as_f64()).map_err(|e| format!("{id}.{name}: {e}"))?;
        out.push(Key { t, value, ease });
    }
    out.sort_by(|a, b| a.t.total_cmp(&b.t));
    Ok(out)
}

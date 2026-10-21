//! A window from its spec (docs/phase1/GRADING.md §3.2; window.rs): `{ "shape": "ellipse" | "linear" | "gradient" | "polygon" |
//! "bezier", … }` with the shape's fields (`centre`, `size`, `rotation`; `from`, `to`, `width`; `points`; `nodes`: [{ `p`, `in`,
//! `out` }], handles as offsets), `mode` (`add` default, `subtract`, `intersect`), `soft` (a number: both edges; or `{ inner,
//! outer }`), `invert`, `opacity` and `transform` (`{ pan, scale: n | [sx, sy], rotate }`). Unknown fields and wrong values are errors.
use super::spec::{Obj, fields, get};
use super::window::{Mode, Node, Shape, Window};
use serde_json::Value;

type P = [f32; 2];

fn pair(v: &Value, what: &str) -> Result<P, String> {
    match v.as_array().map(|a| a.iter().map(|x| x.as_f64()).collect::<Vec<_>>()).as_deref() {
        Some([Some(x), Some(y)]) => Ok([*x as f32, *y as f32]),
        _ => Err(format!("{what} is [x, y] (fractions of the frame); got {v}")),
    }
}

impl Window {
    pub fn from_spec(v: &Value, at: &str) -> Result<Window, String> {
        let shape = v.get("shape").and_then(Value::as_str).ok_or_else(|| format!("{at}: names its `shape` (ellipse, linear, gradient, polygon, bezier)"))?;
        let extra: &[&str] = match shape {
            "ellipse" => &["centre", "size", "rotation"],
            "linear" => &["from", "to", "width"],
            "gradient" => &["from", "to"],
            "polygon" => &["points"],
            "bezier" => &["nodes"],
            _ => return Err(format!("{at}: unknown shape `{shape}` (ellipse, linear, gradient, polygon, bezier)")),
        };
        let allowed: Vec<&str> = ["shape", "mode", "soft", "invert", "opacity", "transform"].iter().chain(extra).copied().collect();
        let o = Obj { o: fields(v, at, &allowed)?, what: at.to_string() };
        let p = |k: &str| -> Result<P, String> { pair(get(o.o, k).ok_or_else(|| format!("{at}: a {shape} window needs `{k}`"))?, &format!("{at}: `{k}`")) };
        let list = |k: &str| -> Result<&Vec<Value>, String> { get(o.o, k).and_then(Value::as_array).ok_or_else(|| format!("{at}: a {shape} window needs `{k}`, a list")) };
        let shape = match shape {
            "ellipse" => Shape::Ellipse { centre: p("centre")?, size: p("size")?, rotation: o.num("rotation", 0.0)? },
            "linear" => Shape::Linear { from: p("from")?, to: p("to")?, width: o.num("width", f32::NAN)? },
            "gradient" => Shape::Gradient { from: p("from")?, to: p("to")? },
            "polygon" => Shape::Polygon(list("points")?.iter().map(|x| pair(x, &format!("{at}: a point"))).collect::<Result<_, _>>()?),
            _ => Shape::Bezier(
                list("nodes")?
                    .iter()
                    .map(|n| {
                        let no = Obj { o: fields(n, &format!("{at}: a node"), &["p", "in", "out"])?, what: format!("{at}: a node") };
                        let pt = |k: &str, d: P| no.o.get(k).filter(|x| !x.is_null()).map_or(Ok(d), |x| pair(x, &format!("{at}: node `{k}`")));
                        Ok(Node { p: pt("p", [f32::NAN; 2])?, hin: pt("in", [0.0; 2])?, hout: pt("out", [0.0; 2])? })
                    })
                    .collect::<Result<_, String>>()?,
            ),
        };
        let mut w = Window::new(shape);
        w.mode = match o.word("mode", &["add", "subtract", "intersect"])? {
            Some("subtract") => Mode::Subtract,
            Some("intersect") => Mode::Intersect,
            _ => Mode::Add,
        };
        w.soft = match get(o.o, "soft") {
            None => [0.0; 2],
            Some(Value::Number(n)) => [n.as_f64().unwrap_or(0.0) as f32; 2],
            Some(s) => {
                let so = Obj { o: fields(s, &format!("{at}: `soft`"), &["inner", "outer"])?, what: format!("{at}: `soft`") };
                [so.num("inner", 0.0)?, so.num("outer", 0.0)?]
            }
        };
        w.invert = match get(o.o, "invert") {
            None => false,
            Some(x) => x.as_bool().ok_or_else(|| format!("{at}: `invert` is true or false; got {x}"))?,
        };
        w.opacity = o.num("opacity", 1.0)?;
        if let Some(t) = get(o.o, "transform") {
            let to = Obj { o: fields(t, &format!("{at}: `transform`"), &["pan", "scale", "rotate"])?, what: format!("{at}: `transform`") };
            if let Some(x) = get(to.o, "pan") {
                w.pan = pair(x, &format!("{at}: transform `pan`"))?;
            }
            w.scale = match get(to.o, "scale") {
                None => [1.0; 2],
                Some(Value::Number(n)) => [n.as_f64().unwrap_or(1.0) as f32; 2],
                Some(x) => pair(x, &format!("{at}: transform `scale` (a number, or [sx, sy])"))?,
            };
            w.rotate = to.num("rotate", 0.0)?;
        }
        Ok(w)
    }
}

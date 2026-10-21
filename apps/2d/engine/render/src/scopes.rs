//! Scopes (rostrum-color `scope`, docs/phase1/GRADING.md §5) for a frame the renderer made. Two doors:
//! - `serve`'s frame request with `scopes: {…}`: measured from the F16 frame as the surface stores it (before the
//!   8-bit output step), in the render's colour pipeline, then the numbers come back in the reply and the pictures
//!   are written as PNGs.
//! - `rostrum2d-render scope <spec.json>`: an image file (PNG: display code values; EXR: scene linear, `inputSpace`
//!   `acescg` or `lin_rec709`) or `{ "diff": [a, b] }` (two scope results compared). Prints `{ scope, files }`.
//!
//! The request (both doors): `space` (`display` default, `acescg`, `acescct`), `region` (`[x, y, w, h]` or
//! `{x, y, w, h}` in frame fractions), `parts` (blocks to return), `histogram` (16 | 64), `zones`, `images`
//! (`true` or names from `draw::NAMES`), `sheet` (one PNG of everything), `title`, `dir`, `name`.

use rostrum_color::pipeline::{Pipeline, Working};
use rostrum_color::scope::draw::{self, Image};
use rostrum_color::scope::measure::{measure, Options};
use rostrum_color::scope::{compare, Domain, Frame};
use rostrum_color::view::Target;
use serde_json::{json, Value};

pub fn domain_of(req: &Value, hdr: bool) -> Result<Domain, String> {
    Domain::parse(req["space"].as_str().unwrap_or("display"), hdr)
}

/// A premultiplied F16 frame (rgba, as the surface stores it) in `domain`; transparent pixels read as black (the
/// frame as seen over black).
pub fn from_f16(pipeline: &Pipeline, raw: &[u8], width: usize, height: usize, domain: Domain) -> Frame {
    let table = crate::pixels::halves();
    let n = width * height;
    let threads = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4).min(8);
    let band = n.div_ceil(threads).max(1);
    let mut px = vec![[0f32; 3]; n];
    std::thread::scope(|s| {
        for (k, dst) in px.chunks_mut(band).enumerate() {
            s.spawn(move || {
                for (j, o) in dst.iter_mut().enumerate() {
                    let p = &raw[(k * band + j) * 8..(k * band + j) * 8 + 8];
                    let v = |c: usize| table[u16::from_le_bytes([p[c * 2], p[c * 2 + 1]]) as usize];
                    let c = [v(0), v(1), v(2)].map(|x| if x.is_finite() { x } else { 0.0 });
                    *o = domain.from_working(pipeline, c);
                }
            });
        }
    });
    Frame::new(width, height, domain, px)
}

fn save(img: &Image, path: &std::path::Path) -> Result<(), String> {
    image::RgbaImage::from_raw(img.width as u32, img.height as u32, img.rgba.clone())
        .ok_or("scope picture size mismatch")?
        .save(path)
        .map_err(|e| format!("writing {}: {e}", path.display()))
}

/// Measures `frame` (already in the requested space) and writes the pictures the request asks for.
pub fn run(frame: &Frame, req: &Value) -> Result<Value, String> {
    let mut o = Options::parse(req)?;
    o.region = o.region.resolve(frame.width, frame.height);
    let scope = measure(frame, &o)?;
    let mut files = serde_json::Map::new();
    let wants_images = req["images"].as_bool() == Some(true) || req["images"].is_array();
    let sheet = req["sheet"].as_bool() == Some(true);
    if wants_images || sheet {
        let dir = std::path::PathBuf::from(req["dir"].as_str().ok_or("images and sheet need `dir` (where the PNGs go)")?);
        std::fs::create_dir_all(&dir).map_err(|e| format!("{}: {e}", dir.display()))?;
        let name = req["name"].as_str().unwrap_or("scope");
        if wants_images {
            let names: Vec<String> = match req["images"].as_array() {
                Some(a) => a.iter().filter_map(|v| v.as_str().map(String::from)).collect(),
                None => draw::NAMES.iter().map(|s| s.to_string()).collect(),
            };
            let refs: Vec<&str> = names.iter().map(String::as_str).collect();
            for (n, img) in draw::draw(frame, &o.region, &refs)? {
                let path = dir.join(format!("{name}_{n}.png"));
                save(&img, &path)?;
                files.insert(n, json!(path.to_string_lossy()));
            }
        }
        if sheet {
            let title = req["title"].as_str().map(String::from).unwrap_or_else(|| format!("{}x{}  SPACE {}", frame.width, frame.height, frame.domain.id().to_uppercase()));
            let path = dir.join(format!("{name}_sheet.png"));
            save(&draw::sheet(frame, &o.region, &title), &path)?;
            files.insert("sheet".into(), json!(path.to_string_lossy()));
        }
    }
    Ok(json!({ "scope": scope, "files": files }))
}

/// An image file as a frame: PNG / JPEG as display code values, EXR as scene-linear light in `input_space`.
fn read_file(path: &str, input_space: Option<&str>, target: Domain) -> Result<Frame, String> {
    let img = image::open(path).map_err(|e| format!("{path}: {e}"))?;
    let is_exr = path.to_ascii_lowercase().ends_with(".exr");
    let rgba = img.to_rgba32f();
    let (w, h) = (rgba.width() as usize, rgba.height() as usize);
    let px: Vec<[f32; 3]> = rgba.pixels().map(|p| [p.0[0], p.0[1], p.0[2]]).collect();
    let src = if is_exr {
        let lower = path.to_ascii_lowercase();
        let id = input_space.unwrap_or(if lower.contains("acescg") { "acescg" } else if lower.contains("rec709") { "lin_rec709" } else {
            return Err(format!("{path}: an EXR holds scene linear light: say which with inputSpace (acescg or lin_rec709)"));
        });
        let m = rostrum_color::convert::gamut_matrix(id, "acescg").map_err(|_| format!("inputSpace `{id}` is not a gamut id (acescg, lin_rec709, lin_rec2020 …)"))?;
        let px = px.iter().map(|&c| rostrum_color::matrix::apply(&m, c.map(f64::from)).map(|v| v as f32)).collect();
        Frame::new(w, h, Domain::AcesCg, px)
    } else {
        if let Some(s) = input_space.filter(|s| *s != "display") {
            return Err(format!("{path}: PNG / JPEG values are display code values; inputSpace `{s}` applies to EXR files only"));
        }
        Frame::new(w, h, Domain::Display { hdr: false }, px)
    };
    Ok(src.to(target))
}

/// `rostrum2d-render scope <spec.json>`.
pub fn run_cli(args: &[String]) {
    let result = (|| -> Result<Value, String> {
        let [spec] = args else { return Err("usage: rostrum2d-render scope <spec.json>".into()) };
        let req: Value = serde_json::from_str(&std::fs::read_to_string(spec).map_err(|e| format!("{spec}: {e}"))?).map_err(|e| e.to_string())?;
        if let Some(d) = req.get("diff") {
            let [a, b] = d.as_array().map(Vec::as_slice).unwrap_or(&[]) else { return Err("diff is [scopeA, scopeB]".into()) };
            return compare::diff(a, b);
        }
        let input = req["input"].as_str().ok_or("scope needs `input` (an image file) or `diff`")?;
        let target = domain_of(&req, req["hdr"].as_bool() == Some(true))?;
        let frame = read_file(input, req["inputSpace"].as_str(), target)?;
        run(&frame, &req)
    })();
    match result {
        Ok(v) => println!("{v}"),
        Err(e) => {
            eprintln!("{e}");
            std::process::exit(1);
        }
    }
}

/// Whether a render's pipeline targets HDR (the display scopes then read PQ Rec.2020).
pub fn is_hdr(p: &Pipeline) -> bool {
    p.target == Target::Hdr1000
}

// ---- G7: shot match and auto balance (rostrum-color `grade::fit`) --------------------------------------------------

/// A frame's scene light as the compositor made it (ACEScg, graded), written for `match` to read: the magic
/// `RSMPLACG`, width and height (u32 LE), then width × height × 3 f32 LE, top row first.
const SAMPLE_MAGIC: &[u8; 8] = b"RSMPLACG";

pub fn write_sample(frame: &Frame, path: &str) -> Result<(), String> {
    if frame.domain != Domain::AcesCg {
        return Err("a sample is written in ACEScg".into());
    }
    let mut out = Vec::with_capacity(16 + frame.px.len() * 12);
    out.extend_from_slice(SAMPLE_MAGIC);
    out.extend_from_slice(&(frame.width as u32).to_le_bytes());
    out.extend_from_slice(&(frame.height as u32).to_le_bytes());
    for p in &frame.px {
        for c in p {
            out.extend_from_slice(&c.to_le_bytes());
        }
    }
    std::fs::write(path, out).map_err(|e| format!("writing {path}: {e}"))
}

fn read_sample(path: &str) -> Result<Frame, String> {
    let b = std::fs::read(path).map_err(|e| format!("{path}: {e}"))?;
    if b.len() < 16 || &b[..8] != SAMPLE_MAGIC {
        return Err(format!("{path} is not a frame sample (RSMPLACG)"));
    }
    let (w, h) = (u32::from_le_bytes(b[8..12].try_into().unwrap()) as usize, u32::from_le_bytes(b[12..16].try_into().unwrap()) as usize);
    if b.len() != 16 + w * h * 12 {
        return Err(format!("{path}: a {w}x{h} sample is {} bytes, the file has {}", 16 + w * h * 12, b.len()));
    }
    let f = |i: usize| f32::from_le_bytes(b[16 + i * 4..20 + i * 4].try_into().unwrap());
    Ok(Frame::new(w, h, Domain::AcesCg, (0..w * h).map(|i| [f(i * 3), f(i * 3 + 1), f(i * 3 + 2)]).collect()))
}

const MATCH_KEYS: [&str; 12] = ["mode", "shot", "reference", "referenceInput", "strength", "parts", "region", "referenceRegion", "keepSkin", "black", "white", "hueRange"];

/// `{ "match": {...} }` on a `serve` session (so the fit sees the project's view): `mode` `match` (`shot` and `reference`
/// samples, or `reference` an image file with `referenceInput`) or `auto`; the rest are the options of
/// `grade.match` / `grade.auto`. Replies `{ fields, before, after, iterations, residual, notes }`.
/// `hueRange`: `{ from, to }` or a list of them, degrees (`from` > `to` wraps through red); absent = every hue.
fn hue_ranges(v: &Value) -> Result<Vec<(f64, f64)>, String> {
    let one = |r: &Value| match (r["from"].as_f64(), r["to"].as_f64()) {
        (Some(a), Some(b)) if a.is_finite() && b.is_finite() => Ok((a, b)),
        _ => Err("hueRange is { from, to } in degrees (or a list of them)".to_string()),
    };
    match v {
        Value::Null => Ok(vec![]),
        Value::Array(a) => a.iter().map(one).collect(),
        r => Ok(vec![one(r)?]),
    }
}

pub fn run_match(pipeline: &Pipeline, req: &Value) -> Result<Value, String> {
    use rostrum_color::grade::fit::{fit_auto, fit_match, AutoOptions, AutoParts, MatchOptions, MatchParts};
    use rostrum_color::scope::Region;
    let obj = req.as_object().ok_or("match is an object")?;
    if let Some(k) = obj.keys().find(|k| !MATCH_KEYS.contains(&k.as_str())) {
        return Err(format!("unknown match option `{k}` (options: {})", MATCH_KEYS.join(", ")));
    }
    let domain = Domain::Display { hdr: is_hdr(pipeline) };
    let shot = read_sample(req["shot"].as_str().ok_or("match needs `shot`: a frame sample")?)?;
    // The shot's graded ACEScg light through the project's view (the pipeline's working space in between).
    let to_lin = Domain::AcesCg.to_lin709_fn();
    let to_srgb = Domain::Display { hdr: false }.from_lin709_fn();
    let p = *pipeline;
    let working = p.working;
    let to_working = move |cg: rostrum_color::Rgb| match working {
        Working::AcesCg => cg,
        Working::LinearDisplay => to_lin(cg),
        Working::Display => to_srgb(to_lin(cg)),
    };
    let view = move |cg: rostrum_color::Rgb| domain.from_working(&p, to_working(cg));
    let region = Region::parse(&req["region"])?;
    let strings = |k: &str| -> Result<Option<Vec<String>>, String> {
        match &req[k] {
            Value::Null => Ok(None),
            Value::Array(a) => a.iter().map(|v| v.as_str().map(String::from).ok_or(format!("{k} is a list of names"))).collect::<Result<_, _>>().map(Some),
            _ => Err(format!("{k} is a list of names")),
        }
    };
    let fit = match req["mode"].as_str() {
        Some("match") => {
            let reference = match (&req["reference"], req["referenceInput"].as_str()) {
                (Value::String(path), Some("sample")) => {
                    let r = read_sample(path)?;
                    Frame::new(r.width, r.height, domain, r.px.iter().map(|&c| view(c)).collect())
                }
                (Value::String(path), input) => read_file(path, input, domain)?,
                _ => return Err("match needs `reference`: a frame sample or an image file".into()),
            };
            let mut o = MatchOptions { region, ..Default::default() };
            if let Some(p) = strings("parts")? {
                o.parts = MatchParts::parse(&p)?;
            }
            if let Some(s) = req["strength"].as_f64() {
                o.strength = s;
            } else if !req["strength"].is_null() {
                return Err("strength is a number, 0 … 1".into());
            }
            if !req["referenceRegion"].is_null() {
                o.reference_region = Some(Region::parse(&req["referenceRegion"])?);
            }
            o.keep_skin = req["keepSkin"].as_bool() == Some(true);
            o.hue_ranges = hue_ranges(&req["hueRange"])?;
            fit_match(&shot, &reference, &view, domain, &o)?
        }
        Some("auto") => {
            let mut o = AutoOptions { region, ..Default::default() };
            if let Some(p) = strings("parts")? {
                o.parts = AutoParts::parse(&p)?;
            }
            if let Some(v) = req["black"].as_f64() {
                o.black = v;
            }
            if let Some(v) = req["white"].as_f64() {
                o.white = v;
            }
            fit_auto(&shot, &view, domain, &o)?
        }
        _ => return Err("match `mode` is `match` or `auto`".into()),
    };
    Ok(json!({ "fields": fit.fields, "before": fit.before, "after": fit.after, "iterations": fit.iterations, "residual": fit.residual, "notes": fit.notes }))
}

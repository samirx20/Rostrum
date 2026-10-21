//! Resources a stage page asks for: data: URLs (fonts, inline images) and the host's local assets
//! (`/__local_asset?p=<path>`, the URLs the prepared document carries for video frames, mattes, depth
//! maps and images; served by the export page's HTTP server in Chromium, read from disk here).
//! A resource that cannot be loaded is recorded, and the frame that asked for it fails naming it.
//!
//! A local asset tagged with its colour (`&color=<input>`: `display`, or a rostrum-color space id for
//! scene-referred pictures: 3D frames, log or HDR footage) is decoded here at full precision and converted into the
//! render's working space (color.rs `rhalf`); `&view=<id>` gives a scene-referred picture its own view (a 3D
//! clip's scene). An untagged or `display` 8-bit picture under the display working
//! space passes through untouched, as before; so does anything untagged (fonts too).

use std::sync::{Arc, Mutex};

use blitz_traits::net::{NetHandler, NetProvider, Request};
use rostrum_color::pipeline::{Input, Pipeline, Working};

use crate::color::Spec;

#[derive(Clone)]
pub struct Assets {
    pub failures: Arc<Mutex<Vec<String>>>,
    color: Spec,
}

impl Assets {
    pub fn new(color: Spec) -> Assets {
        Assets { failures: Default::default(), color }
    }
}

/// The display working space: pictures load as they are (tools that only lay out or measure a page).
impl Default for Assets {
    fn default() -> Assets {
        Assets::new(Spec::default())
    }
}

/// The document base URL: relative asset paths resolve against it.
pub const BASE_URL: &str = "http://rostrum.local/";

impl NetProvider for Assets {
    fn fetch(&self, _doc_id: usize, request: Request, handler: Box<dyn NetHandler>) {
        let url = request.url.to_string();
        // url(#id) (a mask or filter in the page itself) resolves to the page: nothing to load.
        if request.url.fragment().is_some() && url.split('#').next() == Some(BASE_URL) {
            return;
        }
        // Kept between frames and page shells (asset_cache.rs): a picture shown again is not read and converted again.
        match crate::asset_cache::kept(&request.url, &self.colour_key(), || load(&request.url).and_then(|b| self.in_working_space(&request.url, b))) {
            Ok(bytes) => handler.bytes(url, bytes),
            Err(e) => self.failures.lock().unwrap().push(format!("{}: {e}", short(&url))),
        }
    }
}

impl Assets {
    /// The bytes `url` loads as, converted like an `<img>`'s: the loader an SVG `feImage` with `&color=` uses (a comp's
    /// still image enters in the working space; anyrender `filters::images::set_loader`, installed by serve.rs). A failure
    /// is recorded like a fetch's, so the frame fails naming it.
    pub fn decode(&self, url: &str) -> Result<Vec<u8>, String> {
        let parsed = blitz_traits::net::Url::parse(url).map_err(|e| format!("{}: {e}", short(url)))?;
        crate::asset_cache::kept(&parsed, &self.colour_key(), || load(&parsed).and_then(|b| self.in_working_space(&parsed, b))).map(|b| b.to_vec()).inspect_err(|e| self.failures.lock().unwrap().push(format!("{}: {e}", short(url))))
    }

    /// Decodes `url` (as the page names it, resolved against the page) into the asset cache before anything asks for it, with the
    /// key and conversion a fetch uses; skipped when kept or being decoded. A failure is dropped: the fetch that needs it reports it.
    pub fn warm(&self, url: &str) -> crate::asset_cache::Warmed {
        let Ok(parsed) = blitz_traits::net::Url::parse(BASE_URL).and_then(|b| b.join(url)) else { return crate::asset_cache::Warmed::Done };
        crate::asset_cache::warm(&parsed, &self.colour_key(), || load(&parsed).and_then(|b| self.in_working_space(&parsed, b)))
    }

    /// Whether `url` is in the asset cache already (a frame's `timing.decoded`: serve.rs).
    pub fn is_kept(&self, url: &str) -> bool {
        blitz_traits::net::Url::parse(BASE_URL).and_then(|b| b.join(url)).is_ok_and(|u| crate::asset_cache::is_kept(&u, &self.colour_key()))
    }

    /// Decodes `urls` into the asset cache on up to `threads` threads at once (a frame's pictures before its layout and paint).
    pub fn warm_all(&self, urls: &[String], threads: usize) {
        let next = std::sync::atomic::AtomicUsize::new(0);
        let work = || {
            while let Some(u) = urls.get(next.fetch_add(1, std::sync::atomic::Ordering::Relaxed)) {
                // A file written this instant is read now all the same (the frame needs it; its fetch would read it anyway).
                if self.warm(u) == crate::asset_cache::Warmed::NotYet {
                    if let Ok(parsed) = blitz_traits::net::Url::parse(BASE_URL).and_then(|b| b.join(u)) {
                        let _ = crate::asset_cache::kept(&parsed, &self.colour_key(), || load(&parsed).and_then(|b| self.in_working_space(&parsed, b)));
                    }
                }
            }
        };
        match threads.min(urls.len()) {
            0 => {}
            1 => work(),
            n => std::thread::scope(|s| {
                for _ in 0..n {
                    s.spawn(work);
                }
            }),
        }
    }

    /// What a converted picture depends on besides its URL: the working space, view and target (asset_cache.rs key).
    fn colour_key(&self) -> String {
        let p = &self.color.pipeline;
        format!("{:p}|{:?}|{:?}", p.view, p.working, p.target)
    }

    /// A picture's bytes as the renderer should draw them: converted into the working space when its colour
    /// needs it (module doc), else as they are.
    fn in_working_space(&self, url: &blitz_traits::net::Url, bytes: Vec<u8>) -> Result<Vec<u8>, String> {
        // Untagged resources (fonts, 8-bit pictures) load as they are; Skia converts an untagged picture as sRGB.
        let Some(tag) = url.query_pairs().find(|(k, _)| k == "color").map(|(_, v)| v.into_owned()) else { return Ok(bytes) };
        // `raw`: float RGBA already premultiplied in the working space (an OpenFX result, ofxPrep.ts): to half floats as it is.
        if tag == "raw" {
            let rgba = image::load_from_memory(&bytes).map_err(|e| format!("decoding a raw picture: {e}"))?.to_rgba32f();
            return Ok(raw_half(rgba.as_raw(), rgba.width(), rgba.height()));
        }
        let input = Input::parse(&tag)?;
        // An EXR is always decoded here (Skia cannot read one): a data pass tagged with the working space (passPrep.ts) keeps its numbers.
        if matches!(input, Input::Display) && self.color.pipeline.working == Working::Display && !deep_png(&bytes) && !exr(&bytes) && !raw_handoff(&bytes) {
            return Ok(bytes);
        }
        // An 8-bit display picture in a linear working space (a playing edit's footage frames: videoFrameSource.ts decodes them
        // to 8-bit) enters as Skia draws an untagged sRGB picture: the sRGB curve and Rec.709 → working primaries, the same
        // maths as `display_light` (color.rs acescg_space), done on the GPU. So it is decoded here to raw 8-bit RGBA (RRGBA8:
        // half the bytes of RHALF, no float conversion per pixel) and uploaded as it is.
        if matches!(input, Input::Display) && !deep_png(&bytes) && !exr(&bytes) && !raw_handoff(&bytes) && !url.query_pairs().any(|(k, _)| k == "grade" || k == "view" || k == "bg") {
            let img = image::load_from_memory(&bytes).map_err(|e| format!("decoding a picture: {e}"))?;
            if matches!(img.color(), image::ColorType::Rgb8 | image::ColorType::Rgba8 | image::ColorType::L8 | image::ColorType::La8) {
                let rgba = img.into_rgba8();
                let mut out = Vec::with_capacity(16 + rgba.len());
                out.extend_from_slice(blitz_dom::net::RGBA8_MAGIC);
                out.extend_from_slice(&rgba.width().to_le_bytes());
                out.extend_from_slice(&rgba.height().to_le_bytes());
                out.extend_from_slice(rgba.as_raw());
                return Ok(out);
            }
        }
        // A scene-referred picture may name its own view (a 3D clip shows through its scene's view: C6).
        let pipeline = match url.query_pairs().find(|(k, _)| k == "view") {
            Some((_, v)) => Pipeline::new(self.color.pipeline.working, &v, self.color.pipeline.target)?,
            None => self.color.pipeline,
        };
        // A raw handoff frame (rostrum-3d post/output.rs write_raw_half, the app's live preview): premultiplied half floats.
        if raw_handoff(&bytes) {
            // Already in the working space (a pass picture tagged with it: passPrep.ts), nothing laid under, graded or viewed: the halves
            // as they are, without a trip through floats and the colour maths (which would give the same numbers).
            let as_is = matches!((&input, self.color.pipeline.working), (Input::Display, Working::Display)) || (tag == "acescg" && self.color.pipeline.working == Working::AcesCg);
            if as_is && !url.query_pairs().any(|(k, v)| k == "grade" || k == "view" || (k == "bg" && v != "transparent")) {
                return rhf_as_is(&bytes);
            }
            let (w, h, rgba) = read_raw_half(&bytes)?;
            let grade = match url.query_pairs().find(|(k, _)| k == "grade") {
                Some((_, f)) => Some(scene_grade(&f)?),
                None => None,
            };
            let under = match url.query_pairs().find(|(k, _)| k == "bg") {
                Some((_, v)) if v != "transparent" && matches!(input, Input::Scene { .. }) => Some(pipeline.display_to_scene(hex_colour(&v)?)),
                _ => None,
            };
            // A playing preview's frame (`&fast=1`): the grade and view through a table (color.rs SceneLut), made once per view and grade.
            let fast = url.query_pairs().any(|(k, v)| k == "fast" && v == "1") && matches!(input, Input::Scene { .. });
            let lut = if fast { Some(scene_lut(&pipeline, url.query_pairs().find(|(k, _)| k == "grade").map(|(_, v)| v.into_owned()), grade.clone())) } else { None };
            return Ok(crate::color::rhalf_with(&pipeline, &input, grade.as_deref(), under, w, h, &rgba, true, lut.as_deref()));
        }
        let img = image::load_from_memory(&bytes).map_err(|e| format!("decoding a colour-managed picture: {e}"))?;
        let rgba = img.to_rgba32f();
        // OpenEXR stores premultiplied colour; every other format here is straight.
        let premultiplied = bytes.starts_with(&[0x76, 0x2f, 0x31, 0x01]);
        // A scene's grade (`&grade=<spec.json>`: grade_cmd.rs) runs on its light before the view.
        let grade = match url.query_pairs().find(|(k, _)| k == "grade") {
            Some((_, f)) => Some(scene_grade(&f)?),
            None => None,
        };
        // The scene's background (`&bg=#rrggbb`, a display colour as authored) under its light, before its grade and view, as the
        // scene's own frame has it: the light the picture's view shows as that colour (exact on screen when the render's view is
        // the scene's: renderColor.ts sharedSceneView). The CSS background threeHandoff.ts lays is then covered.
        let under = match url.query_pairs().find(|(k, _)| k == "bg") {
            Some((_, v)) if v != "transparent" && matches!(input, Input::Scene { .. }) => Some(pipeline.display_to_scene(hex_colour(&v)?)),
            _ => None,
        };
        Ok(crate::color::rhalf(&pipeline, &input, grade.as_deref(), under, rgba.width(), rgba.height(), rgba.as_raw(), premultiplied))
    }
}

/// The pictures `markup` names that load through here (assets.rs `load`): `/__local_asset?p=…`, `file:` and `data:` URLs in any
/// attribute or CSS `url(…)` (`src`, `href`, `xlink:href`, an effect's `images="name href;…"`), HTML-unescaped, each once.
pub fn picture_urls(markup: &str, out: &mut Vec<String>) {
    for start in ["/__local_asset?", "file:", "data:"] {
        let mut from = 0;
        while let Some(at) = markup[from..].find(start).map(|i| from + i) {
            // A data: URL holds `;` (`;base64`); a local one's `;` is only an entity's end (`&amp;`).
            let data = start == "data:";
            let mut url = String::new();
            let mut rest = &markup[at..];
            while let Some(c) = rest.chars().next() {
                if rest.starts_with("&amp;") {
                    url.push('&');
                    rest = &rest[5..];
                    continue;
                }
                if c == '&' || c == '"' || c == '\'' || c == ')' || c == '<' || c == '>' || c.is_whitespace() || (c == ';' && !data) {
                    break;
                }
                url.push(c);
                rest = &rest[c.len_utf8()..];
            }
            from = markup.len() - rest.len();
            if url.len() > start.len() && !out.contains(&url) {
                out.push(url);
            }
        }
    }
}

/// Premultiplied working-space RGBA floats as an `RHALF` image: no maths, only the half-float rounding (infinities and NaN are held to 0 as `rhalf` does).
pub fn raw_half(rgba: &[f32], w: u32, h: u32) -> Vec<u8> {
    let mut out = Vec::with_capacity(16 + rgba.len() * 2);
    out.extend_from_slice(blitz_dom::net::RHALF_MAGIC);
    out.extend_from_slice(&w.to_le_bytes());
    out.extend_from_slice(&h.to_le_bytes());
    for v in rgba {
        out.extend_from_slice(&half::f16::from_f32(if v.is_finite() { *v } else { 0.0 }).to_le_bytes());
    }
    out
}

/// A raw handoff frame already in the working space as an `RHALF` image, giving what `rhalf` gives with no conversion (premultiplied
/// in, alpha held to 0 … 1, ±inf to the largest half float, NaN to 0, light with alpha 0 kept) up to float rounding.
fn rhf_as_is(b: &[u8]) -> Result<Vec<u8>, String> {
    const HALF_MAX: f32 = 65504.0;
    if b.len() < 12 {
        return Err("a raw handoff frame is cut short".into());
    }
    let w = u32::from_le_bytes([b[4], b[5], b[6], b[7]]);
    let h = u32::from_le_bytes([b[8], b[9], b[10], b[11]]);
    let n = (w as usize) * (h as usize);
    let src = b.get(12..12 + n * 8).ok_or_else(|| format!("a raw handoff frame of {w}×{h} is cut short ({} bytes)", b.len()))?;
    let mut out = Vec::with_capacity(16 + n * 8);
    out.extend_from_slice(blitz_dom::net::RHALF_MAGIC);
    out.extend_from_slice(&w.to_le_bytes());
    out.extend_from_slice(&h.to_le_bytes());
    let mut px = vec![0u8; n * 8];
    crate::pixels::bands(n, |range, dst: &mut [u8]| {
        for (i, o) in range.zip(dst.chunks_exact_mut(8)) {
            let s = &src[i * 8..i * 8 + 8];
            let v = |k: usize| half::f16::from_le_bytes([s[k * 2], s[k * 2 + 1]]).to_f32();
            let (rgb, a0) = ([v(0), v(1), v(2)], v(3));
            // Opaque and finite (most pixels): the bytes as they are.
            if a0 == 1.0 && rgb.iter().all(|x| x.is_finite()) {
                o.copy_from_slice(s);
                continue;
            }
            let a = a0.clamp(0.0, 1.0);
            let emit = a <= 0.0 && rgb.iter().any(|&x| x != 0.0 && x.is_finite());
            let k = if a > 0.0 { 1.0 / a } else { 1.0 };
            let c = if a <= 0.0 && !emit { [0.0; 3] } else { rgb.map(|x| (x * k).clamp(-HALF_MAX, HALF_MAX)) };
            let m = if emit { 1.0 } else { a };
            for (j, x) in [c[0] * m, c[1] * m, c[2] * m, a].into_iter().enumerate() {
                o[j * 2..j * 2 + 2].copy_from_slice(&half::f16::from_f32(if x.is_finite() { x } else { 0.0 }).to_le_bytes());
            }
        }
    }, &mut px, 8);
    out.extend_from_slice(&px);
    Ok(out)
}

/// The grade + view table for a pipeline and grade file, made once per process (color.rs SceneLut).
fn scene_lut(pipeline: &rostrum_color::pipeline::Pipeline, grade_file: Option<String>, grade: Option<Arc<rostrum_color::grade::Grade>>) -> Arc<crate::color::SceneLut> {
    static LUTS: std::sync::OnceLock<Mutex<std::collections::HashMap<String, Arc<crate::color::SceneLut>>>> = std::sync::OnceLock::new();
    let key = format!("{:p}|{:?}|{:?}|{}", pipeline.view, pipeline.working, pipeline.target, grade_file.unwrap_or_default());
    let map = LUTS.get_or_init(Default::default);
    if let Some(l) = map.lock().unwrap().get(&key) {
        return l.clone();
    }
    let p = *pipeline;
    let lut = Arc::new(crate::color::SceneLut::build(move |lin| p.scene_in(grade.as_ref().map_or(lin, |g| g.apply(lin)))));
    let mut m = map.lock().unwrap();
    if m.len() > 16 {
        m.clear();
    }
    m.insert(key, lut.clone());
    lut
}

/// A grade spec file, parsed once per process (every frame of a scene names the same one; its LUT is read once).
fn scene_grade(file: &str) -> Result<Arc<rostrum_color::grade::Grade>, String> {
    static GRADES: std::sync::OnceLock<Mutex<std::collections::HashMap<String, Arc<rostrum_color::grade::Grade>>>> = std::sync::OnceLock::new();
    let map = GRADES.get_or_init(Default::default);
    if let Some(g) = map.lock().unwrap().get(file) {
        return Ok(g.clone());
    }
    let spec = std::fs::read_to_string(file).map_err(|e| format!("{file}: {e}"))?;
    let g = Arc::new(rostrum_color::grade::Grade::from_spec(&serde_json::from_str(&spec).map_err(|e| format!("{file}: {e}"))?)?);
    map.lock().unwrap().insert(file.to_string(), g.clone());
    Ok(g)
}

/// "#rrggbb" (or "#rgb") as display code values 0 … 1.
fn hex_colour(s: &str) -> Result<[f32; 3], String> {
    let h = s.strip_prefix('#').unwrap_or(s);
    let h: String = if h.len() == 3 { h.chars().flat_map(|c| [c, c]).collect() } else { h.to_string() };
    let byte = |i: usize| h.get(i..i + 2).and_then(|x| u8::from_str_radix(x, 16).ok()).map(|b| b as f32 / 255.0);
    match (h.len(), byte(0), byte(2), byte(4)) {
        (6, Some(r), Some(g), Some(b)) => Ok([r, g, b]),
        _ => Err(format!("bg={s:?} is not a colour (#rrggbb)")),
    }
}

/// A raw handoff frame: `RHF1`, u32 LE width and height, then RGBA half floats LE (rostrum-3d write_raw_half).
fn raw_handoff(b: &[u8]) -> bool {
    b.starts_with(b"RHF1")
}

/// A raw handoff frame's size and its RGBA as floats.
pub fn read_raw_half(b: &[u8]) -> Result<(u32, u32, Vec<f32>), String> {
    if b.len() < 12 {
        return Err("a raw handoff frame is cut short".into());
    }
    let w = u32::from_le_bytes([b[4], b[5], b[6], b[7]]);
    let h = u32::from_le_bytes([b[8], b[9], b[10], b[11]]);
    let n = (w as usize) * (h as usize) * 4;
    if b.len() < 12 + n * 2 {
        return Err(format!("a raw handoff frame of {w}×{h} is cut short ({} bytes)", b.len()));
    }
    let rgba = b[12..12 + n * 2].chunks_exact(2).map(|c| half::f16::from_le_bytes([c[0], c[1]]).to_f32()).collect();
    Ok((w, h, rgba))
}

/// An OpenEXR file (its magic number).
fn exr(b: &[u8]) -> bool {
    b.starts_with(&[0x76, 0x2f, 0x31, 0x01])
}

/// A PNG with 16 bits a channel (its IHDR bit depth), the depth ingest decodes video to.
fn deep_png(b: &[u8]) -> bool {
    b.len() > 24 && b.starts_with(&[0x89, b'P', b'N', b'G']) && b[24] == 16
}

fn short(url: &str) -> String {
    if url.starts_with("data:") {
        format!("{}…", &url[..url.len().min(40)])
    } else {
        url.to_string()
    }
}

fn load(url: &blitz_traits::net::Url) -> Result<Vec<u8>, String> {
    match url.scheme() {
        "data" => {
            let s = url.as_str();
            let (meta, data) = s["data:".len()..].split_once(',').ok_or("malformed data: URL")?;
            Ok(if meta.ends_with(";base64") { base64(data) } else { percent(data) })
        }
        "file" => {
            let path = url.to_file_path().map_err(|_| "not a local file path".to_string())?;
            std::fs::read(&path).map_err(|e| format!("{e} ({})", path.display()))
        }
        "http" | "https" if url.path() == "/__local_asset" => {
            let p = url.query_pairs().find(|(k, _)| k == "p").map(|(_, v)| v.into_owned()).ok_or("local asset URL without ?p=")?;
            std::fs::read(&p).map_err(|e| format!("{e} ({p})"))
        }
        _ => Err("only data:, file: and /__local_asset URLs are loaded (the stage page has no network)".into()),
    }
}

fn base64(s: &str) -> Vec<u8> {
    let val = |c: u8| match c {
        b'A'..=b'Z' => Some(c - b'A'),
        b'a'..=b'z' => Some(c - b'a' + 26),
        b'0'..=b'9' => Some(c - b'0' + 52),
        b'+' | b'-' => Some(62),
        b'/' | b'_' => Some(63),
        _ => None,
    };
    let digits: Vec<u8> = s.bytes().filter_map(val).collect();
    digits
        .chunks(4)
        .flat_map(|c| {
            let n = c.iter().enumerate().fold(0u32, |n, (i, d)| n | (*d as u32) << (18 - 6 * i));
            [(n >> 16) as u8, (n >> 8) as u8, n as u8].into_iter().take(c.len().saturating_sub(1))
        })
        .collect()
}

fn percent(s: &str) -> Vec<u8> {
    let b = s.as_bytes();
    let mut out = vec![];
    let mut i = 0;
    while i < b.len() {
        if b[i] == b'%' && i + 2 < b.len() {
            if let Ok(v) = u8::from_str_radix(&s[i + 1..i + 3], 16) {
                out.push(v);
                i += 3;
                continue;
            }
        }
        out.push(b[i]);
        i += 1;
    }
    out
}

#[cfg(test)]
mod tests {
    #[test]
    fn picture_urls_finds_every_local_picture_once() {
        let markup = r##"<img src="/__local_asset?p=C%3A%2Fa.png&amp;color=acescg"><div style="mask-image: url(&quot;/__local_asset?p=C%3A%2Fm.png&quot;)"></div>
<svg><feImage href="file:///C:/b.exr" result="x"/><feImage xlink:href="#ref"/><feshader images="depth /__local_asset?p=C%3A%2Fz.rhf&amp;color=acescg;normal /__local_asset?p=C%3A%2Fn.rhf"/>
<img src='data:image/png;base64,AAAA'><img src="/__local_asset?p=C%3A%2Fa.png&amp;color=acescg"></svg>"##;
        let mut urls = vec![];
        super::picture_urls(markup, &mut urls);
        assert_eq!(
            urls,
            [
                "/__local_asset?p=C%3A%2Fa.png&color=acescg",
                "/__local_asset?p=C%3A%2Fm.png",
                "/__local_asset?p=C%3A%2Fz.rhf&color=acescg",
                "/__local_asset?p=C%3A%2Fn.rhf",
                "file:///C:/b.exr",
                "data:image/png;base64,AAAA",
            ]
        );
    }
}

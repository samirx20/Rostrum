//! `rostrum2d-render serve`: the Motion renderer as a long-lived process the host drives (the Python layer,
//! proofs/2d-renderer/driver/rostrum2d.py today). One JSON request per stdin line, one JSON reply per stdout line:
//!
//! - `{"open": {"width", "height", "html", "cpu"?, "depth"?, "color"?}}` — the page shell (styles, fonts, an empty
//!   `<div id="rostrum-stage">`); paints on the GPU unless `cpu` is true; always into half-float surfaces in the
//!   working colour space `color` names (color.rs); `depth: 16` makes `rgba` frames 16-bit (rgba64le), else 8-bit
//!   with dither. Replies `{"ok": true, "gpu": bool}`.
//! - `{"frame": {"stage": "<markup>", "index"?: n, "samples"?: ["<markup>", …], "image"?: path, "rgba"?: true, "boxes"?: true}}` —
//!   (`index`: the document frame number, the output dither's seed, so a preview frame equals the exported one)
//!   the stage's content for this frame, applied as edits to the kept page. `samples` (motion blur): the stage at
//!   each shutter sub-frame, each painted and the pictures averaged on the GPU (painter.rs `accumulate`); the
//!   frame's `stage` is then laid out only when `boxes` asks. With `held: true` the `stage` is painted after the
//!   sum with the sum drawn in place of the children of its `data-shutter-held` element (an <Adjust> whose look
//!   then runs once, after the shutter; painter.rs). Writes a PNG or JPEG (by extension, 8-bit) to
//!   `image`, or with `rgba` replies `{"ok": true, "bytes": n, …}` followed by n bytes of straight-alpha RGBA on
//!   stdout. `boxes` adds each layer's laid-out box to the reply (boxes.rs). With `encode: true` the pixels go
//!   to the open's encoder instead and the reply is `{"ok": true, …}`.
//! - `{"page": {"html"}}` — another page shell on the open session (a live preview's next prepared document):
//!   the document is replaced, the painter (GPU context and surfaces), colour, encoder and scratch parser kept;
//!   replies `{"ok": true, "timing": {"pageMs"}}`. An older renderer answers "unknown request" (the host then opens).
//! - `open.encode: {"program", "args"}` — an encoder (ffmpeg reading raw frames on stdin) the renderer starts
//!   and writes `encode` frames to itself (sink.rs), so pixels never pass through the host.
//! - `{"frame": {…, "sample": path}}` — also writes the frame's ACEScg light to `path` (scopes.rs `write_sample`); with no `image` / `rgba` the reply is `{"ok": true, "sample": path}`.
//! - `{"match": {"mode": "match" | "auto", "shot": sample, …}}` — a shot match / auto balance through the session's view (scopes.rs `run_match`): `{"ok": true, "fit": {…}}`.
//! - A frame's pictures (every `/__local_asset?p=`, `file:` and `data:` URL its `stage` and `samples` name) that the asset cache
//!   (asset_cache.rs) does not keep yet are decoded on up to 4 threads before it is laid out, so layout and paint only hit the
//!   cache; the reply's `timing.decodeMs` is that time, `timing.pictures` how many it names and `timing.decoded` how many of
//!   those were not kept yet (a `warm` that came too late, or missed). `timing.gpuMs`: of `readMs`, the wait for the GPU to
//!   finish drawing the frame (the rest is the copy).
//! - `{"warm": {"urls": ["…", …]}}` — pictures the next frames will name (as the stage markup names them), decoded into the asset
//!   cache ahead on 2 background threads, which wait while a frame decodes its own; replies `{"ok": true, "queued": n}` at once.
//!   A picture kept, queued or being decoded is skipped; a failure is dropped (the frame that needs it reports it); past 64
//!   waiting, the oldest go. One whose file is not written yet (a 3D pass named as its render starts) or was written in the
//!   last 20 ms is looked for again every 5 ms for 3 s.
//! - `{"finish": {}}` — closes the encoder's input and waits for it: `{"ok": true, "code": 0}`, or an error
//!   with what it said.
//!
//! Errors reply `{"error": "…"}` (an asset that failed to load names its URL); the process keeps serving.

use std::collections::VecDeque;
use std::io::{BufRead, Write};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Condvar, Mutex, OnceLock};
use std::time::Instant;

use blitz_dom::DocumentConfig;
use blitz_html::HtmlDocument;
use blitz_traits::node_id::NodeId;
use blitz_traits::shell::{ColorScheme, Viewport};
use serde_json::{json, Value};

use crate::assets::{Assets, BASE_URL};
use crate::color::Spec;
use crate::keep;
use crate::painter::Painter;
use crate::sink::{Pixels, Sink};

const STAGE: &str = "#rostrum-stage";

struct Session {
    doc: HtmlDocument,
    stage: NodeId,
    assets: Assets,
    painter: Painter,
    width: u32,
    height: u32,
    /// rgba frames are 16-bit.
    deep: bool,
    /// The working space, view and output (color.rs).
    color: Spec,
    /// Where `encode` frames go (open.encode).
    sink: Option<Sink>,
    /// Each frame's stage markup is parsed here (no styles, no loads) and walked beside the kept page.
    scratch: keep::Scratch,
}

/// `warm`: the GL context made as the process started (taken by the first GPU open).
fn open(req: &Value, warm: &mut Option<Result<crate::painter::Gl, String>>) -> Result<(Session, Value), String> {
    let width = req["width"].as_u64().ok_or("open needs width")? as u32;
    let height = req["height"].as_u64().ok_or("open needs height")? as u32;
    let html = req["html"].as_str().ok_or("open needs html")?;
    let color = Spec::parse(&req["color"])?;
    let assets = Assets::new(color);
    // An feImage with `&color=` (a comp's still image) decodes through the same colour input as an `<img>`.
    let loader = assets.clone();
    anyrender::filters::images::set_loader(std::sync::Arc::new(move |url: &str| loader.decode(url)));
    let config = page_config(width, height, &assets);
    let t0 = Instant::now();
    let (doc, stage) = shell(html, config, &assets)?;
    let deep = match req["depth"].as_u64() {
        None | Some(8) => false,
        Some(16) => true,
        Some(d) => return Err(format!("depth is 8 or 16; got {d}")),
    };
    let page_ms = t0.elapsed().as_secs_f64() * 1000.0;
    let t1 = Instant::now();
    let painter = match (req["cpu"].as_bool() == Some(true), warm.take()) {
        (true, _) => Painter::cpu(width, height, color.surface_space())?,
        (false, Some(gl)) => Painter::gpu_on(gl?, width, height, color.surface_space())?,
        (false, None) => Painter::gpu(width, height, color.surface_space())?,
    };
    let painter_ms = t1.elapsed().as_secs_f64() * 1000.0;
    let gpu = painter.is_gpu();
    let adapter = painter.gpu_name().unwrap_or("").to_string();
    let sink = match req.get("encode") {
        Some(e) => {
            let program = e["program"].as_str().ok_or("encode needs program")?;
            let args: Vec<String> = e["args"].as_array().ok_or("encode needs args")?.iter().filter_map(|a| a.as_str().map(String::from)).collect();
            Some(Sink::start(program, &args)?)
        }
        None => None,
    };
    let scratch = keep::Scratch::new(|| DocumentConfig { base_url: Some(BASE_URL.into()), ..Default::default() });
    Ok((Session { doc, stage, assets, painter, width, height, deep, color, sink, scratch }, json!({ "ok": true, "gpu": gpu, "adapter": adapter, "depth": if deep { 16 } else { 8 }, "timing": { "pageMs": page_ms, "painterMs": painter_ms } })))
}

/// The page document's settings at a frame size, its loads through `assets`.
fn page_config(width: u32, height: u32, assets: &Assets) -> DocumentConfig {
    DocumentConfig {
        viewport: Some(Viewport::new(width, height, 1.0, ColorScheme::Light)),
        base_url: Some(BASE_URL.into()),
        net_provider: Some(std::sync::Arc::new(assets.clone())),
        // Incremental layout: only what an edit damaged is laid out again. A frame must still be a function of
        // its markup alone (AGENTS.md rule 5): a measure cache hit used to lose an inline-block's baseline, so
        // after opacity edits on split letters their line grew by the descent (41 px off a fresh frame);
        // vendor/blitz-dom keeps measured baselines now (PATCHES.md round 9; incremental_tests.rs checks
        // edited pages against fresh ones).
        incremental: Some(true),
        ..Default::default()
    }
}

/// A page shell parsed and resolved, and its stage element.
fn shell(html: &str, config: DocumentConfig, assets: &Assets) -> Result<(HtmlDocument, NodeId), String> {
    let mut doc = HtmlDocument::from_html(html, config);
    doc.handle_messages();
    doc.resolve(0.0);
    failures(assets)?;
    let stage = doc.query_selector(STAGE).map_err(|_| "bad selector")?.ok_or("the page shell has no <div id=\"rostrum-stage\">")?;
    Ok((doc, stage))
}

/// `page`: another page shell on the open session (a live preview's next prepared document): the document is
/// replaced; the painter (its GPU context and surfaces), the colour spec, the encoder and the scratch parser stay.
fn page(s: &mut Session, req: &Value) -> Result<Value, String> {
    let html = req["html"].as_str().ok_or("page needs html")?;
    let t0 = Instant::now();
    let (doc, stage) = shell(html, page_config(s.width, s.height, &s.assets), &s.assets)?;
    s.doc = doc;
    s.stage = stage;
    Ok(json!({ "ok": true, "timing": { "pageMs": t0.elapsed().as_secs_f64() * 1000.0 } }))
}

fn failures(assets: &Assets) -> Result<(), String> {
    let mut f = assets.failures.lock().unwrap();
    if f.is_empty() {
        return Ok(());
    }
    let list = std::mem::take(&mut *f);
    Err(format!("{} asset(s) failed to load: {}", list.len(), list.join("; ")))
}

/// Applies one stage's markup to the kept page as edits and lays it out: (diff ms, layout ms, edit count).
fn apply(s: &mut Session, markup: &str) -> Result<(f64, f64, usize), String> {
    let t0 = Instant::now();
    // The new stage, parsed on its own (no styles, no loads), walked beside the kept one.
    let next_stage = s.scratch.parse(markup).ok_or("stage markup lost its container")?;
    let edits = keep::diff_from(&s.doc, &s.scratch.0, s.stage, next_stage);
    let diff_ms = t0.elapsed().as_secs_f64() * 1000.0;
    let t1 = Instant::now();
    keep::apply(&mut s.doc, &s.scratch.0, &edits);
    s.doc.handle_messages();
    s.doc.resolve(0.0);
    failures(&s.assets)?;
    Ok((diff_ms, t1.elapsed().as_secs_f64() * 1000.0, edits.count()))
}

/// Paints the kept page (`held`: over the motion-blur sum, painter.rs); an effect shader that failed fails the
/// frame (AGENTS.md rule 6), naming what failed.
fn paint(s: &mut Session, held: bool) -> Result<(), String> {
    let (w, h) = (s.width, s.height);
    let doc = &mut s.doc;
    s.painter.paint(held, |scene| blitz_paint::paint_scene(scene, doc, 1.0, w, h, 0, 0))?;
    let shader_errors = anyrender::filters::shader_errors::take();
    if shader_errors.is_empty() { Ok(()) } else { Err(shader_errors.join("; ")) }
}

/// Threads a frame decodes its own pictures on (the laptop's 8 logical cores are shared with the 3D engine).
const FRAME_DECODE_THREADS: usize = 4;
/// Threads `warm` decodes the next frames' pictures on.
const AHEAD_THREADS: usize = 2;
/// The most pictures `warm` keeps waiting (the oldest go: the playhead has passed them).
const AHEAD_MAX: usize = 64;

/// A frame is decoding its own pictures: the decodes ahead wait.
static FRAME_DECODING: AtomicBool = AtomicBool::new(false);

/// How long a picture `warm` names whose file is not written yet is looked for again (a 3D pass the host names as it starts
/// that frame's render: it appears a few frames' time later).
const AHEAD_WAIT: std::time::Duration = std::time::Duration::from_secs(3);
/// How often a picture not written yet is looked for again.
const AHEAD_POLL: std::time::Duration = std::time::Duration::from_millis(5);

/// One picture `warm` queued: the session's loader (its colour), the URL, until when it is looked for if its file is not there
/// yet, and when it is due (now, or AHEAD_POLL after a look that did not find it).
type Ahead = (Assets, String, Instant, Instant);

/// `warm`'s queue and its threads, started at the first `warm`. A picture whose file is not written yet (or was written this
/// instant) goes to the back, due again AHEAD_POLL later, until AHEAD_WAIT has passed; the pictures due go first.
fn ahead() -> &'static (Mutex<VecDeque<Ahead>>, Condvar) {
    static A: OnceLock<(Mutex<VecDeque<Ahead>>, Condvar)> = OnceLock::new();
    A.get_or_init(|| {
        for _ in 0..AHEAD_THREADS {
            std::thread::spawn(|| loop {
                let (assets, url, until, _) = {
                    let (q, ready) = ahead();
                    let mut q = q.lock().unwrap_or_else(|e| e.into_inner());
                    loop {
                        let now = Instant::now();
                        if let Some(job) = q.iter().position(|j| j.3 <= now).and_then(|i| q.remove(i)) {
                            break job;
                        }
                        q = if q.is_empty() { ready.wait(q).unwrap_or_else(|e| e.into_inner()) } else { ready.wait_timeout(q, AHEAD_POLL).unwrap_or_else(|e| e.into_inner()).0 };
                    }
                };
                while FRAME_DECODING.load(Ordering::Relaxed) {
                    std::thread::sleep(std::time::Duration::from_millis(2));
                }
                if assets.warm(&url) == crate::asset_cache::Warmed::NotYet && Instant::now() < until {
                    let mut q = ahead().0.lock().unwrap_or_else(|e| e.into_inner());
                    // Not twice when `warm` named it anew meanwhile.
                    if !q.iter().any(|j| j.1 == url) {
                        q.push_back((assets, url, until, Instant::now() + AHEAD_POLL));
                    }
                }
            });
        }
        (Mutex::new(VecDeque::new()), Condvar::new())
    })
}

/// `warm`: the next frames' pictures queued for decoding ahead; answers at once.
fn warm_ahead(s: &Session, req: &Value) -> Result<Value, String> {
    let urls = req["urls"].as_array().ok_or("warm needs urls")?;
    let (q, ready) = ahead();
    let mut q = q.lock().unwrap_or_else(|e| e.into_inner());
    let mut queued = 0;
    let now = Instant::now();
    for u in urls.iter().filter_map(Value::as_str).map(|u| u.replace("&amp;", "&")) {
        if !q.iter().any(|j| j.1 == u) {
            q.push_back((s.assets.clone(), u, now + AHEAD_WAIT, now));
            queued += 1;
        }
    }
    while q.len() > AHEAD_MAX {
        q.pop_front();
    }
    ready.notify_all();
    Ok(json!({ "ok": true, "queued": queued }))
}

fn frame(s: &mut Session, req: &Value, out: &mut impl Write) -> Result<Option<Vec<u8>>, String> {
    let markup = req["stage"].as_str().ok_or("frame needs stage")?;
    let samples: Vec<&str> = req["samples"].as_array().map(|a| a.iter().filter_map(Value::as_str).collect()).unwrap_or_default();
    // The frame's pictures not kept yet, decoded side by side now, so layout and paint (which load one after another) only hit the cache.
    let t_decode = Instant::now();
    let mut urls = vec![];
    for mk in std::iter::once(markup).chain(samples.iter().copied()) {
        crate::assets::picture_urls(mk, &mut urls);
    }
    // How many were kept already (decoded ahead by `warm`, or by an earlier frame): `timing.pictures` / `timing.decoded`.
    let decoded = urls.iter().filter(|u| !s.assets.is_kept(u)).count();
    FRAME_DECODING.store(true, Ordering::Relaxed);
    s.assets.warm_all(&urls, FRAME_DECODE_THREADS);
    FRAME_DECODING.store(false, Ordering::Relaxed);
    let decode_ms = t_decode.elapsed().as_secs_f64() * 1000.0;
    let boxes_wanted = req["boxes"].as_bool() == Some(true);
    let held = !samples.is_empty() && req["held"].as_bool() == Some(true);
    let index = req["index"].as_u64().unwrap_or(0) as u32;
    let (mut diff_ms, mut layout_ms, mut edits, mut paint_ms, mut record_ms) = (0.0, 0.0, 0, 0.0, 0.0);
    let (mut taps, mut tap_read_ms, mut tap_write_ms) = (0, 0.0, 0.0);
    let mut timed = |s: &mut Session, mk: &str, draw: bool, held: bool| -> Result<(), String> {
        let (d, l, e) = apply(s, mk)?;
        (diff_ms, layout_ms, edits) = (diff_ms + d, layout_ms + l, edits + e);
        if draw {
            let t = Instant::now();
            paint(s, held)?;
            paint_ms += t.elapsed().as_secs_f64() * 1000.0;
            record_ms += s.painter.last_draw_ms;
            (taps, tap_read_ms, tap_write_ms) = (taps + s.painter.last_taps, tap_read_ms + s.painter.last_tap_read_ms, tap_write_ms + s.painter.last_tap_write_ms);
        }
        Ok(())
    };
    if samples.is_empty() {
        timed(s, markup, true, false)?;
    } else {
        // Motion blur: every sub-frame painted and summed with an equal share (then, held, the stage over the sum).
        let k = 1.0 / samples.len() as f32;
        for (i, mk) in samples.iter().enumerate() {
            timed(s, mk, true, false)?;
            s.painter.accumulate(i == 0, k)?;
        }
        if held || boxes_wanted {
            timed(s, markup, held, held)?;
        }
    }
    let t2 = Instant::now();
    let (w, h) = (s.width, s.height);
    if req["encode"].as_bool() == Some(true) {
        // To the encoder: the frame's readback is started and collected while the next frame is made (one
        // frame in flight; readback.rs), or read now where the GPU cannot.
        s.sink.as_ref().ok_or("encode frames need an encoder (open.encode)")?;
        let mut wait_ms = 0.0;
        if s.painter.start_read(index) {
            paint_ms += t2.elapsed().as_secs_f64() * 1000.0;
            while s.painter.reads_in_flight() > 1 {
                wait_ms += collect(s)?;
            }
        } else {
            let raw = s.painter.read();
            paint_ms += t2.elapsed().as_secs_f64() * 1000.0;
            let t3 = Instant::now();
            let px = Pixels { raw, spec: s.color, width: w, deep: s.deep, index };
            s.sink.as_mut().unwrap().push(px)?;
            wait_ms += t3.elapsed().as_secs_f64() * 1000.0;
        }
        let boxes = if boxes_wanted { crate::boxes::boxes(&s.doc, w, h) } else { Value::Null };
        // The comp-cache buffers the frame tapped are on disk before it is answered (the host looks them up next).
        s.painter.taps_written()?;
        tap_write_ms += s.painter.last_tap_write_ms;
        let timing = json!({ "diffMs": diff_ms, "layoutMs": layout_ms, "paintMs": paint_ms, "recordMs": record_ms, "readMs": s.painter.last_read_ms, "convertMs": s.painter.last_convert_ms, "edits": edits, "samples": samples.len().max(1), "encodeWaitMs": wait_ms, "decodeMs": decode_ms, "pictures": urls.len(), "decoded": decoded, "gpuMs": s.painter.last_gpu_ms, "taps": taps, "tapReadMs": tap_read_ms, "tapWriteMs": tap_write_ms });
        reply(out, &json!({ "ok": true, "timing": timing, "boxes": boxes }));
        return Ok(None);
    }
    let image = req["image"].as_str();
    // A playing frame (the app server asks for a .jpg only while playing) goes through the output step's checked 3D table:
    // on the GPU when it can (painter.rs `read_output8`: 8-bit read back, no step on the CPU), else on the CPU below.
    let fast = image.is_some_and(|p| { let p = p.to_ascii_lowercase(); p.ends_with(".jpg") || p.ends_with(".jpeg") });
    let gpu_lut = if fast && req.get("scopes").is_none() && req["sample"].is_null() && crate::color::channel_table(&s.color).is_none() { crate::color::output_lut(&s.color) } else { None };
    if let Some(pixels) = gpu_lut.and_then(|l| s.painter.read_output8(&l)) {
        let pixels = pixels?;
        s.painter.last_convert_ms = 0.0;
        s.painter.taps_written()?;
        tap_write_ms += s.painter.last_tap_write_ms;
        paint_ms += t2.elapsed().as_secs_f64() * 1000.0;
        let mut timing = json!({ "diffMs": diff_ms, "layoutMs": layout_ms, "paintMs": paint_ms, "recordMs": record_ms, "readMs": s.painter.last_read_ms, "convertMs": 0.0, "edits": edits, "samples": samples.len().max(1), "decodeMs": decode_ms, "pictures": urls.len(), "decoded": decoded, "gpuMs": s.painter.last_gpu_ms, "taps": taps, "tapReadMs": tap_read_ms, "tapWriteMs": tap_write_ms, "gpuOutput": true });
        let boxes = if boxes_wanted { crate::boxes::boxes(&s.doc, w, h) } else { Value::Null };
        let t4 = Instant::now();
        let path = image.unwrap();
        jpeg_encoder::Encoder::new_file(path, 75).and_then(|e| e.encode(&pixels, w as u16, h as u16, jpeg_encoder::ColorType::Rgba)).map_err(|e| format!("writing {path}: {e}"))?;
        timing["writeMs"] = json!(t4.elapsed().as_secs_f64() * 1000.0);
        reply(out, &json!({ "ok": true, "timing": timing, "boxes": boxes, "scopes": Value::Null }));
        return Ok(None);
    }
    let raw = s.painter.read();
    // The frame's taps are written while it is read back and converted; on disk before it is answered.
    let taps_done = |s: &mut Session, ms: &mut f64| -> Result<(), String> {
        s.painter.taps_written()?;
        *ms += s.painter.last_tap_write_ms;
        Ok(())
    };
    // Scopes: measured from the F16 frame as stored (before the output step; scopes.rs).
    let scopes_out = match req.get("scopes") {
        Some(sc) => {
            let domain = crate::scopes::domain_of(sc, crate::scopes::is_hdr(&s.color.pipeline))?;
            let frame = crate::scopes::from_f16(&s.color.pipeline, &raw, w as usize, h as usize, domain);
            crate::scopes::run(&frame, sc)?
        }
        None => Value::Null,
    };
    // Sample (G7): the frame's ACEScg light, for `match` (scopes.rs).
    let sample_out = match req["sample"].as_str() {
        Some(path) => {
            let frame = crate::scopes::from_f16(&s.color.pipeline, &raw, w as usize, h as usize, rostrum_color::scope::Domain::AcesCg);
            crate::scopes::write_sample(&frame, path)?;
            json!(path)
        }
        None => Value::Null,
    };
    if image.is_none() && req["rgba"].as_bool() != Some(true) && (!scopes_out.is_null() || !sample_out.is_null()) {
        taps_done(s, &mut tap_write_ms)?;
        reply(out, &json!({ "ok": true, "scopes": scopes_out, "sample": sample_out }));
        return Ok(None);
    }
    let t3 = Instant::now();
    let mut pixels = vec![];
    crate::color::output(&s.color, &raw, w, s.deep && image.is_none(), fast, index, &mut pixels);
    s.painter.last_convert_ms = t3.elapsed().as_secs_f64() * 1000.0;
    taps_done(s, &mut tap_write_ms)?;
    paint_ms += t2.elapsed().as_secs_f64() * 1000.0;
    let mut timing = json!({ "diffMs": diff_ms, "layoutMs": layout_ms, "paintMs": paint_ms, "recordMs": record_ms, "readMs": s.painter.last_read_ms, "convertMs": s.painter.last_convert_ms, "edits": edits, "samples": samples.len().max(1), "decodeMs": decode_ms, "pictures": urls.len(), "decoded": decoded, "gpuMs": s.painter.last_gpu_ms, "taps": taps, "tapReadMs": tap_read_ms, "tapWriteMs": tap_write_ms });
    let boxes = if boxes_wanted { crate::boxes::boxes(&s.doc, w, h) } else { Value::Null };
    if let Some(path) = image {
        let t4 = Instant::now();
        let img = image::RgbaImage::from_raw(w, h, pixels).ok_or("frame size mismatch")?;
        let jpeg = path.ends_with(".jpg") || path.ends_with(".jpeg");
        // PNGs with fast compression (fdeflate): the same pixels, written in a fraction of the time (live frames are written per paint).
        // JPEGs (playing frames) by jpeg-encoder (SIMD; the RGBA read as it is, alpha dropped): faster than image's own encoder, same quality (75).
        let saved = if jpeg {
            jpeg_encoder::Encoder::new_file(path, 75)
                .and_then(|e| e.encode(img.as_raw(), w as u16, h as u16, jpeg_encoder::ColorType::Rgba))
                .map_err(|e| image::ImageError::IoError(std::io::Error::other(e.to_string())))
        } else {
            std::fs::File::create(path).map_err(image::ImageError::IoError).and_then(|f| {
                let enc = image::codecs::png::PngEncoder::new_with_quality(std::io::BufWriter::new(f), image::codecs::png::CompressionType::Fast, image::codecs::png::FilterType::Adaptive);
                img.write_with_encoder(enc)
            })
        };
        saved.map_err(|e| format!("writing {path}: {e}"))?;
        // The picture's encode and write (after `paintMs`; the host waits for it all the same).
        timing["writeMs"] = json!(t4.elapsed().as_secs_f64() * 1000.0);
        reply(out, &json!({ "ok": true, "timing": timing, "boxes": boxes, "scopes": scopes_out }));
        return Ok(None);
    }
    if req["rgba"].as_bool() == Some(true) {
        reply(out, &json!({ "ok": true, "bytes": pixels.len(), "timing": timing, "boxes": boxes, "scopes": scopes_out }));
        return Ok(Some(pixels));
    }
    Err("frame needs image (a .png / .jpg path) or rgba: true".into())
}

/// The oldest frame in flight, read back and queued for the encoder (its stored bytes are converted on the
/// writer thread). Returns the ms spent (waiting for the GPU or the encoder).
fn collect(s: &mut Session) -> Result<f64, String> {
    let t = Instant::now();
    let (raw, index) = s.painter.finish_read()?;
    let px = Pixels { raw, spec: s.color, width: s.width, deep: s.deep, index };
    s.sink.as_mut().ok_or("no encoder")?.push(px)?;
    Ok(t.elapsed().as_secs_f64() * 1000.0)
}

/// Every frame in flight to the encoder, then the encoder closed and waited for.
fn finish(s: &mut Session) -> Result<i32, String> {
    while s.painter.reads_in_flight() > 0 {
        collect(s)?;
    }
    s.sink.as_mut().ok_or("finish without an encoder (open.encode)")?.finish()
}

fn reply(out: &mut impl Write, v: &Value) {
    writeln!(out, "{v}").unwrap();
}

pub fn run() {
    let stdin = std::io::stdin();
    let stdout = std::io::stdout();
    let mut out = stdout.lock();
    let mut session: Option<Session> = None;
    // The GL context, made now: the driver takes ~0.2 s to load, overlapping the host's preparation of the
    // render (the host starts this process before it needs it).
    let mut warm = Some(crate::painter::gl_context());
    for line in stdin.lock().lines() {
        let Ok(line) = line else { break };
        if line.trim().is_empty() {
            continue;
        }
        let req: Value = match serde_json::from_str(&line) {
            Ok(v) => v,
            Err(e) => {
                reply(&mut out, &json!({ "error": format!("bad request: {e}") }));
                out.flush().unwrap();
                continue;
            }
        };
        if let Some(o) = req.get("open") {
            match open(o, &mut warm) {
                Ok((s, r)) => {
                    session = Some(s);
                    reply(&mut out, &r);
                }
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(f) = req.get("frame") {
            match session.as_mut() {
                None => reply(&mut out, &json!({ "error": "frame before open" })),
                Some(s) => match frame(s, f, &mut out) {
                    Ok(Some(pixels)) => out.write_all(&pixels).unwrap(),
                    Ok(None) => {}
                    Err(e) => reply(&mut out, &json!({ "error": e })),
                },
            }
        } else if let Some(p) = req.get("page") {
            match session.as_mut().ok_or_else(|| "page before open".to_string()).and_then(|s| page(s, p)) {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(m) = req.get("match") {
            match session.as_ref().ok_or_else(|| "match before open".to_string()).and_then(|s| crate::scopes::run_match(&s.color.pipeline, m)) {
                Ok(fit) => reply(&mut out, &json!({ "ok": true, "fit": fit })),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(w) = req.get("warm") {
            match session.as_ref().ok_or_else(|| "warm before open".to_string()).and_then(|s| warm_ahead(s, w)) {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if req.get("finish").is_some() {
            match session.as_mut().ok_or_else(|| "finish before open".to_string()).and_then(finish) {
                Ok(code) => reply(&mut out, &json!({ "ok": true, "code": code })),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if req.get("close").is_some() {
            break;
        } else {
            reply(&mut out, &json!({ "error": "unknown request (open, page, frame, warm, match, finish or close)" }));
        }
        out.flush().unwrap();
    }
}

//! `rostrum2d-render serve`: the Motion renderer as a long-lived process the host drives (the Python layer,
//! proofs/2d-renderer/driver/rostrum2d.py today). One JSON request per stdin line, one JSON reply per stdout line:
//!
//! - `{"open": {"width", "height", "html", "cpu"?, "depth"?, "color"?}}` — the page shell (styles, fonts, an empty
//!   `<div id="rostrum-stage">`); paints on the GPU unless `cpu` is true; always into half-float surfaces in the
//!   working colour space `color` names (color.rs); `depth: 16` makes `rgba` frames 16-bit (rgba64le), else 8-bit
//!   with dither. Replies `{"ok": true, "gpu": bool, "adapter", "fallback"}`: with no GL context (no working graphics
//!   driver, or `ROSTRUM2D_NO_GPU=1`) it paints on the CPU and `fallback` says so in plain words (else null).
//! - `{"frame": {"stage": "<markup>", "index"?: n, "samples"?: ["<markup>", …], "image"?: path, "rgba"?: true, "boxes"?: true}}` —
//!   (`index`: the document frame number, the output dither's seed, so a preview frame equals the exported one)
//!   the stage's content for this frame, applied as edits to the kept page. `samples` (motion blur): the stage at
//!   each shutter sub-frame, each painted and the pictures averaged on the GPU (painter.rs `accumulate`); the
//!   frame's `stage` is then laid out only when `boxes` asks. With `held: true` the `stage` is painted after the
//!   sum with the sum drawn in place of the children of its `data-shutter-held` element (an <Adjust> whose look
//!   then runs once, after the shutter; painter.rs). Writes a PNG or JPEG (by extension, 8-bit) to
//!   `image`, or with `rgba` replies `{"ok": true, "bytes": n, …}` followed by n bytes of straight-alpha RGBA on
//!   stdout; with `pixels` the same bytes go into shared memory instead and the reply's `shm` says where (handoff.rs,
//!   shm.rs; `screen`: the screen's form; `ahead`: the next frame drawn after the reply, serve_ahead.rs).
//!   `scale` (with `pixels` only: the live canvas while playing): 1, 0.5 or 0.25, the same laid-out page drawn at that
//!   size (painter.rs `set_view`); the reply's `width` / `height` and `shm` give the smaller size, `boxes` stay in comp px.
//!   Or `view: {x, y, w, h, scale}` (with `pixels` only: the zoomed-in canvas): the comp px crop x..x+w, y..y+h drawn at
//!   `scale` (up to 64; at most 8192 px a side), round(w·scale) × round(h·scale) px, through the same paint as any frame.
//!   `boxes` adds each layer's laid-out box to the reply (boxes.rs). With `encode: true` the pixels go
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
//! - `{"scene"}`, `{"change"}`, `{"frame": {"t"}}`, `{"export"}`, `{"edit"}`, `{"bones"}`, `{"outline"}`, `{"measure"}`, `{"layout"}` — the engine holds the scene description and evaluates every
//!   frame itself (ENGINE_CONTRACT.md; scene_serve.rs).
//!
//! Errors reply `{"error": "…"}` (an asset that failed to load names its URL); the process keeps serving.

use std::collections::{HashMap, VecDeque};
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

pub(crate) struct Session {
    pub(crate) doc: HtmlDocument,
    stage: NodeId,
    assets: Assets,
    /// A picture laid over the next frame once it is drawn (image, image px → device px, the device polygon it fills):
    /// the frame's export in the world picture (scene_world.rs). Before the painter: GPU images go before its context.
    pub(crate) over: Option<(skia_safe::Image, skia_safe::Matrix, skia_safe::Path)>,
    /// The stage's clip is lifted (`open_stage`).
    stage_open: bool,
    pub(crate) painter: Painter,
    pub(crate) width: u32,
    pub(crate) height: u32,
    /// rgba frames are 16-bit.
    pub(crate) deep: bool,
    /// The working space, view and output (color.rs).
    pub(crate) color: Spec,
    /// Where `encode` frames go (open.encode).
    pub(crate) sink: Option<Sink>,
    /// Each frame's stage markup is parsed here (no styles, no loads) and walked beside the kept page.
    scratch: keep::Scratch,
    /// The pieces the kept stage was staged from (restage.rs), and the next frame's when its caller has them.
    pub(crate) kept_pieces: crate::restage::Kept,
    pub(crate) next_pieces: Option<Vec<String>>,
    /// The next frame's motion-blur sub-frames cut the same way, one list per sub-frame (`samples` in order).
    pub(crate) sample_pieces: Vec<Vec<String>>,
    /// Grouped sub-frames (scene_serve.rs `stage_at`): each sample's group's middle sample; empty when not grouped.
    pub(crate) sample_bases: Vec<usize>,
    /// The live canvas's shared-memory frames (`pixels`), made on first use and remade at a new frame size.
    pub(crate) shm: Option<crate::shm::Shm>,
    /// A frame drawn with `defer` (serve_ahead.rs): its output started, handed over when it is asked for.
    pub(crate) deferred: Option<crate::handoff::Started>,
    /// What paints (`with_painting`): every open and scene reply says it.
    pub(crate) painting: Value,
}

/// Opens a session in place of the running one (`session`), on the running one's GL context (painter.rs `into_gl`): one
/// context per process. `warm`: the GL context made as the process started (taken by the first GPU open).
pub(crate) fn reopen(session: &mut Option<Session>, req: &Value, warm: &mut Option<Result<crate::painter::Gl, String>>) -> Result<Value, String> {
    if let Some(gl) = session.take().and_then(|s| s.painter.into_gl()) {
        *warm = Some(Ok(gl));
    }
    let (s, reply) = open(req, warm)?;
    *session = Some(s);
    Ok(reply)
}

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
    // On the GPU unless asked for the CPU; on the CPU too, said in plain words, when the GPU can't be used (painter.rs `best`).
    let (painter, fallback) = match (req["cpu"].as_bool() == Some(true), warm.take()) {
        (true, _) => (Painter::cpu(width, height, color.surface_space())?, None),
        (false, gl) => match Painter::best(gl, width, height, color.surface_space())? {
            (p, Ok(())) => (p, None),
            (p, Err(why)) => {
                eprintln!("2D engine: no GPU painter ({why}); painting on the CPU");
                (p, Some(crate::painter::NO_GPU))
            }
        },
    };
    let painter_ms = t1.elapsed().as_secs_f64() * 1000.0;
    let painting = json!({ "gpu": painter.is_gpu(), "adapter": painter.gpu_name().unwrap_or(""), "fallback": fallback });
    let sink = match req.get("encode") {
        Some(e) => {
            let program = e["program"].as_str().ok_or("encode needs program")?;
            let args: Vec<String> = e["args"].as_array().ok_or("encode needs args")?.iter().filter_map(|a| a.as_str().map(String::from)).collect();
            Some(Sink::start(program, &args, e["repeat"].as_bool() == Some(true))?)
        }
        None => None,
    };
    let scratch = keep::Scratch::new(|| DocumentConfig { base_url: Some(BASE_URL.into()), ..Default::default() });
    let mut reply = json!({ "ok": true, "depth": if deep { 16 } else { 8 }, "timing": { "pageMs": page_ms, "painterMs": painter_ms } });
    with_painting(&mut reply, &painting);
    Ok((Session { doc, stage, assets, painter, width, height, deep, color, sink, scratch, kept_pieces: Default::default(), next_pieces: None, sample_pieces: vec![], sample_bases: vec![], shm: None, deferred: None, painting, over: None, stage_open: false }, reply))
}

/// What a drawing worker's session copies from the export's (`twin`): size, depth, colour and what paints.
pub(crate) struct Like {
    width: u32,
    height: u32,
    deep: bool,
    color: Spec,
    /// The graphics card's name when it paints on the GPU, None on the CPU.
    gpu: Option<String>,
    painting: Value,
}

impl Session {
    pub(crate) fn like(&self) -> Like {
        let gpu = self.painter.is_gpu().then(|| self.painter.gpu_name().unwrap_or("").to_string());
        Like { width: self.width, height: self.height, deep: self.deep, color: self.color, gpu, painting: self.painting.clone() }
    }
}

/// A session like `like` on the page shell `html`, made on the calling thread: an export's drawing worker
/// (export_crew.rs). It paints as the export's session does, never otherwise: on the GPU through its own GL context
/// (made and used on this thread only) on the same graphics card, or on the CPU; a worker that can't is an error,
/// never a different picture. No encoder of its own; the loader feImages decode through stays the export's (the same colour).
pub(crate) fn twin(like: &Like, html: &str) -> Result<Session, String> {
    let Like { width, height, deep, color, .. } = *like;
    let assets = Assets::new(color);
    let (doc, stage) = shell(html, page_config(width, height, &assets), &assets)?;
    let painter = match &like.gpu {
        Some(card) => {
            let p = Painter::gpu_on(crate::painter::gl_context()?, width, height, color.surface_space())?;
            if p.gpu_name().unwrap_or("") != card {
                return Err(format!("a drawing worker got the graphics card \"{}\", not \"{card}\"", p.gpu_name().unwrap_or("")));
            }
            p
        }
        None => Painter::cpu(width, height, color.surface_space())?,
    };
    let scratch = keep::Scratch::new(|| DocumentConfig { base_url: Some(BASE_URL.into()), ..Default::default() });
    let painting = like.painting.clone();
    Ok(Session { doc, stage, assets, painter, width, height, deep, color, sink: None, scratch, kept_pieces: Default::default(), next_pieces: None, sample_pieces: vec![], sample_bases: vec![], shm: None, deferred: None, painting, over: None, stage_open: false })
}

/// Adds what paints (`gpu`, `adapter`, `fallback`: the plain reason it paints on the CPU, null on the GPU) to a reply.
pub(crate) fn with_painting(reply: &mut Value, painting: &Value) {
    if let (Some(r), Some(p)) = (reply.as_object_mut(), painting.as_object()) {
        r.extend(p.clone());
    }
}

/// The page document's settings at a frame size, its loads through `assets`.
pub(crate) fn page_config(width: u32, height: u32, assets: &Assets) -> DocumentConfig {
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

/// Lays the page out with every picture it names in place. Pictures named by CSS (`background-image`, `mask-image`)
/// are asked for while styles resolve; their bytes come back (at once: Assets::fetch is synchronous) as messages,
/// taken in here, so the frame drawn next shows them. Without it a picture used only as a background (a tiled fill)
/// drew as nothing on its first frame, and on every frame of a still or a fresh export.
pub(crate) fn settle(doc: &mut HtmlDocument) {
    doc.handle_messages();
    doc.resolve(0.0);
    doc.handle_messages();
}

/// A page shell parsed and resolved, and its stage element.
fn shell(html: &str, config: DocumentConfig, assets: &Assets) -> Result<(HtmlDocument, NodeId), String> {
    let mut doc = HtmlDocument::from_html(html, config);
    settle(&mut doc);
    failures(assets)?;
    let stage = doc.query_selector(STAGE).map_err(|_| "bad selector")?.ok_or("the page shell has no <div id=\"rostrum-stage\">")?;
    Ok((doc, stage))
}

/// `page`: another page shell on the open session (a live preview's next prepared document): the document is
/// replaced; the painter (its GPU context and surfaces), the colour spec, the encoder and the scratch parser stay.
pub(crate) fn page(s: &mut Session, req: &Value) -> Result<Value, String> {
    let html = req["html"].as_str().ok_or("page needs html")?;
    let t0 = Instant::now();
    let (doc, stage) = shell(html, page_config(s.width, s.height, &s.assets), &s.assets)?;
    s.doc = doc;
    s.stage = stage;
    s.stage_open = false;
    s.kept_pieces = Default::default();
    Ok(json!({ "ok": true, "timing": { "pageMs": t0.elapsed().as_secs_f64() * 1000.0 } }))
}

/// Each stage child painted alone on the laid-out page, and the ms the GPU took for it (waited for): the export's
/// "where render time goes" (scene_export.rs). Named by the child's `id` (a layer's id; the background has none).
pub(crate) fn time_each(s: &mut Session) -> Result<Vec<(Option<String>, f64)>, String> {
    let kids = stage_kids(s);
    let mut out = vec![];
    s.painter.sync();
    let timed = (|| -> Result<(), String> {
        for &k in &kids {
            blitz_paint::set_plan(kids.iter().filter(|&&o| o != k).map(|&o| (o, blitz_paint::Run::Skip)).collect());
            let id = s.doc.get_node(k).and_then(|n| n.attrs()).and_then(|a| a.iter().find(|a| &*a.name.local == "id").map(|a| a.value.to_string()));
            crate::profile::label(id.as_deref().unwrap_or("piece"));
            let t = Instant::now();
            paint(s, false)?;
            s.painter.sync();
            out.push((id, t.elapsed().as_secs_f64() * 1000.0));
        }
        Ok(())
    })();
    blitz_paint::set_plan(Default::default());
    crate::profile::label("frame");
    timed.map(|_| out)
}

/// The stage's children (one per piece when restage.rs cut the stage) in order.
pub(crate) fn stage_kids(s: &Session) -> Vec<NodeId> {
    s.doc.get_node(s.stage).map_or(vec![], |n| n.children.to_vec())
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
pub(crate) fn apply(s: &mut Session, markup: &str) -> Result<(f64, f64, usize), String> {
    let t0 = Instant::now();
    // The new stage (or only its changed pieces), parsed on its own (no styles, no loads), walked beside the kept one.
    let pieces = s.next_pieces.take();
    let edits = crate::restage::edits(&s.doc, s.stage, &mut s.scratch, &mut s.kept_pieces, pieces, markup)?;
    let diff_ms = t0.elapsed().as_secs_f64() * 1000.0;
    let t1 = Instant::now();
    keep::apply(&mut s.doc, &s.scratch.0, &edits);
    s.doc.handle_messages();
    crate::stage_profile::note(crate::stage_profile::APPLY, t1.elapsed().as_secs_f64() * 1000.0);
    s.doc.resolve(0.0);
    s.doc.handle_messages();          // pictures CSS asked for while resolving (settle)
    crate::stage_profile::note(crate::stage_profile::EDITS, edits.count() as f64);
    crate::stage_profile::note(crate::stage_profile::DIFF, diff_ms);
    crate::stage_profile::row();
    failures(&s.assets)?;
    Ok((diff_ms, t1.elapsed().as_secs_f64() * 1000.0, edits.count()))
}

/// Lifts the stage's clip at the comp's edge (`open`: the world picture shows the endless canvas round the frame) or
/// puts it back (every other frame: the export clips at the frame exactly as before, byte for byte). Only a change is
/// written, so a run of frames of one kind restyles nothing.
pub(crate) fn open_stage(s: &mut Session, open: bool) {
    if s.stage_open == open {
        return;
    }
    let style = blitz_dom::QualName::new(None, blitz_dom::ns!(), blitz_dom::local_name!("style"));
    let mut m = s.doc.mutate();
    if open {
        m.set_attribute(s.stage, style, "overflow: visible");
    } else {
        m.clear_attribute(s.stage, style);
    }
    drop(m);
    s.stage_open = open;
}

/// The paint plan of grouped sub-frame `i` drawn from its group's kept pictures (still_runs.rs): still runs as kept, each
/// kept moved layer moved by its own matrix, every other piece drawn as the page holds it, which must be the same
/// text as this sample's (the page was last staged from sample `applied`; `base` is the group's middle sample, whose
/// pieces were kept). None when a piece is neither.
fn moved_plan(kids: &[NodeId], cuts: &[Vec<String>], runs: &[std::ops::Range<usize>], keep: &HashMap<usize, (usize, [f64; 6], usize)>, i: usize, base: usize, applied: Option<usize>, view: (f32, f32, f32)) -> Option<HashMap<NodeId, blitz_paint::Run>> {
    let (cut, page) = (&cuts[i], &cuts[applied?]);
    if kids.len() != cut.len() || page.len() != cut.len() {
        return None;
    }
    let mut plan = if runs.is_empty() { HashMap::new() } else { crate::still_runs::kept(kids, runs) };
    let mut p = 0;
    while p < cut.len() {
        if runs.iter().any(|r| r.contains(&p)) {
            p += 1;
            continue;
        }
        if let Some(&(slot, from, end)) = keep.get(&p) {
            // Compared with the base's piece (the one kept), not the page's: the page may hold another sample's matrix.
            // The run's other pieces move alike in every sample of the group (checked when it was kept): skipped.
            let to = crate::still_runs::moved(&cut[p], &cuts[base][p])?;
            plan.insert(kids[p], blitz_paint::Run::Moved(slot, crate::still_runs::delta(to, from, view)?));
            for q in p + 1..end {
                plan.insert(kids[q], blitz_paint::Run::Skip);
            }
            p = end;
            continue;
        }
        if cut[p] != page[p] {
            return None;
        }
        p += 1;
    }
    Some(plan)
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

/// The most memory a motion-blurred frame's kept pictures take on the graphics card (still runs and a group's moving
/// runs, each a whole frame): the laptop's card has 4 GB; past this its memory spills and a frame takes minutes.
const KEPT_BYTES: usize = 768 << 20;

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

/// The most a `view` crop may enlarge (64 × is the canvas's top zoom) and the largest picture side it may make.
const VIEW_MOST_SCALE: f64 = 64.0;
const VIEW_MOST_PX: f64 = 8192.0;

/// The part of the page a frame draws (painter.rs `View`): the whole comp unless the request asks, only on `pixels`
/// frames (the live canvas; stills, pictures, scopes and exports are the comp's size):
/// `scale` 0.5 / 0.25: the whole comp smaller (playing); `view {x, y, w, h, scale}`: the comp px crop x..x+w, y..y+h
/// drawn at any scale up to 64 (the zoomed-in canvas drawn sharp; the picture at most 8192 px a side).
fn preview_view(req: &Value, width: u32, height: u32) -> Result<crate::painter::View, String> {
    let full = crate::painter::View::full(width, height);
    let scale = match &req["scale"] {
        Value::Null => 1.0,
        v => v.as_f64().ok_or_else(|| format!("scale is 1, 0.5 or 0.25; got {v}"))?,
    };
    if ![1.0, 0.5, 0.25].contains(&scale) {
        return Err(format!("scale is 1, 0.5 or 0.25; got {scale}"));
    }
    // The world picture (scene_world.rs): any page px rectangle, the endless canvas around the frame.
    let page = &req["pageView"];
    let view = if page.is_null() { &req["view"] } else { page };
    let elsewhere = ["image", "rgba", "encode", "scopes", "sample"].iter().any(|k| !matches!(req[*k], Value::Null | Value::Bool(false)));
    if (scale != 1.0 || !view.is_null()) && (req["pixels"].as_bool() != Some(true) || elsewhere) {
        return Err("scale and view are for pixels frames (the live canvas) only; pictures, scopes and exports are drawn at the comp's size".into());
    }
    if view.is_null() {
        return Ok(crate::painter::View { scale: scale as f32, ..full });
    }
    if scale != 1.0 {
        return Err("a frame takes scale or view, not both".into());
    }
    let n = |k: &str| view[k].as_f64().filter(|v| v.is_finite()).ok_or_else(|| format!("view needs x, y, w, h, scale (numbers); {k} is {}", view[k]));
    let (x, y, w, h, k) = (n("x")?, n("y")?, n("w")?, n("h")?, n("scale")?);
    if w <= 0.0 || h <= 0.0 || page.is_null() && (x < -0.5 || y < -0.5 || x + w > width as f64 + 0.5 || y + h > height as f64 + 0.5) {
        return Err(format!("view {x}, {y}, {w} × {h} is not inside the {width} × {height} comp"));
    }
    if !(k > 0.0 && k <= VIEW_MOST_SCALE) || (w * k).round() > VIEW_MOST_PX || (h * k).round() > VIEW_MOST_PX {
        return Err(format!("view scale {k} on {w} × {h}: the scale is above 0 and at most {VIEW_MOST_SCALE}, the picture at most {VIEW_MOST_PX} px a side"));
    }
    Ok(crate::painter::View { scale: k as f32, x0: x as f32, y0: y as f32, w: w as f32, h: h as f32 })
}

/// One frame: the reply, and the rgba bytes that follow it when asked for.
pub(crate) fn frame(s: &mut Session, req: &Value) -> Result<(Value, Option<Vec<u8>>), String> {
    let markup = req["stage"].as_str().ok_or("frame needs stage")?;
    // The same laid-out page, drawn smaller (playing) or a crop of it larger (zoomed in): painter.rs `set_view`.
    let view = preview_view(req, s.width, s.height)?;
    s.painter.set_view(view)?;
    open_stage(s, !req["pageView"].is_null());
    let scale = view.scale;
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
    let (mut still_ms, mut still_pieces) = (0.0, 0);
    // Grouped sub-frames drawn from their group's kept pictures (no staging, no layer painted again): `timing.movedSamples`.
    let mut moved_samples = 0;
    let mut timed = |s: &mut Session, mk: Option<&str>, draw: bool, held: bool| -> Result<(), String> {
        if let Some(mk) = mk {
            let (d, l, e) = apply(s, mk)?;
            (diff_ms, layout_ms, edits) = (diff_ms + d, layout_ms + l, edits + e);
        }
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
        timed(s, Some(markup), true, false)?;
    } else {
        // Motion blur: every sub-frame painted and summed with an equal share (then, held, the stage over the sum).
        // Each sub-frame is staged from its pieces when the caller cut them (restage.rs): only what moved is parsed.
        // The runs of pieces that are the same in every sub-frame are painted once, at the first (still_runs.rs).
        let own = s.next_pieces.take();
        let cuts = std::mem::take(&mut s.sample_pieces);
        let bases = std::mem::take(&mut s.sample_bases);
        // Not grouped (the layers' own moves need every sub-frame): all of them still share one base, the middle one, so
        // a layer only the frame moves (a depth layer under a pan, with its depth-of-field blur) is painted once a frame
        // and slid, as in a group; what moves on its own is drawn per sub-frame as before (B1). Exact as a group is: the
        // slid piece's markup is the base's but for its frame matrix (still_runs.rs `moving_runs`).
        let bases = if bases.is_empty() && samples.len() >= 2 && cuts.len() == samples.len() { vec![samples.len() / 2; samples.len()] } else { bases };
        let runs = crate::still_runs::of(&cuts);
        let pieces = cuts.first().map_or(0, Vec::len);
        let grouped = bases.len() == samples.len() && cuts.len() == samples.len();
        let k = 1.0 / samples.len() as f32;
        let view = s.painter.view();
        let drawn = (|| -> Result<(), String> {
            // Grouped sub-frames (still_runs.rs `order`): the group's moved layers kept at its middle sample, by a run's
            // first piece (still_runs.rs `moving_runs`): (kept picture, the matrix it was drawn through, the run's end);
            // `applied` is the sample the page was last staged from.
            let (mut group, mut keep): (Option<usize>, HashMap<usize, (usize, [f64; 6], usize)>) = (None, HashMap::new());
            // The most pictures a frame keeps at once (KEPT_BYTES): past it a group's other moving runs are drawn whole each sample.
            let most_kept = (KEPT_BYTES / (s.width as usize * s.height as usize * if s.deep { 8 } else { 4 }).max(1)).max(2);
            let (mut applied, mut still_kept) = (None::<usize>, 0);
            for (nth, i) in crate::still_runs::order(if grouped { &bases } else { &[] }, samples.len()).into_iter().enumerate() {
                // Another sample of the group whose base is drawn: its moved layers' pictures moved, its other pieces
                // as the page shows them (the same text as the sample it was last staged from), nothing staged.
                if grouped && bases[i] != i && group == Some(bases[i]) {
                    let mut plan = moved_plan(&stage_kids(s), &cuts, &runs, &keep, i, bases[i], applied, view);
                    // A piece neither kept nor as the page holds it (one that moves but can't be slid: a glow, a blend):
                    // this sample is staged (only its changed pieces, mostly as text edits: restage.rs) and that piece
                    // drawn anew, the kept pictures still slid. It used to draw the whole sample, every layer and its
                    // depth-of-field blur, in every sub-frame of the group (Undertow r2: its glowing water at depth 0 did so in
                    // every drop frame, which took 5-35 s each).
                    if plan.is_none() && !keep.is_empty() {
                        s.next_pieces = cuts.get(i).cloned();
                        timed(s, Some(samples[i]), false, false)?;
                        applied = Some(i);
                        plan = moved_plan(&stage_kids(s), &cuts, &runs, &keep, i, bases[i], applied, view);
                    }
                    if let Some(plan) = plan {
                        blitz_paint::set_plan(plan);
                        timed(s, None, true, false)?;
                        s.painter.accumulate(nth == 0, k)?;
                        moved_samples += 1;
                        continue;
                    }
                }
                s.next_pieces = cuts.get(i).cloned();
                timed(s, Some(samples[i]), false, false)?;
                applied = Some(i);
                let kids = stage_kids(s);
                if runs.is_empty() || kids.len() != pieces {
                    blitz_paint::set_plan(Default::default());
                } else {
                    if nth == 0 {
                        let t = Instant::now();
                        for r in 0..runs.len() {
                            blitz_paint::set_plan(crate::still_runs::only(&kids, &runs, r));
                            timed(s, None, true, false)?;
                            s.painter.keep_cached();
                        }
                        (still_ms, still_pieces) = (t.elapsed().as_secs_f64() * 1000.0, crate::still_runs::count(&runs));
                        still_kept = s.painter.cached_len();
                    }
                    blitz_paint::set_plan(crate::still_runs::kept(&kids, &runs));
                }
                if grouped && bases[i] == i && kids.len() == pieces {
                    // A group's base: each of its frame-moved layers painted alone and kept, then drawn in its place.
                    s.painter.truncate_cached(still_kept);
                    keep.clear();
                    group = Some(i);
                    let mut plan = if runs.is_empty() { HashMap::new() } else { crate::still_runs::kept(&kids, &runs) };
                    // The moving pieces that move alike, in a row, painted together and kept as one picture (still_runs.rs `moving_runs`).
                    for (run, m) in crate::still_runs::moving_runs(&cuts, &bases, i, &runs, view) {
                        if s.painter.cached_len() >= most_kept {
                            break;
                        }
                        blitz_paint::set_plan(kids.iter().enumerate().filter(|(q, _)| !run.contains(q)).map(|(_, &o)| (o, blitz_paint::Run::Skip)).collect());
                        timed(s, None, true, false)?;
                        s.painter.keep_cached();
                        let slot = s.painter.cached_len() - 1;
                        plan.insert(kids[run.start], blitz_paint::Run::Cached(slot));
                        for q in run.start + 1..run.end {
                            plan.insert(kids[q], blitz_paint::Run::Skip);
                        }
                        keep.insert(run.start, (slot, m, run.end));
                    }
                    blitz_paint::set_plan(plan);
                }
                timed(s, None, true, false)?;
                s.painter.accumulate(nth == 0, k)?;
            }
            Ok(())
        })();
        blitz_paint::set_plan(Default::default());
        s.painter.clear_cached();
        drawn?;
        if held || boxes_wanted {
            s.next_pieces = own;
            timed(s, Some(markup), held, held)?;
        }
    }
    if let Some((image, m, clip)) = s.over.take() {
        s.painter.draw_over(&image, &m, &clip);
    }
    if req["noRead"].as_bool() == Some(true) {
        // Drawn and kept on the GPU (the frame's export for the world picture, scene_world.rs): nothing read back.
        let timing = json!({ "diffMs": diff_ms, "layoutMs": layout_ms, "paintMs": paint_ms, "edits": edits, "samples": samples.len().max(1), "movedSamples": moved_samples, "decodeMs": decode_ms });
        return Ok((json!({ "ok": true, "timing": timing }), None));
    }
    let t2 = Instant::now();
    let (w, h) = (s.width, s.height);
    if req["encode"].as_bool() == Some(true) {
        // To the encoder: the frame's readback is started and collected while the next frame is made (one
        // frame in flight): the encoder's bytes from the GPU's output step (gpu_output_queue.rs), else as stored
        // (readback.rs); or read now where the GPU cannot.
        s.sink.as_ref().ok_or("encode frames need an encoder (open.encode)")?;
        let mut wait_ms = 0.0;
        if s.painter.start_read(index, &s.color, s.deep)? {
            paint_ms += t2.elapsed().as_secs_f64() * 1000.0;
            while s.painter.reads_in_flight() > 1 {
                wait_ms += collect(s)?;
            }
        } else {
            let raw = s.painter.read()?;
            paint_ms += t2.elapsed().as_secs_f64() * 1000.0;
            let t3 = Instant::now();
            let px = Pixels { raw, spec: s.color, width: w, deep: s.deep, index, ready: false, repeat: false };
            s.sink.as_mut().unwrap().push(px)?;
            wait_ms += t3.elapsed().as_secs_f64() * 1000.0;
        }
        let boxes = if boxes_wanted { crate::boxes::boxes(&s.doc, w, h) } else { Value::Null };
        // The comp-cache buffers the frame tapped are on disk before it is answered (the host looks them up next).
        s.painter.taps_written()?;
        tap_write_ms += s.painter.last_tap_write_ms;
        let timing = json!({ "diffMs": diff_ms, "layoutMs": layout_ms, "paintMs": paint_ms, "recordMs": record_ms, "readMs": s.painter.last_read_ms, "convertMs": s.painter.last_convert_ms, "edits": edits, "samples": samples.len().max(1), "movedSamples": moved_samples, "stillMs": still_ms, "stillPieces": still_pieces, "encodeWaitMs": wait_ms, "decodeMs": decode_ms, "pictures": urls.len(), "decoded": decoded, "gpuMs": s.painter.last_gpu_ms, "taps": taps, "tapReadMs": tap_read_ms, "tapWriteMs": tap_write_ms });
        return Ok((json!({ "ok": true, "timing": timing, "boxes": boxes }), None));
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
        let mut timing = json!({ "diffMs": diff_ms, "layoutMs": layout_ms, "paintMs": paint_ms, "recordMs": record_ms, "readMs": s.painter.last_read_ms, "convertMs": 0.0, "edits": edits, "samples": samples.len().max(1), "movedSamples": moved_samples, "stillMs": still_ms, "stillPieces": still_pieces, "decodeMs": decode_ms, "pictures": urls.len(), "decoded": decoded, "gpuMs": s.painter.last_gpu_ms, "taps": taps, "tapReadMs": tap_read_ms, "tapWriteMs": tap_write_ms, "gpuOutput": true });
        let boxes = if boxes_wanted { crate::boxes::boxes(&s.doc, w, h) } else { Value::Null };
        let t4 = Instant::now();
        let path = image.unwrap();
        jpeg_encoder::Encoder::new_file(path, 75).and_then(|e| e.encode(&pixels, w as u16, h as u16, jpeg_encoder::ColorType::Rgba)).map_err(|e| format!("writing {path}: {e}"))?;
        timing["writeMs"] = json!(t4.elapsed().as_secs_f64() * 1000.0);
        return Ok((json!({ "ok": true, "timing": timing, "boxes": boxes, "scopes": Value::Null }), None));
    }
    // Scopes and samples measure the frame as stored; anything else goes through the output step on the GPU when it can
    // (`convert`), which reads nothing else back.
    let analyse = req.get("scopes").is_some() || !req["sample"].is_null();
    let mut raw = if analyse { Some(s.painter.read()?) } else { None };
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
            let frame = crate::scopes::from_f16(&s.color.pipeline, raw.as_ref().unwrap(), w as usize, h as usize, domain);
            crate::scopes::run(&frame, sc)?
        }
        None => Value::Null,
    };
    // Sample (G7): the frame's ACEScg light, for `match` (scopes.rs).
    let sample_out = match req["sample"].as_str() {
        Some(path) => {
            let frame = crate::scopes::from_f16(&s.color.pipeline, raw.as_ref().unwrap(), w as usize, h as usize, rostrum_color::scope::Domain::AcesCg);
            crate::scopes::write_sample(&frame, path)?;
            json!(path)
        }
        None => Value::Null,
    };
    let shared = req["pixels"].as_bool() == Some(true);
    if image.is_none() && req["rgba"].as_bool() != Some(true) && !shared && (!scopes_out.is_null() || !sample_out.is_null()) {
        taps_done(s, &mut tap_write_ms)?;
        return Ok((json!({ "ok": true, "scopes": scopes_out, "sample": sample_out }), None));
    }
    if shared && image.is_none() {
        // Into the canvas's shared memory (handoff.rs): the same output step as every frame, no pipe; at the painter's
        // size (smaller with `scale`). Deferred (a frame drawn ahead: serve_ahead.rs), the memory is written when asked.
        let started = crate::handoff::start(s, raw.take(), req["screen"].as_bool() == Some(true), index)?;
        taps_done(s, &mut tap_write_ms)?;
        paint_ms += t2.elapsed().as_secs_f64() * 1000.0;
        let (pw, ph) = s.painter.size();
        let timing = json!({ "diffMs": diff_ms, "layoutMs": layout_ms, "paintMs": paint_ms, "recordMs": record_ms, "edits": edits, "samples": samples.len().max(1), "movedSamples": moved_samples, "stillMs": still_ms, "stillPieces": still_pieces, "scale": scale, "flushMs": s.painter.last_flush_ms, "taps": taps, "tapReadMs": tap_read_ms, "gpuCache": s.painter.gpu_cache() });
        let boxes = if boxes_wanted { crate::boxes::boxes(&s.doc, w, h) } else { Value::Null };
        let mut reply = json!({ "ok": true, "width": pw, "height": ph, "timing": timing, "boxes": boxes, "scopes": scopes_out });
        if req["defer"].as_bool() == Some(true) {
            s.deferred = Some(started);
        } else {
            crate::handoff::finish(s, started, &mut reply)?;
        }
        return Ok((reply, None));
    }
    let deep = s.deep && image.is_none();
    let mut pixels = vec![0u8; (w * h) as usize * if deep { 8 } else { 4 }];
    convert(&mut s.painter, &s.color, &mut raw, w, deep, fast, index, &mut pixels)?;
    taps_done(s, &mut tap_write_ms)?;
    paint_ms += t2.elapsed().as_secs_f64() * 1000.0;
    let mut timing = json!({ "diffMs": diff_ms, "layoutMs": layout_ms, "paintMs": paint_ms, "recordMs": record_ms, "readMs": s.painter.last_read_ms, "convertMs": s.painter.last_convert_ms, "edits": edits, "samples": samples.len().max(1), "movedSamples": moved_samples, "stillMs": still_ms, "stillPieces": still_pieces, "decodeMs": decode_ms, "pictures": urls.len(), "decoded": decoded, "gpuMs": s.painter.last_gpu_ms, "taps": taps, "tapReadMs": tap_read_ms, "tapWriteMs": tap_write_ms });
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
        return Ok((json!({ "ok": true, "timing": timing, "boxes": boxes, "scopes": scopes_out }), None));
    }
    if req["rgba"].as_bool() == Some(true) {
        return Ok((json!({ "ok": true, "bytes": pixels.len(), "timing": timing, "boxes": boxes, "scopes": scopes_out }), Some(pixels)));
    }
    Err("frame needs image (a .png / .jpg path), rgba: true or pixels: true".into())
}

/// The last frame through the output step into `out`: on the GPU, exact, when it can and the frame was not read back already
/// (`raw`), else read and converted on the CPU: the same bytes either way (color.rs `gpu_codes`).
#[allow(clippy::too_many_arguments)]
fn convert(p: &mut crate::painter::Painter, spec: &crate::color::Spec, raw: &mut Option<Vec<u8>>, w: u32, deep: bool, fast: bool, index: u32, out: &mut [u8]) -> Result<(), String> {
    if raw.is_none() {
        if let Some(done) = p.output_into(spec, deep, false, out) {
            return done;
        }
        *raw = Some(p.read()?);
    }
    let t = Instant::now();
    crate::color::output_into(spec, raw.as_ref().unwrap(), w, deep, fast, index, out);
    p.last_convert_ms = t.elapsed().as_secs_f64() * 1000.0;
    Ok(())
}

/// The oldest frame in flight, read back and queued for the encoder (bytes read back as stored are converted on a
/// drawing worker or the writer thread). Returns the ms spent (waiting for the GPU or the encoder).
fn collect(s: &mut Session) -> Result<f64, String> {
    let t = Instant::now();
    let (raw, index, ready) = s.painter.finish_read()?;
    let px = Pixels { raw, spec: s.color, width: s.width, deep: s.deep, index, ready, repeat: false };
    s.sink.as_mut().ok_or("no encoder")?.push(px)?;
    Ok(t.elapsed().as_secs_f64() * 1000.0)
}

/// Frame `index` is the same picture as the export's frame before it (export_crew.rs: the same stage): the encoder gets
/// that frame again, nothing drawn or read back. This worker's frames in flight go first, so it never waits on its own.
pub(crate) fn repeat(s: &mut Session, index: u32) -> Result<(), String> {
    drain(s)?;
    let px = Pixels { raw: vec![], spec: s.color, width: s.width, deep: s.deep, index, ready: true, repeat: true };
    s.sink.as_mut().ok_or("no encoder")?.push(px)
}

/// Every frame in flight to the encoder, then the encoder closed and waited for.
pub(crate) fn finish(s: &mut Session) -> Result<i32, String> {
    drain(s)?;
    s.sink.as_mut().ok_or("finish without an encoder (open.encode)")?.finish()
}

/// Every frame in flight read back and queued for the encoder.
pub(crate) fn drain(s: &mut Session) -> Result<(), String> {
    while s.painter.reads_in_flight() > 0 {
        collect(s)?;
    }
    Ok(())
}

/// Every frame in flight read back and dropped (an export that failed): the next export starts with none of its frames.
pub(crate) fn drop_in_flight(s: &mut Session) {
    while s.painter.reads_in_flight() > 0 {
        if s.painter.finish_read().is_err() {
            break;
        }
    }
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
    // The scene the engine holds (scene_serve.rs).
    let mut held = crate::scene_serve::Held::default();
    // A frame drawn ahead while playing (serve_ahead.rs).
    let mut ahead: Option<crate::serve_ahead::Ahead> = None;
    // The GPU programs the page's next frames need, built while nothing is asked (warmup.rs): requests are read on a
    // thread of their own so the loop can tell a quiet moment.
    let mut warm_up = crate::warmup::Warm::default();
    let (tx, rx) = std::sync::mpsc::channel::<String>();
    std::thread::spawn(move || {
        for line in stdin.lock().lines() {
            let Ok(line) = line else { break };
            if tx.send(line).is_err() {
                break;
            }
        }
    });
    loop {
        let quiet = warm_up.wait().filter(|_| ahead.is_none() && session.is_some());
        let line = match quiet.map(|w| rx.recv_timeout(w)) {
            Some(Err(std::sync::mpsc::RecvTimeoutError::Timeout)) => {
                warm_up.step(session.as_mut().unwrap());
                continue;
            }
            Some(Err(std::sync::mpsc::RecvTimeoutError::Disconnected)) => break,
            Some(Ok(line)) => line,
            None => match rx.recv() {
                Ok(line) => line,
                Err(_) => break,
            },
        };
        warm_up.asked();
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
        if let Some(r) = crate::serve_ahead::answer(&mut ahead, session.as_mut(), &req) {
            match r {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
            out.flush().unwrap();
            if let (Some(s), Some(f)) = (session.as_mut(), req.get("frame")) {
                ahead = crate::serve_ahead::prepare(&held, s, f);
            }
            continue;
        }
        if req.get("scene").is_some() || req.get("change").is_some() {
            match crate::scene_serve::load(&mut held, &mut session, &mut warm, &req) {
                Ok(r) => {
                    if req.get("scene").is_some() {
                        warm_up.page_loaded();
                    }
                    reply(&mut out, &r)
                }
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(e) = req.get("edit") {
            match crate::scene_serve::edit(&mut held, &mut session, e) {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if req.get("fonts").is_some() {
            match crate::scene_serve::font_list(&held) {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(m) = req.get("measure") {
            match crate::scene_serve::measure(&held, m) {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(l) = req.get("layout") {
            match crate::scene_serve::layout(&held, l) {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(sh) = req.get("shapes") {
            match crate::scene_serve::shapes(sh) {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(b) = req.get("bones") {
            match crate::scene_serve::bones(&held, b) {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(o) = req.get("outline") {
            match crate::scene_serve::outline(&held, o) {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(p) = req.get("place") {
            let r = session.as_mut().ok_or_else(|| "place before scene".to_string()).and_then(|s| crate::scene_serve::place(&held, s, p));
            match r {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(x) = req.get("export") {
            let mut progress = |line: Value| {
                reply(&mut out, &line);
                out.flush().unwrap();
            };
            let r = session.as_mut().ok_or_else(|| "export before scene".to_string()).and_then(|s| crate::scene_export::export(&held, s, x, &mut progress));
            match r {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(o) = req.get("open") {
            held.shell = None;
            match reopen(&mut session, o, &mut warm) {
                Ok(r) => reply(&mut out, &r),
                Err(e) => reply(&mut out, &json!({ "error": e })),
            }
        } else if let Some(f) = req.get("frame") {
            match session.as_mut() {
                None => reply(&mut out, &json!({ "error": "frame before open" })),
                // A frame of the held scene (`t`), or of the stage markup the host wrote (`stage`).
                Some(s) => match if f.get("stage").is_none() && f.get("t").is_some() { crate::scene_serve::frame(&held, s, f) } else { frame(s, f) } {
                    Ok((r, pixels)) => {
                        reply(&mut out, &r);
                        if let Some(px) = pixels {
                            out.write_all(&px).unwrap();
                        }
                        out.flush().unwrap();
                        ahead = crate::serve_ahead::prepare(&held, s, f);
                    }
                    Err(e) => reply(&mut out, &json!({ "error": e })),
                },
            }
        } else if let Some(p) = req.get("page") {
            held.shell = None;
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
            reply(&mut out, &json!({ "error": "unknown request (scene, change, frame, export, edit, open, page, warm, match, finish or close)" }));
        }
        out.flush().unwrap();
    }
}

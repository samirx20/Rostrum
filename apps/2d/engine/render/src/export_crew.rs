//! An export's drawing workers (scene_export.rs): `workers` threads each draw the next frame no worker has taken yet
//! (claimed in order from one counter, so a worker held up by a slow frame never leaves the others idle) through a
//! session of their own (serve.rs `twin`: its own page, and on the GPU its own GL context made and used on that
//! thread), so a frame's layout and paint on the processor overlap other frames' and the graphics card stays fed.
//! The extra workers are kept between exports (export_pool.rs): a film drawn in parts starts each part drawing at once.
//! This thread is worker 0, on the export's own session. Each worker has a markup thread building its next frames'
//! stage ahead (`AHEAD` at most: it claims the frames, in order). A frame is a function of its time
//! alone (cold_warm_tests.rs), so which worker drew it never shows in its pixels.
//!
//! Frames to the encoder go through one turn (sink_turn.rs): every frame once, in order, each worker keeping one
//! frame in flight; a frame drawn early is held there, up to sink_turn.rs `WINDOW`. The card's memory is shared: each session's Skia budget is `budget` (only what is kept between
//! draws depends on it, never the pixels). A failure on any worker stops every worker at its next frame and fails
//! the export with the first failure, naming the frame; nothing is left running.

use std::panic::{catch_unwind, AssertUnwindSafe};
use std::collections::HashMap;
use std::sync::mpsc::{channel, sync_channel, Receiver};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::Instant;

use serde_json::{json, Value};

use crate::render_costs::{Costs, EVERY};
use crate::scene_serve::{draw, stage_at, Held, Staged};
use crate::serve::{self, Session};
use crate::sink::Sink;
use crate::sink_turn::Turn;
use crate::export_pool;
use crate::export_workers::budget;
use crate::slide::Slides;

#[cfg(test)]
#[path = "export_crew_tests.rs"]
mod tests;

/// The frame reply's timing fields summed (ms in the reply, seconds in the sum), in this order in the CSV.
pub const STEPS: [&str; 11] = ["evalMs", "decodeMs", "diffMs", "layoutMs", "paintMs", "stillMs", "recordMs", "gpuMs", "readMs", "convertMs", "encodeWaitMs"];
/// Frames whose markup may be built ahead of the one a worker draws.
const AHEAD: usize = 2;
/// How many frames back a stage's print is kept (`Shared::prints`): a frame whose previous print is gone is drawn.
const PRINTS_KEPT: u64 = 64;

/// What an export's workers share: the next frame to claim, the first failure, and each frame's stage print
/// (scene_serve.rs `Staged::print`) by its number, so a frame whose stage is its previous frame's is repeated in the
/// encoder, not drawn: a still stretch costs its stages and nothing else.
struct Shared {
    claim: AtomicU64,
    failed: Mutex<Option<String>>,
    prints: Mutex<HashMap<u64, u128>>,
    /// Microseconds the drawing workers took to start (their sessions made: page, fonts, GL context; or kept), summed.
    start_us: AtomicU64,
    /// How many extra workers made their session in this export (the others kept theirs: export_pool.rs).
    made: AtomicU64,
}

/// What an extra worker sends this thread: a drawn frame, then its end (its layers' timings, or its failure).
enum Msg {
    Row(Row),
    /// A frame's paint calls for the card thread (`own`): its number in the export, its document number, the calls.
    Tape(u64, u32, anyrender::Tape),
    Done(Result<Costs, String>),
}
/// One drawn frame: its number in the export, ms, the STEPS (ms), motion-blur samples and still pieces.
pub struct Row {
    pub i: u64,
    pub took: f64,
    pub steps: Vec<f64>,
    pub samples: u64,
    pub still: u64,
    /// The same picture as the frame before: repeated in the encoder, not drawn.
    pub repeat: bool,
}

/// An export's frames: `n` from `start` at `fps`.
#[derive(Clone, Copy)]
pub struct Span {
    pub start: f64,
    pub fps: f64,
    pub n: u64,
}

impl Span {
    pub fn time(&self, i: u64) -> f64 {
        self.start + i as f64 / self.fps
    }
    fn index(&self, i: u64) -> u64 {
        (self.time(i) * self.fps).round() as u64
    }
}

/// Draws every frame of `span` with `workers` workers; the rows in frame order and the layers' timings.
/// Also the seconds the extra workers took to start, summed, how many of them made their session now, and the
/// encoder's turn's seconds (sink_turn.rs `spent`). `saves`: the segment files the encoder saves, by the export position
/// each ends at (scene_export.rs `saves`).
#[allow(clippy::too_many_arguments)]
pub fn draw_all(held: &Held, s: &mut Session, req: &Value, span: Span, workers: usize, saves: HashMap<usize, String>, progress: &mut dyn FnMut(Value)) -> Result<(Vec<Row>, Costs, f64, u64, [f64; 3], Value), String> {
    let html = crate::scene_serve::shell_of(held.scene()?, s.width, s.height)?;
    let like = s.like();
    let turn = match s.sink.take() {
        Some(sink) if req["images"].is_null() => {
            let t = Turn::new(sink, (0..span.n).map(|i| span.index(i) as u32).collect(), saves);
            s.sink = Some(Sink::turn(t.clone()));
            Some(t)
        }
        other => {
            s.sink = other;
            None
        }
    };
    // One thread owns the graphics card (`own`): this one, while `workers` others lay frames out and keep their paint calls.
    let card = turn.is_some() && s.painter.is_gpu() && std::env::var(CARD_VAR).map_or(true, |v| v.trim() != "0");
    if let Some(t) = turn.as_ref().filter(|_| card) {
        t.free_this_thread();
    }
    let per = budget(s.width, s.height, workers);
    s.painter.set_budget(per);
    let shared = Shared { claim: AtomicU64::new(0), failed: Mutex::new(None), prints: Mutex::new(HashMap::new()), start_us: AtomicU64::new(0), made: AtomicU64::new(0) };
    let fail = |e: &str| {
        shared.failed.lock().unwrap().get_or_insert_with(|| e.to_string());
        if let Some(t) = &turn {
            t.stop(e);
        }
    };
    let (t0, mut rows, mut costs) = (Instant::now(), vec![], Costs::default());
    let mut note = |row: Row, rows: &mut Vec<Row>| {
        rows.push(row);
        if req["progress"].as_bool() == Some(true) {
            let (done, elapsed) = (rows.len() as u64, t0.elapsed().as_secs_f64());
            progress(json!({ "progress": done, "of": span.n, "elapsedS": elapsed, "leftS": elapsed / done as f64 * (span.n - done) as f64 }));
        }
    };
    let (tx, rx) = channel::<Msg>();
    let tx = Mutex::new(tx);
    let mut ends = vec![];
    // An extra worker: its kept session (export_pool.rs; made on its first export), its frames, then its GPU memory freed.
    let job = |w: usize, slot: &mut Option<Session>| {
        let send = |m: Msg| drop(tx.lock().unwrap().send(m));
        let r = catch_unwind(AssertUnwindSafe(|| {
            let started = Instant::now();
            let (ws, made) = export_pool::session(slot, &like, &html).map_err(|e| format!("export: starting drawing worker {w}: {e}"))?;
            if made {
                shared.made.fetch_add(1, Ordering::Relaxed);
            }
            shared.start_us.fetch_add(started.elapsed().as_micros() as u64, Ordering::Relaxed);
            ws.painter.set_budget(per);
            ws.sink = turn.clone().map(Sink::turn);
            let r = share(held, ws, req, span, &shared, card, &mut |m| send(m));
            let r = settle(ws, r);
            ws.sink = None;
            ws.painter.release();
            r
        }))
        .unwrap_or_else(|_| Err(format!("export: drawing worker {w} panicked")));
        if r.is_err() {
            *slot = None; // a worker that failed starts afresh next time
        }
        if let Err(e) = &r {
            fail(e);
        }
        send(Msg::Done(r));
    };
    let mut pool = std::mem::take(&mut s.pool);
    let extra = if card { workers } else { workers - 1 };
    let mut played = Played::default();
    pool.run(extra, &job, || {
        let mine = if card {
            own(s, &rx, extra, &shared, &mut played, &mut |row| note(row, &mut rows), &mut ends)
        } else {
            share(held, s, req, span, &shared, false, &mut |m| {
                if let Msg::Row(row) = m {
                    note(row, &mut rows);
                }
                while let Ok(m) = rx.try_recv() {
                    match m {
                        Msg::Row(r) => note(r, &mut rows),
                        Msg::Done(d) => ends.push(d),
                        Msg::Tape(..) => {}
                    }
                }
            })
        };
        match settle(s, mine) {
            Ok(c) => costs.merge(c),
            Err(e) => fail(&e),
        }
    });
    // Every worker has finished (Pool::run waits): its rows and its end are all in the channel.
    for m in rx.try_iter() {
        match m {
            Msg::Row(r) => note(r, &mut rows),
            Msg::Done(d) => ends.push(d),
            Msg::Tape(..) => fail("export: a frame's paint calls came after the card thread had stopped"),
        }
    }
    let ended = ends.len();
    for d in ends {
        match d {
            Ok(c) => costs.merge(c),
            Err(e) => fail(&e),
        }
    }
    if ended != extra {
        fail("export: a drawing worker stopped without finishing");
    }
    s.pool = pool;
    s.painter.set_budget(crate::painter::gpu_budget(s.width, s.height));
    s.sink = None; // this thread's turn; the encoder comes back below
    let failure = shared.failed.into_inner().unwrap();
    let turn_s = turn.as_ref().map_or([0.0; 3], |t| t.spent());
    if let Some(t) = turn {
        let sink = Turn::into_sink(t)?;
        // A failed export's encoder is stopped here (dropped), never finished: no partial file is reported as made.
        s.sink = failure.is_none().then_some(sink);
    }
    if let Some(e) = failure {
        return Err(e);
    }
    rows.sort_by_key(|r| r.i);
    if rows.len() as u64 != span.n || rows.iter().enumerate().any(|(k, r)| r.i != k as u64) {
        return Err(format!("export: {} of {} frames were drawn", rows.len(), span.n));
    }
    let card_v = card.then(|| played.report());
    Ok((rows, costs, shared.start_us.load(Ordering::Relaxed) as f64 / 1e6, shared.made.load(Ordering::Relaxed), turn_s, card_v.unwrap_or(Value::Null)))
}

/// `ROSTRUM2D_EXPORT_CARD=0`: every worker paints its own frames on its own card connection (as before round 5).
const CARD_VAR: &str = "ROSTRUM2D_EXPORT_CARD";

/// What the card thread did (`own`): frames played, and ms spent playing their calls, flushing them to the card and
/// waiting for read-backs and the encoder; ms it waited for the workers' next tape.
#[derive(Default)]
struct Played {
    frames: u64,
    ms: [f64; 4],
}

impl Played {
    fn report(&self) -> Value {
        let s = |k: usize| self.ms[k] / 1000.0;
        json!({ "frames": self.frames, "playS": s(0), "flushS": s(1), "readS": s(2), "idleS": s(3) })
    }
}

/// The card thread (this one, on the export's own session): every frame a worker laid out and kept as paint calls is
/// played here, on one graphics connection that never changes thread, lowest frame first, its read-back overlapping the
/// next frame's playing (the frames still on the card are sent on whenever no tape is waiting); the frames a worker
/// painted itself (`Tape::unfit`) and repeats go to the encoder from that worker. Ends when every worker has ended and every tape is played. A tape waiting here is never one a pushing worker
/// waits for in the encoder's turn: the lowest is always played first, so the frame due is never held back here.
fn own(s: &mut Session, rx: &Receiver<Msg>, workers: usize, shared: &Shared, played: &mut Played, note: &mut dyn FnMut(Row), ends: &mut Vec<Result<Costs, String>>) -> Result<Costs, String> {
    let mut waiting: std::collections::BTreeMap<u64, (u32, anyrender::Tape)> = Default::default();
    let mut take = |m: Msg, waiting: &mut std::collections::BTreeMap<u64, (u32, anyrender::Tape)>, ends: &mut Vec<Result<Costs, String>>| match m {
        Msg::Row(r) => note(r),
        Msg::Tape(i, index, tape) => drop(waiting.insert(i, (index, tape))),
        Msg::Done(d) => ends.push(d),
    };
    loop {
        if let Some(e) = shared.failed.lock().unwrap().as_ref() {
            return Err(format!("export stopped: {e}"));
        }
        while let Ok(m) = rx.try_recv() {
            take(m, &mut waiting, ends);
        }
        let Some((i, (index, tape))) = waiting.pop_first() else {
            if ends.len() >= workers {
                return Ok(Costs::default());
            }
            // Nothing to play: the frames still on the card go to the encoder before this thread waits. A worker's
            // repeat of one of them (a still stretch) waits for it in the encoder's turn, and nothing else would send it.
            serve::drain(s).map_err(|e| format!("export (on the card thread): {e}"))?;
            let t = Instant::now();
            match rx.recv() {
                Ok(m) => take(m, &mut waiting, ends),
                Err(_) => return Err("export: the drawing workers went away".into()),
            }
            played.ms[3] += t.elapsed().as_secs_f64() * 1000.0;
            continue;
        };
        let ms = catch_unwind(AssertUnwindSafe(|| serve::play(s, &tape, index)))
            .unwrap_or_else(|p| Err(format!("the engine crashed painting it ({})", panic_words(&p))))
            .map_err(|e| format!("export frame {index} (export frame {i}, on the card thread): {e}"))?;
        played.frames += 1;
        for k in 0..3 {
            played.ms[k] += ms[k];
        }
    }
}

/// A worker's end: its frames in flight to the encoder, or dropped when it failed.
fn settle(s: &mut Session, r: Result<Costs, String>) -> Result<Costs, String> {
    let r = r.and_then(|c| if s.sink.is_some() { serve::drain(s).map(|_| c) } else { Ok(c) });
    if r.is_err() {
        serve::drop_in_flight(s);
    }
    r
}

/// One worker: the frames its markup thread claims from `claim` (each the next no worker has), drawn on `s` in that order.
fn share(held: &Held, s: &mut Session, req: &Value, span: Span, shared: &Shared, card: bool, on_row: &mut dyn FnMut(Msg)) -> Result<Costs, String> {
    let scene = held.scene()?;
    std::thread::scope(|sc| {
        let (tx, rx) = sync_channel::<(u64, Result<Staged, String>)>(AHEAD);
        let builder = sc.spawn(move || {
            loop {
                let i = shared.claim.fetch_add(1, Ordering::Relaxed);
                if i >= span.n {
                    break;
                }
                let staged = stage_at(scene, span.time(i), req);
                if let Ok(st) = &staged {
                    let mut prints = shared.prints.lock().unwrap();
                    prints.insert(i, st.print());
                    prints.remove(&i.wrapping_sub(PRINTS_KEPT));
                }
                let bad = staged.is_err();
                if tx.send((i, staged)).is_err() || bad {
                    break; // the drawing side stopped (its error is the export's), or this frame failed
                }
            }
        });
        let drawn = draw_frames(held, s, req, span, rx, shared, card, on_row);
        // `rx` is gone with draw_frames: a builder still working stops at its next frame.
        match builder.join() {
            Ok(()) => drawn,
            Err(_) => Err("export: the thread building the frames' markup panicked".to_string()),
        }
    })
}

/// Draws the frames `rx` brings on `s`, laid out incrementally as the canvas lays out its frames (one path: preview = export). An
/// exported frame is still a function of its time alone, whichever frames this worker (or the canvas before the export)
/// drew first: incremental layout gives a fresh layout's boxes (vendor/PATCHES.md J1; incremental_tests.rs). Laying every
/// export frame out whole cost Night Bloom ~40 % more layout (calm 4-5 s: 256 vs 147 ms a frame per worker).
#[allow(clippy::too_many_arguments)]
fn draw_frames(held: &Held, s: &mut Session, req: &Value, span: Span, rx: Receiver<(u64, Result<Staged, String>)>, shared: &Shared, card: bool, on_row: &mut dyn FnMut(Msg)) -> Result<Costs, String> {
    let mut slides = Slides::new(s, req);
    let drawn = draw_each(held, s, req, span, rx, shared, card, on_row, &mut slides);
    slides.forget(s);
    if slides.made > 0 {
        eprintln!("export: slid {} frames from {} kept pictures (slide.rs)", slides.slid, slides.made);
    }
    drawn
}

/// `draw_frames`' frames, each slid from a kept picture of its still stage when only the frame moved (slide.rs).
#[allow(clippy::too_many_arguments)]
fn draw_each(held: &Held, s: &mut Session, req: &Value, span: Span, rx: Receiver<(u64, Result<Staged, String>)>, shared: &Shared, card: bool, on_row: &mut dyn FnMut(Msg), slides: &mut Slides) -> Result<Costs, String> {
    let mut costs = Costs::default();
    loop {
        if let Some(e) = shared.failed.lock().unwrap().as_ref() {
            return Err(format!("export stopped: {e}"));
        }
        let tf = Instant::now();
        // No more: every frame is claimed (draw_all checks every one was drawn).
        let Ok((i, staged)) = rx.recv() else { break };
        let t = span.time(i);
        let staged = staged.map_err(|e| format!("export frame {} (t={t:.3} s): {e}", span.index(i)))?;
        // The same stage as the frame before (its print known): that picture again in the encoder, nothing drawn.
        let same = i > 0 && req["images"].is_null() && {
            let prints = shared.prints.lock().unwrap();
            prints.get(&(i - 1)).is_some_and(|p| prints.get(&i) == Some(p))
        };
        if same {
            serve::repeat(s, span.index(i) as u32).map_err(|e| format!("export frame {} (t={t:.3} s): {e}", span.index(i)))?;
            let took = tf.elapsed().as_secs_f64() * 1000.0;
            on_row(Msg::Row(Row { i, took, steps: vec![0.0; STEPS.len()], samples: 0, still: 0, repeat: true }));
            continue;
        }
        let mut f = json!({ "t": t, "index": span.index(i), "alpha": req["alpha"].as_bool() == Some(true) });
        match req["images"].as_str() {
            Some(p) => f["image"] = json!(p.replace("{frame}", &format!("{:04}", span.index(i)))),
            None => f["encode"] = json!(true),
        }
        if card {
            f["tape"] = json!(true);
        }
        // A panic while drawing fails this frame, named, like any error: uncaught on worker 0 (this thread) it left the
        // other workers waiting for its frame in the encoder's turn, and the export hung with no word (p1, 2026-10-25).
        let slid = catch_unwind(AssertUnwindSafe(|| slides.try_slide(held, s, &f, &staged)))
            .unwrap_or_else(|p| Err(format!("the engine crashed sliding it ({})", panic_words(&p))))
            .map_err(|e| format!("export frame {} (t={t:.3} s): {e}", span.index(i)))?;
        if slid.is_none() {
            slides.before_whole(s, &staged);
        }
        let (reply, _) = catch_unwind(AssertUnwindSafe(|| match slid {
            Some(reply) => Ok((reply, None)),
            None => draw(held, s, &f, staged),
        }))
            .unwrap_or_else(|p| Err(format!("the engine crashed drawing it ({})", panic_words(&p))))
            .map_err(|e| format!("export frame {} (t={t:.3} s): {e}", span.index(i)))?;
        let took = tf.elapsed().as_secs_f64() * 1000.0;
        if i % EVERY == EVERY / 2 || span.n <= EVERY / 2 && i == 0 {
            costs.sample(s).map_err(|e| format!("export frame {i}: timing its layers: {e}"))?;
        }
        let timing = &reply["timing"];
        let steps = STEPS.iter().map(|k| timing[*k].as_f64().unwrap_or(0.0)).collect();
        let (samples, still) = (timing["samples"].as_u64().unwrap_or(1), timing["stillPieces"].as_u64().unwrap_or(0));
        on_row(Msg::Row(Row { i, took, steps, samples, still, repeat: false }));
        // Laid out and walked here, painted on the card thread.
        if let Some(tape) = s.tape.take() {
            on_row(Msg::Tape(i, span.index(i) as u32, tape));
        }
    }
    Ok(costs)
}

/// A caught panic's message, in its own words.
fn panic_words(p: &Box<dyn std::any::Any + Send>) -> String {
    p.downcast_ref::<&str>().map(|m| m.to_string()).or_else(|| p.downcast_ref::<String>().cloned()).unwrap_or_else(|| "no message".into())
}

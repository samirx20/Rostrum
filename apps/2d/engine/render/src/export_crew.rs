//! An export's drawing workers (scene_export.rs): `workers` threads each draw the next frame no worker has taken yet
//! (claimed in order from one counter, so a worker held up by a slow frame never leaves the others idle) through a
//! session of their own (serve.rs `twin`: its own page, and on the GPU its own GL context made and used on that
//! thread), so a frame's layout and paint on the processor overlap other frames' and the graphics card stays fed.
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
use crate::export_workers::budget;

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
    /// Microseconds the drawing workers took to start (their sessions made: page, fonts, GL context), summed.
    start_us: AtomicU64,
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
/// Also the seconds the extra workers took to start, summed.
pub fn draw_all(held: &Held, s: &mut Session, req: &Value, span: Span, workers: usize, progress: &mut dyn FnMut(Value)) -> Result<(Vec<Row>, Costs, f64), String> {
    let html = crate::scene_serve::shell_of(held.scene()?, s.width, s.height)?;
    let like = s.like();
    let turn = match s.sink.take() {
        Some(sink) if req["images"].is_null() => {
            let t = Turn::new(sink, (0..span.n).map(|i| span.index(i) as u32).collect());
            s.sink = Some(Sink::turn(t.clone()));
            Some(t)
        }
        other => {
            s.sink = other;
            None
        }
    };
    let per = budget(s.width, s.height, workers);
    s.painter.set_budget(per);
    let shared = Shared { claim: AtomicU64::new(0), failed: Mutex::new(None), prints: Mutex::new(HashMap::new()), start_us: AtomicU64::new(0) };
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
    std::thread::scope(|sc| {
        let (tx, rx) = channel::<Row>();
        let crew: Vec<_> = (1..workers)
            .map(|w| {
                let (tx, turn, html, like, fail, shared) = (tx.clone(), turn.clone(), &html, &like, &fail, &shared);
                sc.spawn(move || {
                    let r = catch_unwind(AssertUnwindSafe(|| {
                        let started = Instant::now();
                        let mut ws = serve::twin(like, html).map_err(|e| format!("export: starting drawing worker {w}: {e}"))?;
                        shared.start_us.fetch_add(started.elapsed().as_micros() as u64, Ordering::Relaxed);
                        ws.painter.set_budget(per);
                        ws.sink = turn.map(Sink::turn);
                        let r = share(held, &mut ws, req, span, shared, &mut |row| drop(tx.send(row)));
                        settle(&mut ws, r)
                    }))
                    .unwrap_or_else(|_| Err(format!("export: drawing worker {w} panicked")));
                    if let Err(e) = &r {
                        fail(e);
                    }
                    r
                })
            })
            .collect();
        drop(tx);
        let mine = share(held, s, req, span, &shared, &mut |row| {
            note(row, &mut rows);
            while let Ok(r) = rx.try_recv() {
                note(r, &mut rows);
            }
        });
        match settle(s, mine) {
            Ok(c) => costs.merge(c),
            Err(e) => fail(&e),
        }
        for r in rx.iter() {
            note(r, &mut rows);
        }
        for h in crew {
            match h.join() {
                Ok(Ok(c)) => costs.merge(c),
                Ok(Err(e)) => fail(&e),
                Err(_) => fail("export: a drawing worker panicked"),
            }
        }
    });
    s.painter.set_budget(crate::painter::gpu_budget(s.width, s.height));
    s.sink = None; // this thread's turn; the encoder comes back below
    let failure = shared.failed.into_inner().unwrap();
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
    Ok((rows, costs, shared.start_us.load(Ordering::Relaxed) as f64 / 1e6))
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
fn share(held: &Held, s: &mut Session, req: &Value, span: Span, shared: &Shared, on_row: &mut dyn FnMut(Row)) -> Result<Costs, String> {
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
        let drawn = draw_frames(held, s, req, span, rx, shared, on_row);
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
fn draw_frames(held: &Held, s: &mut Session, req: &Value, span: Span, rx: Receiver<(u64, Result<Staged, String>)>, shared: &Shared, on_row: &mut dyn FnMut(Row)) -> Result<Costs, String> {
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
            on_row(Row { i, took, steps: vec![0.0; STEPS.len()], samples: 0, still: 0, repeat: true });
            continue;
        }
        let mut f = json!({ "t": t, "index": span.index(i), "alpha": req["alpha"].as_bool() == Some(true) });
        match req["images"].as_str() {
            Some(p) => f["image"] = json!(p.replace("{frame}", &format!("{:04}", span.index(i)))),
            None => f["encode"] = json!(true),
        }
        // A panic while drawing fails this frame, named, like any error: uncaught on worker 0 (this thread) it left the
        // other workers waiting for its frame in the encoder's turn, and the export hung with no word (p1, 2026-10-25).
        let (reply, _) = catch_unwind(AssertUnwindSafe(|| draw(held, s, &f, staged)))
            .unwrap_or_else(|p| Err(format!("the engine crashed drawing it ({})", panic_words(&p))))
            .map_err(|e| format!("export frame {} (t={t:.3} s): {e}", span.index(i)))?;
        let took = tf.elapsed().as_secs_f64() * 1000.0;
        if i % EVERY == EVERY / 2 || span.n <= EVERY / 2 && i == 0 {
            costs.sample(s).map_err(|e| format!("export frame {i}: timing its layers: {e}"))?;
        }
        let timing = &reply["timing"];
        let steps = STEPS.iter().map(|k| timing[*k].as_f64().unwrap_or(0.0)).collect();
        let (samples, still) = (timing["samples"].as_u64().unwrap_or(1), timing["stillPieces"].as_u64().unwrap_or(0));
        on_row(Row { i, took, steps, samples, still, repeat: false });
    }
    Ok(costs)
}

/// A caught panic's message, in its own words.
fn panic_words(p: &Box<dyn std::any::Any + Send>) -> String {
    p.downcast_ref::<&str>().map(|m| m.to_string()).or_else(|| p.downcast_ref::<String>().cloned()).unwrap_or_else(|| "no message".into())
}

//! A frame drawn ahead while playing (ENGINE_CONTRACT.md § 1, `frame` › `ahead`): a `pixels` frame asked with
//! `"ahead": t2` is answered, then the same frame at `t2` is drawn at once and its output started on the GPU, while the
//! host shows the first. When the next request is that frame (the same request with `t2`, whatever its own `ahead`),
//! it is answered from the frame drawn ahead: only its hand-off into the shared memory is left (handoff.rs). Anything
//! else first drops it, unseen: the next frame is then drawn as it always is. The frame drawn ahead is the one the
//! request would draw (the same scene, the same path), so what is shown is the same either way.

use serde_json::Value;

use crate::scene_serve::{self, Held};
use crate::serve::Session;

/// The frame drawn ahead: the request it answers, its reply without the memory, its started output.
pub struct Ahead {
    req: Value,
    reply: Value,
    started: crate::handoff::Started,
}

/// The frame request without its `ahead`.
fn bare(f: &Value) -> Value {
    let mut f = f.clone();
    if let Some(o) = f.as_object_mut() {
        o.remove("ahead");
    }
    f
}

/// Before any request: the frame drawn ahead answers it (Some: the reply) when it is that frame; else it is dropped.
pub fn answer(ahead: &mut Option<Ahead>, session: Option<&mut Session>, req: &Value) -> Option<Result<Value, String>> {
    let a = ahead.take()?;
    let s = session?;
    if req.get("frame").map(bare).as_ref() != Some(&a.req) {
        s.painter.output_cancel();
        return None;
    }
    let (mut reply, t0) = (a.reply, std::time::Instant::now());
    let done = crate::handoff::finish(s, a.started, &mut reply);
    // How long answering took, drawn ahead (`timing.aheadMs`; only on a frame drawn ahead).
    reply["timing"]["aheadMs"] = (t0.elapsed().as_secs_f64() * 1000.0).into();
    Some(done.map(|_| reply))
}

/// After a frame was answered: with `ahead` on a held scene's `pixels` frame, that frame drawn now and its output
/// started. A frame drawn ahead that fails is dropped (the request for it, if it comes, fails or succeeds by itself).
pub fn prepare(held: &Held, s: &mut Session, f: &Value) -> Option<Ahead> {
    let t = f["ahead"].as_f64()?;
    if f["pixels"].as_bool() != Some(true) || f.get("stage").is_some() || f.get("image").is_some() || f["t"].as_f64().is_none() {
        return None;
    }
    let mut req = bare(f);
    req["t"] = t.into();
    let mut deferred = req.clone();
    deferred["defer"] = true.into();
    let drawn = scene_serve::frame(held, s, &deferred);
    match (drawn, s.deferred.take()) {
        (Ok((reply, None)), Some(started)) => Some(Ahead { req, reply, started }),
        _ => {
            s.painter.output_cancel();
            None
        }
    }
}

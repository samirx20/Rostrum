//! The live canvas's hand-off (`frame` with `pixels: true`; ENGINE_CONTRACT.md § 1): a drawn frame through the output
//! step into the next slot of the canvas's shared memory (shm.rs), in two halves so a frame can be drawn ahead and
//! handed over when it is asked for (serve_ahead.rs).
//!
//! `start` queues the GPU output step (gpu_output.rs) for the slot the frame will go into, waiting for nothing; `finish`
//! writes the slot: only the rows that differ from what the slot holds come back from the GPU. Where the GPU step can't
//! run (on the CPU, or the frame was read already for scopes) `finish` converts on the CPU, the same bytes. With
//! `screen` the bytes are in the screen's form (BGRA, premultiplied: `pixels::to_screen`), shown without a step.

use std::time::Instant;

use serde_json::{json, Value};

use crate::serve::Session;

/// A frame drawn and its output started, not yet in the memory.
pub struct Started {
    gpu: bool,
    screen: bool,
    raw: Option<Vec<u8>>,
    index: u32,
}

/// Starts the output of the frame just drawn (`raw`: it was read as stored already); the memory is (re)made at its size.
pub fn start(s: &mut Session, raw: Option<Vec<u8>>, screen: bool, index: u32) -> Result<Started, String> {
    if screen && s.deep {
        return Err("pixels: screen frames are 8-bit; this session draws 16-bit (depth 16)".into());
    }
    let (w, h) = s.painter.size();
    let bytes = (w * h) as usize * if s.deep { 8 } else { 4 };
    if s.shm.as_ref().map(crate::shm::Shm::slot_bytes) != Some(bytes) {
        s.shm = Some(crate::shm::Shm::new(bytes)?);
    }
    let shm = s.shm.as_ref().unwrap();
    let holds = (shm.block, shm.upcoming(), w, h, s.deep, screen);
    let gpu = match raw.is_none().then(|| s.painter.output_start(&s.color, s.deep, screen, Some(holds))).flatten() {
        Some(r) => r.map(|_| true)?,
        None => false,
    };
    Ok(Started { gpu, screen, raw, index })
}

/// The started frame into the memory's next slot: `reply` gets its `shm` and the hand-off's times (`timing`: gpuMs,
/// readMs, convertMs, rowsRead, added to paintMs).
pub fn finish(s: &mut Session, st: Started, reply: &mut Value) -> Result<(), String> {
    let t0 = Instant::now();
    let (w, h) = s.painter.size();
    let shm = s.shm.as_mut().ok_or("pixels: no shared memory")?;
    let at = shm.upcoming();
    let (slot, info) = shm.next(w, h, s.deep, st.screen);
    let rows = if st.gpu {
        s.painter.output_finish(&s.color, slot)?
    } else {
        s.painter.output_forget(at);
        let raw = match st.raw {
            Some(r) => r,
            None => s.painter.read()?,
        };
        let t = Instant::now();
        crate::color::output_into(&s.color, &raw, w, s.deep, false, st.index, slot);
        if st.screen {
            crate::pixels::to_screen(slot);
        }
        s.painter.last_convert_ms = t.elapsed().as_secs_f64() * 1000.0;
        h
    };
    reply["shm"] = info;
    let timing = &mut reply["timing"];
    let paint = timing["paintMs"].as_f64().unwrap_or(0.0) + t0.elapsed().as_secs_f64() * 1000.0;
    for (k, v) in [("gpuMs", s.painter.last_gpu_ms), ("readMs", s.painter.last_read_ms), ("convertMs", s.painter.last_convert_ms), ("paintMs", paint)] {
        timing[k] = json!(v);
    }
    timing["rowsRead"] = json!(rows);
    Ok(())
}

//! Measurement only (E17): where staging a page's time goes. Off unless `ROSTRUM2D_PROFILE_STAGE=<file.csv>` is set;
//! then every staged page (serve.rs `apply`: a frame or one motion-blur sample) appends a row: the pieces that changed
//! and the bytes parsed, reading the changed pieces as text (retext.rs), parsing the rest, the whole comparison (parse + walk beside the kept page), applying the edits, and Blitz's `resolve` phases
//! (vendor blitz-dom `util::PHASE_NANOS`).

use std::cell::RefCell;
use std::io::Write;
use std::sync::atomic::Ordering::Relaxed;
use std::sync::OnceLock;

use blitz_dom::util::PHASE_NANOS;

const COLS: [&str; 16] = ["retextMs", "pieces", "changed", "bytes", "edits", "parseMs", "diffMs", "applyMs", "style", "damage", "construct", "pconstruct", "layout", "transform", "paintTree", "clearDamage"];

fn path() -> Option<&'static str> {
    static P: OnceLock<Option<String>> = OnceLock::new();
    P.get_or_init(|| std::env::var("ROSTRUM2D_PROFILE_STAGE").ok().filter(|p| !p.is_empty())).as_deref()
}

thread_local! {
    static ROW: RefCell<[f64; 8]> = const { RefCell::new([0.0; 8]) };
}

/// Notes one of the row's own values (index into COLS from "frame"): set by restage.rs and serve.rs as they go.
pub fn note(col: usize, v: f64) {
    if path().is_some() {
        ROW.with(|r| r.borrow_mut()[col] = v);
    }
}

/// Appends the staged page's row and clears it.
pub fn row() {
    let Some(p) = path() else { return };
    let new = !std::path::Path::new(p).exists();
    let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(p) else { return };
    if new {
        let _ = writeln!(f, "{}", COLS.join(","));
    }
    let own = ROW.with(|r| std::mem::take(&mut *r.borrow_mut()));
    let phases = PHASE_NANOS.iter().map(|n| format!("{:.3}", n.swap(0, Relaxed) as f64 / 1e6));
    let cells: Vec<String> = own.iter().map(|v| format!("{v:.3}")).chain(phases).collect();
    let _ = writeln!(f, "{}", cells.join(","));
}

pub const RETEXT: usize = 0;
pub const PIECES: usize = 1;
pub const CHANGED: usize = 2;
pub const BYTES: usize = 3;
pub const EDITS: usize = 4;
pub const PARSE: usize = 5;
pub const DIFF: usize = 6;
pub const APPLY: usize = 7;

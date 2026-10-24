//! How many drawing workers an export uses and each one's GPU cache budget (export_crew.rs), measured on the laptop
//! (8 logical cores, a 4 GB RTX 3050) with Night Bloom at 1080p, 4 motion-blur samples a frame.

use serde_json::Value;

const MAX_WORKERS: u64 = 4;
/// Forces the worker count (`workers` in the request wins).
const WORKERS_VAR: &str = "ROSTRUM2D_EXPORT_WORKERS";
/// Forces each worker session's Skia budget, in MB (to measure).
const BUDGET_VAR: &str = "ROSTRUM2D_EXPORT_BUDGET_MB";

/// How many workers draw: the request's `workers`, else ROSTRUM2D_EXPORT_WORKERS, else one per two cores less one (1–3:
/// 3 on the laptop's 8, the fastest measured; each worker is its drawing thread plus its markup thread); never more
/// than there are frames.
pub fn workers(req: &Value, n: u64) -> Result<usize, String> {
    let asked = match &req["workers"] {
        Value::Null => std::env::var(WORKERS_VAR).ok().and_then(|v| v.trim().parse::<u64>().ok()),
        v => Some(v.as_u64().ok_or_else(|| format!("export workers is a count (1 to {MAX_WORKERS}); got {v}"))?),
    };
    let cores = std::thread::available_parallelism().map_or(1, |c| c.get()) as u64;
    let w = asked.unwrap_or((cores / 2).saturating_sub(1).clamp(1, 3));
    if !(1..=MAX_WORKERS).contains(&w) {
        return Err(format!("export workers is 1 to {MAX_WORKERS}; got {w}"));
    }
    Ok(w.min(n).max(1) as usize)
}

/// The card memory several workers' Skia budgets share (MB). Night Bloom's busiest seconds at 1080p: 3 workers × 800 MB
/// peaked at ~3.0 GB of the laptop's 4 GB card, and a budget much under 800 makes each worker rebuild its layers' textures
/// every sample (3 × 600 MB: ~30 % slower).
const SHARED_MB: usize = 2400;

/// Each worker session's Skia budget (bytes): one session's own (painter.rs `gpu_budget`) when it draws alone, else
/// an equal share of SHARED_MB, never under one session's own.
pub fn budget(width: u32, height: u32, workers: usize) -> usize {
    if let Some(mb) = std::env::var(BUDGET_VAR).ok().and_then(|v| v.trim().parse::<usize>().ok()) {
        return mb << 20;
    }
    let one = crate::painter::gpu_budget(width, height);
    if workers == 1 { one } else { one.max((SHARED_MB << 20) / workers) }
}

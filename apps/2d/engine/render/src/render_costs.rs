//! Where an export's render time goes, per layer (E2): every `EVERY`th frame each top-level piece of the stage is
//! painted alone on the GPU and timed (serve.rs `time_each`), and the export's reply gets the 10 that cost most
//! (`timing.layers`): the layer, what it is and which effects it holds (blur, glow …, its own and its children's),
//! the average ms one paint of it took, its share of the timed paint and how often it was in a still run, drawn
//! once for the frame's motion-blur samples instead of each (still_runs.rs). Timing a piece costs a paint, so it
//! runs on 1 frame in `EVERY` only.

use std::collections::BTreeMap;

use serde_json::{json, Value};

use crate::scene::{Node, Scene};
use crate::serve::Session;

/// One frame in this many is timed per layer.
pub const EVERY: u64 = 30;
/// The report lists this many layers, most costly first.
const TOP: usize = 10;

#[derive(Default)]
pub struct Costs {
    /// Per layer id: summed ms, times timed.
    by: BTreeMap<String, (f64, u32)>,
    frames: u32,
}

impl Costs {
    /// Times each piece of the frame just drawn (the page holds its last staged sample).
    pub fn sample(&mut self, s: &mut Session) -> Result<(), String> {
        for (j, (id, ms)) in crate::serve::time_each(s)?.into_iter().enumerate() {
            let e = self.by.entry(id.unwrap_or_else(|| if j == 0 { "background".into() } else { format!("piece {j}") })).or_default();
            (e.0, e.1) = (e.0 + ms, e.1 + 1);
        }
        self.frames += 1;
        Ok(())
    }

    /// Another drawing worker's timings added in (export_crew.rs).
    pub fn merge(&mut self, other: Costs) {
        for (id, (ms, n)) in other.by {
            let e = self.by.entry(id).or_default();
            (e.0, e.1) = (e.0 + ms, e.1 + n);
        }
        self.frames += other.frames;
    }

    /// The top layers, most costly first, for the export's reply.
    pub fn report(&self, scene: &Scene) -> Value {
        let total: f64 = self.by.values().map(|v| v.0).sum::<f64>().max(1e-9);
        let mut rows: Vec<(&String, &(f64, u32))> = self.by.iter().collect();
        rows.sort_by(|a, b| b.1 .0.total_cmp(&a.1 .0));
        let top: Vec<Value> = rows
            .iter()
            .take(TOP)
            .map(|(id, (ms, n))| {
                // A layer seen through the camera is drawn in a `cam~<id>` wrapper (crate::frame).
                let node = find(&scene.comp, id.strip_prefix("cam~").unwrap_or(id));
                json!({
                    "layer": id,
                    "kind": node.map(|l| l.kind),
                    "effects": node.map(effects).unwrap_or_default(),
                    "msPerPaint": ms / *n as f64,
                    "share": ms / total,
                })
            })
            .collect();
        json!({ "framesTimed": self.frames, "every": EVERY, "top": top })
    }
}

/// The effects inside a layer (its own and its children's), as "glow" or "blur ×3".
fn effects(n: &Node) -> Vec<String> {
    let mut count: BTreeMap<&str, usize> = BTreeMap::new();
    let _ = n.walk(&mut |c| {
        if !std::ptr::eq(c, n) && is_effect(c) {
            *count.entry(c.kind).or_default() += 1;
        }
        Ok(())
    });
    count.into_iter().map(|(k, c)| if c == 1 { k.to_string() } else { format!("{k} ×{c}") }).collect()
}

fn find<'a>(n: &'a Node, id: &str) -> Option<&'a Node> {
    if n.id == id {
        return Some(n);
    }
    n.layers.iter().find_map(|l| find(l, id))
}

fn is_effect(n: &Node) -> bool {
    matches!(n.kind, "blur" | "glow" | "shadow" | "backdrop" | "grain" | "trail" | "smear" | "gradient")
}

//! Rostrum patch (E2): a paint plan by node, so a motion-blurred frame draws its still layers once. The caller (the
//! 2D engine's serve.rs) sets, per node: `Skip` (not drawn this paint) or `Cached(k)` (the backend's kept picture `k`
//! drawn in its place, `PaintScene::draw_cached`). An empty plan draws everything, as without the patch.

use std::cell::RefCell;
use std::collections::HashMap;

use blitz_dom::NodeId;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Run {
    Skip,
    Cached(usize),
}

thread_local! {
    static PLAN: RefCell<HashMap<NodeId, Run>> = RefCell::new(HashMap::new());
}

/// The plan the next paints on this thread follow (empty: draw everything).
pub fn set_plan(plan: HashMap<NodeId, Run>) {
    PLAN.with(|p| *p.borrow_mut() = plan);
}

pub(crate) fn planned(node: NodeId) -> Option<Run> {
    PLAN.with(|p| {
        let p = p.borrow();
        if p.is_empty() { None } else { p.get(&node).copied() }
    })
}

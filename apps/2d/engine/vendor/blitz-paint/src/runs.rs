//! Rostrum patch (E2): a paint plan by node, so a motion-blurred frame draws its still layers once. The caller (the
//! 2D engine's serve.rs) sets, per node: `Skip` (not drawn this paint) or `Cached(k)` (the backend's kept picture `k`
//! drawn in its place, `PaintScene::draw_cached`). An empty plan draws everything, as without the patch.

use std::cell::RefCell;
use std::collections::HashMap;

use blitz_dom::NodeId;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Run {
    Skip,
    Cached(usize),
    /// Rostrum patch (motion-blur buckets): kept picture `k` moved by an affine in device px (CSS `matrix()` order),
    /// for a layer that only moved since it was kept (`PaintScene::draw_cached_moved`).
    Moved(usize, [f64; 6]),
    /// Rostrum patch (streak blur): kept picture `k` averaged over streak `s`'s moves (`set_streaks`), one draw for a
    /// layer that only moved through the shutter (`PaintScene::draw_cached_streak`).
    Streak(usize, usize),
    /// Rostrum patch (streak blur, round 5): kept picture `k` averaged over each of the `n` streaks from `s` on, one draw
    /// each, every streak over its own part of the picture: a group whose children each move their own way.
    Streaks(usize, usize, usize),
    /// Rostrum patch (streak blur): the node painted as it is laid out, moved by an affine in page px (CSS `matrix()`
    /// order): a layer that only moved but blends with what is under it, drawn at each sub-frame without a new layout.
    Shift([f64; 6]),
    /// Rostrum patch (streak blur, one paint): the node painted into picture `k` of this paint instead of the canvas
    /// (`PaintScene::begin_kept`), so one paint makes every picture a step's streaks read.
    Keep(usize),
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

/// Rostrum patch (streak blur): one streak `Run::Streak` names: 1..=128 moves as `Run::Moved`'s, drawn only over
/// `rect` (x0, y0, x1, y1 in device px: the area the picture sweeps) when given, else over the whole canvas.
#[derive(Clone, Debug, Default)]
pub struct Streak {
    pub moves: Vec<[f64; 6]>,
    pub rect: Option<[f32; 4]>,
}

thread_local! {
    static STREAKS: RefCell<Vec<Streak>> = const { RefCell::new(Vec::new()) };
}

/// Rostrum patch (streak blur): the streaks `Run::Streak` names on this thread.
pub fn set_streaks(streaks: Vec<Streak>) {
    STREAKS.with(|s| *s.borrow_mut() = streaks);
}

/// Streak `s` (no moves when it is not set: the caller then draws as usual).
pub(crate) fn streak(s: usize) -> Streak {
    STREAKS.with(|v| v.borrow().get(s).cloned().unwrap_or_default())
}

thread_local! {
    static VIEWPORT: RefCell<Option<kurbo::Rect>> = const { RefCell::new(None) };
}

/// Rostrum patch (camera F3): the page px rectangle the next paints on this thread draw, culling what lies wholly
/// outside it (None: the page's own width × height from its top-left, as without the patch). The 2D engine's world
/// picture shows any part of the endless canvas, left of or above the page's origin too.
pub fn set_viewport(rect: Option<kurbo::Rect>) {
    VIEWPORT.with(|v| *v.borrow_mut() = rect);
}

/// The rectangle `set_viewport` set on this thread (None: the page's own).
pub fn viewport() -> Option<kurbo::Rect> {
    VIEWPORT.with(|v| *v.borrow())
}

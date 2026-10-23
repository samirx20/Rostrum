//! Rostrum patch (E3): a layer's glows drawn from its own picture. The 2D stage marks an element with
//! `data-glow="radius strength;…"` (CSS px; 0–1) where each glow used to be a second, blurred copy of the same markup
//! drawn behind it with `plus-lighter`. The element's content is drawn once into an image; each glow is that image
//! blurred, at its strength, added; then the image itself is laid on with the element's own filter, opacity and blend
//! (anyrender `push_glow_layer`). The same picture as the copies, without laying out and drawing the content twice.
//!
//! The content is laid on as one picture, which equals drawing it piece by piece only when every piece composites
//! normally into it. A blend inside it reaching the element (`blend::blends_inside`), a backend without the hook, or a
//! layer it can't capture: each glow is drawn as its own blurred layer of the content, as the copies were.

use std::sync::Arc;

use anyrender::filters::{Filter, FilterEffect};
use peniko::{BlendMode, Compose, Mix};

use crate::particles::data_attr;

/// The element's glows as (filter, strength), in drawing order; empty when it has none.
pub(crate) fn of(node: &blitz_dom::Node) -> Vec<(Arc<Filter>, f32)> {
    let Some(data) = data_attr(node, "data-glow") else { return vec![] };
    data.split(';')
        .filter_map(|g| {
            let mut n = g.split_ascii_whitespace().filter_map(|v| v.parse::<f32>().ok());
            let (radius, strength) = (n.next()?, n.next()?);
            Some((Arc::new(Filter::linear_list([FilterEffect::blur(radius)].into_iter())), strength))
        })
        .collect()
}

pub(crate) fn marked(node: &blitz_dom::Node) -> bool {
    data_attr(node, "data-glow").is_some()
}

/// How a glow adds onto what is behind it (CSS `plus-lighter`).
pub(crate) fn plus() -> BlendMode {
    BlendMode::new(Mix::Normal, Compose::Plus)
}

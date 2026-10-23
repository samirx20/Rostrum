use anyrender::{Filter, PaintScene};
use kurbo::{Affine, Shape};
use peniko::{BlendMode, Fill, Mix};
use std::{cell::Cell, sync::Arc};

#[derive(Default)]
pub(crate) struct LayerManager {
    layers_used: Cell<u32>,
    layer_depth: Cell<u32>,
    layers_wanted: Cell<u32>,

    #[allow(unused)] // Only used for debugging. Enabled as required.
    layer_depth_used: Cell<u32>,
}

impl LayerManager {
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn maybe_with_layer<S: PaintScene, F: FnOnce(&mut S)>(
        &self,
        scene: &mut S,
        condition: bool,
        opacity: f32,
        transform: Affine,
        shape: &impl Shape,
        filter: Option<Arc<Filter>>,
        backdrop_filter: Option<Arc<Filter>>,
        paint_layer: F,
    ) {
        self.maybe_with_blend_layer(scene, condition, opacity, None, transform, shape, filter, backdrop_filter, paint_layer)
    }

    /// maybe_with_layer as a group composited with a blend mode (Rostrum patch: CSS mix-blend-mode and
    /// isolation, blend.rs). `Some(blend)` always makes a real layer, even at full opacity with no filter.
    #[allow(clippy::too_many_arguments)]
    pub(crate) fn maybe_with_blend_layer<S: PaintScene, F: FnOnce(&mut S)>(
        &self,
        scene: &mut S,
        condition: bool,
        opacity: f32,
        blend: Option<BlendMode>,
        transform: Affine,
        shape: &impl Shape,
        filter: Option<Arc<Filter>>,
        backdrop_filter: Option<Arc<Filter>>,
        paint_layer: F,
    ) {
        let layer_used = self.maybe_push_blend_layer(
            scene,
            condition,
            opacity,
            blend,
            transform,
            shape,
            filter,
            backdrop_filter,
        );
        paint_layer(scene);
        self.maybe_pop_layer(scene, layer_used);
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn maybe_push_layer(
        &self,
        scene: &mut impl PaintScene,
        condition: bool,
        opacity: f32,
        transform: Affine,
        shape: &impl Shape,
        filter: Option<Arc<Filter>>,
        backdrop_filter: Option<Arc<Filter>>,
    ) -> bool {
        self.maybe_push_blend_layer(scene, condition, opacity, None, transform, shape, filter, backdrop_filter)
    }

    #[allow(clippy::too_many_arguments)]
    pub(crate) fn maybe_push_blend_layer(
        &self,
        scene: &mut impl PaintScene,
        condition: bool,
        opacity: f32,
        blend: Option<BlendMode>,
        transform: Affine,
        shape: &impl Shape,
        filter: Option<Arc<Filter>>,
        backdrop_filter: Option<Arc<Filter>>,
    ) -> bool {
        if !condition {
            return false;
        }
        self.layers_wanted.update(|x| x + 1);

        // Rostrum patch (H41): no layer cap. Upstream refused every layer after the 1024th of a frame (a Vello
        // budget) and drew on without it, so in a busy frame the late layers silently lost their blend, opacity,
        // filter or clip: a multiply vignette drawn last came out as a plain white oval over the whole film. Skia
        // costs memory per *open* layer (the depth), not per layer used, so every wanted layer is pushed.

        // Actually push the layer. A blended or isolated group is a real layer even at full opacity:
        // its content composites onto the backdrop as one.
        if opacity == 1.0 && filter.is_none() && backdrop_filter.is_none() && blend.is_none() {
            scene.push_clip_layer(Fill::NonZero, transform, shape);
        } else {
            scene.push_layer(
                Fill::NonZero,
                blend.unwrap_or(Mix::Normal.into()),
                opacity,
                transform,
                shape,
                filter,
                backdrop_filter,
            );
        };

        // Update accounting
        self.layers_used.update(|x| x + 1);
        self.layer_depth.update(|x| x + 1);
        self.layer_depth.update(|x| x.max(self.layer_depth.get()));

        true
    }

    pub(crate) fn maybe_pop_layer(&self, scene: &mut impl PaintScene, condition: bool) {
        if condition {
            scene.pop_layer();
            self.layer_depth.update(|x| x - 1);
        }
    }
}


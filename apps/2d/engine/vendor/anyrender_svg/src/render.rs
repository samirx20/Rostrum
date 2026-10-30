// Copyright 2024 the Vello Authors
// SPDX-License-Identifier: Apache-2.0 OR MIT

use crate::util;
use anyrender::PaintScene;
use anyrender::filters::color_transformation::ColorMatrix;
use anyrender::filters::{Filter, FilterEffect};
use kurbo::{Affine, BezPath, Rect};
use peniko::{BlendMode, Color, Compose, Fill, Mix};
use std::sync::Arc;
use usvg::{Node, Path};

/// Rostrum patch (2D SVG masks): everywhere, for the layers a mask or clip is drawn into (a `DestIn` layer
/// clipped smaller would leave the content outside its clip untouched).
const EVERYWHERE: Rect = Rect::new(-1e7, -1e7, 1e7, 1e7);
/// Just below 1, so a backend can't fold an isolation layer into a plain clip (blitz-paint render/mask.rs).
const ALMOST_OPAQUE: f32 = 1.0 - f32::EPSILON;
/// SVG's luminanceToAlpha (Filter Effects § feColorMatrix), as blitz-paint's track mattes use it.
const LUMINANCE_TO_ALPHA: [f32; 20] = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.2125, 0.7154, 0.0721, 0.0, 0.0];

pub(crate) fn render_group<S: PaintScene, F: FnMut(&mut S, &usvg::Node)>(
    scene: &mut S,
    group: &usvg::Group,
    transform: Affine,
    global_transform: Affine,
    error_handler: &mut F,
) {
    render_group_as(scene, group, transform, global_transform, error_handler, false);
}

/// `as_clip` (Rostrum patch): the group is a `<clipPath>`'s content, drawn as coverage only: every visible shape
/// filled opaque black by its clip-rule (usvg puts it in the fill), no strokes, images, opacity or blending
/// (CSS Masking § The clipPath element). Clips on shapes inside the clip still apply.
fn render_group_as<S: PaintScene, F: FnMut(&mut S, &usvg::Node)>(
    scene: &mut S,
    group: &usvg::Group,
    transform: Affine,
    global_transform: Affine,
    error_handler: &mut F,
    as_clip: bool,
) {
    for node in group.children() {
        let transform = transform * util::to_affine(&node.abs_transform());
        match node {
            usvg::Node::Group(g) => {
                let alpha = if as_clip { 1.0 } else { g.opacity().get() };
                let is_fully_opaque = alpha >= 1.0;
                let mix = if as_clip { Mix::Normal } else { util::to_mix(g.blend_mode()) };
                // Where the group's own user space lands on the canvas: clips and masks are in it.
                let ts = global_transform * transform;

                // Rostrum patch (2D SVG masks): a clip path of one plain path (no clip of its own) is the layer's
                // clip shape, under the clip's own transform (upstream left that out). Any other clip path (several
                // shapes, text, a clip on the clip) and every mask are drawn after the content into a `DestIn`
                // layer (`apply_clip`, `apply_mask`); upstream drew masks not at all and other clips not at all.
                let simple_clip = g.clip_path().filter(|c| c.clip_path().is_none()).and_then(|c| match c.root().children() {
                    [usvg::Node::Path(p)] if p.is_visible() && p.fill().is_some() => Some((c, p.as_ref())),
                    _ => None,
                });
                let drawn_clip = g.clip_path().filter(|_| simple_clip.is_none());
                let mask = if as_clip { None } else { g.mask() };
                let blend = BlendMode { mix, compose: Compose::SrcOver };
                let layer_alpha = if (drawn_clip.is_some() || mask.is_some()) && is_fully_opaque { ALMOST_OPAQUE } else { alpha };

                #[allow(deprecated)]
                let did_push_layer = if let Some((clip, clip_path)) = simple_clip {
                    let local_path = util::to_bez_path(clip_path);
                    scene.push_layer(
                        match clip_path.fill().map(|fill| fill.rule()) {
                            Some(usvg::FillRule::EvenOdd) => Fill::EvenOdd,
                            _ => Fill::NonZero,
                        },
                        blend,
                        layer_alpha,
                        ts * util::to_affine(&clip.transform()),
                        &local_path,
                        None,
                        None,
                    );
                    true
                } else if drawn_clip.is_some() || mask.is_some() || mix != Mix::Normal || !is_fully_opaque {
                    // Use the layer bounding box as the clip path. It is in the group's
                    // content coordinate space, so map it to canvas space and outset it
                    // by 2px on each side (like resvg) so anti-aliased pixels at the
                    // layer edge aren't clipped.
                    let bounding_box = g.layer_bounding_box();
                    let rect = kurbo::Rect::from_origin_size(
                        (bounding_box.x() as f64, bounding_box.y() as f64),
                        (bounding_box.width() as f64, bounding_box.height() as f64),
                    );
                    let rect = ts.transform_rect_bbox(rect).inflate(2.0, 2.0);
                    scene.push_layer(Fill::NonZero, blend, layer_alpha, Affine::IDENTITY, &rect, None, None);
                    true
                } else {
                    // Else if there is no clip, mask or blending then don't push a layer
                    false
                };

                render_group_as(scene, g, Affine::IDENTITY, global_transform, error_handler, as_clip);

                if let Some(clip) = drawn_clip {
                    apply_clip(scene, clip, ts, error_handler);
                }
                if let Some(mask) = mask {
                    apply_mask(scene, mask, ts, error_handler);
                }
                if did_push_layer {
                    scene.pop_layer();
                }
            }
            usvg::Node::Path(path) => {
                if !path.is_visible() {
                    continue;
                }
                let local_path = util::to_bez_path(path);

                let transform = global_transform * transform;
                if as_clip {
                    if let Some(fill) = path.fill() {
                        let rule = match fill.rule() {
                            usvg::FillRule::NonZero => Fill::NonZero,
                            usvg::FillRule::EvenOdd => Fill::EvenOdd,
                        };
                        scene.fill(rule, transform, Color::BLACK, None, &local_path);
                    }
                    continue;
                }
                match path.paint_order() {
                    usvg::PaintOrder::FillAndStroke => {
                        fill(scene, error_handler, path, transform, &local_path, node);
                        stroke(scene, error_handler, path, transform, &local_path, node);
                    }
                    usvg::PaintOrder::StrokeAndFill => {
                        stroke(scene, error_handler, path, transform, &local_path, node);
                        fill(scene, error_handler, path, transform, &local_path, node);
                    }
                }
            }
            usvg::Node::Image(img) => {
                if as_clip || !img.is_visible() {
                    continue;
                }
                match img.kind() {
                    usvg::ImageKind::JPEG(_)
                    | usvg::ImageKind::PNG(_)
                    | usvg::ImageKind::GIF(_)
                    | usvg::ImageKind::WEBP(_) => {
                        #[cfg(feature = "image")]
                        {
                            let Ok(decoded_image) = util::decode_raw_raster_image(img.kind())
                            else {
                                error_handler(scene, node);
                                continue;
                            };
                            let image = util::into_image(decoded_image, img.rendering_mode());
                            let image_ts = global_transform * util::to_affine(&img.abs_transform());
                            scene.draw_image(image.as_ref(), image_ts);
                        }

                        #[cfg(not(feature = "image"))]
                        {
                            error_handler(scene, node);
                            continue;
                        }
                    }
                    usvg::ImageKind::SVG(svg) => {
                        render_group_as(
                            scene,
                            svg.root(),
                            transform,
                            global_transform,
                            error_handler,
                            as_clip,
                        );
                    }
                }
            }
            usvg::Node::Text(text) => {
                // The children of the flattened text group already carry the
                // text node's absolute transform, so recurse with the identity
                // transform (like the group case) to avoid applying it twice.
                render_group_as(
                    scene,
                    text.flattened(),
                    Affine::IDENTITY,
                    global_transform,
                    error_handler,
                    as_clip,
                );
            }
        }
    }
}

/// Rostrum patch (2D SVG masks): keeps what is drawn so far (the group's isolation layer) only where `clip`
/// covers: its shapes drawn as coverage into a `DestIn` layer at `ts` (the clipped group's user space) times the
/// clip's own transform (clipPathUnits="objectBoundingBox" is folded into it by usvg). A clip-path on the
/// `<clipPath>` itself narrows it further (at `ts`, as resvg does).
fn apply_clip<S: PaintScene, F: FnMut(&mut S, &usvg::Node)>(scene: &mut S, clip: &usvg::ClipPath, ts: Affine, error_handler: &mut F) {
    scene.push_layer(Fill::NonZero, BlendMode::new(Mix::Normal, Compose::DestIn), 1.0, Affine::IDENTITY, &EVERYWHERE, None, None);
    let inner = clip.clip_path();
    if inner.is_some() {
        scene.push_layer(Fill::NonZero, Mix::Normal, ALMOST_OPAQUE, Affine::IDENTITY, &EVERYWHERE, None, None);
    }
    render_group_as(scene, clip.root(), Affine::IDENTITY, ts * util::to_affine(&clip.transform()), error_handler, true);
    if let Some(inner) = inner {
        apply_clip(scene, inner, ts, error_handler);
        scene.pop_layer();
    }
    scene.pop_layer();
}

/// Rostrum patch (2D SVG masks): keeps what is drawn so far where `mask` lets it through: the mask's content, cut
/// to its region (`rect`, already in the group's user space; maskContentUnits="objectBoundingBox" is a transform
/// on its content), drawn into a `DestIn` layer. A luminance mask (the default) draws its content over opaque black
/// and the layer turns luminance into alpha, so what the mask leaves transparent reads as black and a half
/// transparent white lets half through, as in browsers.
fn apply_mask<S: PaintScene, F: FnMut(&mut S, &usvg::Node)>(scene: &mut S, mask: &usvg::Mask, ts: Affine, error_handler: &mut F) {
    let luminance = mask.kind() == usvg::MaskType::Luminance;
    let filter = luminance.then(|| Arc::new(Filter::single(FilterEffect::ColorMatrix(ColorMatrix(LUMINANCE_TO_ALPHA)))));
    scene.push_layer(Fill::NonZero, BlendMode::new(Mix::Normal, Compose::DestIn), 1.0, Affine::IDENTITY, &EVERYWHERE, filter, None);
    let r = mask.rect();
    let region = Rect::new(r.left() as f64, r.top() as f64, r.right() as f64, r.bottom() as f64);
    scene.push_clip_layer(Fill::NonZero, ts, &region);
    if luminance {
        scene.fill(Fill::NonZero, ts, Color::BLACK, None, &region);
    }
    // A `mask` on the `<mask>` itself (`mask.mask()`) is left out, as Chromium does (resvg applies it).
    render_group_as(scene, mask.root(), Affine::IDENTITY, ts, error_handler, false);
    scene.pop_layer();
    scene.pop_layer();
}

fn fill<S: PaintScene, F: FnMut(&mut S, &usvg::Node)>(
    scene: &mut S,
    error_handler: &mut F,
    path: &Path,
    transform: Affine,
    local_path: &BezPath,
    node: &Node,
) {
    if let Some(fill) = &path.fill() {
        if let Some((paint, brush_transform)) = util::to_brush(fill.paint(), fill.opacity()) {
            scene.fill(
                match fill.rule() {
                    usvg::FillRule::NonZero => Fill::NonZero,
                    usvg::FillRule::EvenOdd => Fill::EvenOdd,
                },
                transform,
                paint.as_ref(),
                Some(brush_transform),
                local_path,
            );
        } else {
            error_handler(scene, node);
        }
    }
}

fn stroke<S: PaintScene, F: FnMut(&mut S, &usvg::Node)>(
    scene: &mut S,
    error_handler: &mut F,
    path: &Path,
    transform: Affine,
    local_path: &BezPath,
    node: &Node,
) {
    if let Some(stroke) = &path.stroke() {
        if let Some((paint, brush_transform)) = util::to_brush(stroke.paint(), stroke.opacity()) {
            let conv_stroke = util::to_stroke(stroke);
            scene.stroke(
                &conv_stroke,
                transform,
                paint.as_ref(),
                Some(brush_transform),
                local_path,
            );
        } else {
            error_handler(scene, node);
        }
    }
}

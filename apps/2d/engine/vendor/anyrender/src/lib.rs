//! 2D drawing abstraction that allows applications/frameworks to support many rendering backends through
//! a unified API.
//!
//! ### Painting a scene
//!
//! The core abstraction in AnyRender is the [`PaintScene`] trait.
//!
//! [`PaintScene`] is a "sink" which accepts drawing commands:
//!
//!   - Applications and libraries draw by pushing commands into a [`PaintScene`]
//!   - Backends execute those commands to produce an output
//!
//! ### Rendering to surface or buffer
//!
//! In addition to PaintScene, there is:
//!
//!   - The [`ImageRenderer`] trait which provides an abstraction for rendering to a `Vec<u8>` RGBA8 buffer.
//!   - The [`WindowRenderer`] trait which provides an abstraction for rendering to a surface/window
//!
//! ### SVG
//!
//! The [anyrender_svg](https://docs.rs/anyrender_svg) crate allows SVGs to be rendered using AnyRender
//!
//! ### WASM support
//!
//! Wgpu adapter/device/surface initialization is fundamentally async on the web. To avoid
//! deadlocking the JS event loop, [`WindowRenderer::resume`] takes an `on_ready` callback:
//! GPU backends spawn the init on `wasm_bindgen_futures::spawn_local` and invoke the callback
//! once the surface is live. The embedder then calls [`WindowRenderer::complete_resume`] to
//! transition the renderer to the active state. On native targets the same code path runs
//! inline (`pollster::block_on` on the GPU backends), so callers see no behavioural difference.
//!
//! ### Backends
//!
//! Currently existing backends are:
//!
//! - [anyrender_vello_hybrid](https://docs.rs/anyrender_vello_hybrid) which draws using [vello_hybrid](https://docs.rs/vello_hybrid)
//! - [anyrender_vello_cpu](https://docs.rs/anyrender_vello_cpu) which draws using [vello_cpu](https://docs.rs/vello_cpu)
//! - [anyrender_vello](https://docs.rs/anyrender_vello) which draws using [vello](https://docs.rs/vello)
//! - [anyrender_skia](https://crates.io/crates/anyrender_skia) which draws using Skia (via the [skia-safe](https://github.com/rust-skia/rust-skia) crate)

#![allow(clippy::collapsible_if)]

use kurbo::{Affine, Rect, Shape, Stroke};
use peniko::{BlendMode, Color, Fill, FontData, ImageBrushRef, StyleRef};
use recording::RenderCommand;
use std::{any::Any, sync::Arc};

pub mod filters;
pub use filters::Filter;
pub mod wasm_send_sync;
pub use wasm_send_sync::*;
pub mod types;
pub use types::*;
mod null_backend;
pub use null_backend::*;
pub mod recording;
pub use recording::Scene;

mod resource_id;
pub use resource_id::ResourceId;

#[cfg(feature = "serde")]
mod svg_path_parser;

#[derive(Debug, Copy, Clone, Eq, PartialEq)]
pub enum RegisterResourceErrorKind {
    /// The `RenderContext` you tried to register the resource with does not support the kind of resource
    UnsupportedResourceKind,
    /// Some other kind of error occured
    Other,
    /// This backend has not implemented resource registration
    Unimplemented,
    /// The `RenderContext` you tried to register the resource is not currently active
    NotActive,
}

#[derive(Debug, Clone)]
pub struct RegisterResourceError {
    /// The kind of error that occurred when registering the resource
    pub kind: RegisterResourceErrorKind,
    /// An optional detailed error message
    pub message: Option<String>,
}

impl From<RegisterResourceErrorKind> for RegisterResourceError {
    fn from(kind: RegisterResourceErrorKind) -> Self {
        Self {
            kind,
            message: None,
        }
    }
}

pub trait RenderContext {
    fn try_register_custom_resource(
        &mut self,
        resource: Box<dyn Any>,
    ) -> Result<ResourceId, RegisterResourceError> {
        let _ = resource;
        Err(RegisterResourceErrorKind::Unimplemented.into())
    }
    fn unregister_resource(&mut self, resource_id: ResourceId) {
        let _ = resource_id;
    }

    /// Return a type-erased context type that is passed to custom widgets
    /// in order to enable them to render renderer-specific content
    fn renderer_specific_context(&self) -> Option<Box<dyn Any>> {
        None
    }
}

/// Abstraction for rendering a scene to a window
pub trait WindowRenderer: RenderContext {
    type ScenePainter<'a>: PaintScene
    where
        Self: 'a;

    /// Begin resuming the renderer. `on_ready` fires when initialization completes —
    /// synchronously inside `resume` on native, asynchronously (via
    /// `wasm_bindgen_futures::spawn_local`) on `wasm32-unknown-unknown`. After it
    /// fires, the embedder must call [`complete_resume`](Self::complete_resume) to
    /// transition the renderer to the active state.
    fn resume<F: FnOnce() + 'static>(
        &mut self,
        window: Arc<dyn WindowHandle>,
        width: u32,
        height: u32,
        on_ready: F,
    );

    /// Finalize a previously-initiated resume. Returns `true` once the renderer is
    /// active and ready to render. Idempotent on already-active renderers; returns
    /// `false` if a pending init has not yet produced a result.
    ///
    /// Backends whose `resume` finishes synchronously inline should return `true`
    /// directly. There is intentionally no default: forgetting to override this on
    /// an async-init backend would silently no-op rendering.
    fn complete_resume(&mut self) -> bool;

    fn suspend(&mut self);
    fn is_active(&self) -> bool;

    /// Returns `true` while an asynchronous resume is in flight (after `resume`
    /// but before `complete_resume` has succeeded). Defaults to `false` for
    /// backends with synchronous initialization.
    fn is_pending(&self) -> bool {
        false
    }
    fn set_size(&mut self, width: u32, height: u32);
    fn render<F: FnOnce(&mut Self::ScenePainter<'_>)>(&mut self, draw_fn: F);
}

/// Abstraction for rendering a scene to an image buffer
pub trait ImageRenderer: RenderContext {
    type ScenePainter<'a>: PaintScene
    where
        Self: 'a;
    fn new(width: u32, height: u32) -> Self;
    fn resize(&mut self, width: u32, height: u32);
    fn reset(&mut self);
    fn render_to_vec<F: FnOnce(&mut Self::ScenePainter<'_>)>(
        &mut self,
        draw_fn: F,
        vec: &mut Vec<u8>,
    );
    fn render<F: FnOnce(&mut Self::ScenePainter<'_>)>(&mut self, draw_fn: F, buffer: &mut [u8]);
}

/// Draw a scene to a buffer using an `ImageRenderer`
pub fn render_to_buffer<R: ImageRenderer, F: FnOnce(&mut R::ScenePainter<'_>)>(
    draw_fn: F,
    width: u32,
    height: u32,
) -> Vec<u8> {
    let mut buf = Vec::with_capacity((width * height * 4) as usize);
    let mut renderer = R::new(width, height);
    renderer.render_to_vec(draw_fn, &mut buf);

    buf
}

/// Rostrum patch (round 8, free triangles in round 13): a raster warp — a triangle mesh whose vertex i shows the
/// picture of `rest` (element px) at `uvs[i]` (element px, inside `rest`) and lands at `points[i]` (element px);
/// `tris` are corner indices, three per triangle. A regular grid is one such mesh (`WarpMesh::grid`);
/// a skinned character's mesh is another (free vertices). `transform` maps element px to the scene.
#[derive(Clone, Debug, PartialEq)]
pub struct WarpMesh {
    pub transform: Affine,
    pub rest: Rect,
    pub points: Vec<kurbo::Point>,
    pub uvs: Vec<kurbo::Point>,
    pub tris: Vec<u32>,
}

impl WarpMesh {
    /// A regular `cols` × `rows` grid over `rest` whose points (row by row) land at `points`.
    pub fn grid(transform: Affine, rest: Rect, cols: usize, rows: usize, points: Vec<kurbo::Point>) -> Self {
        let mut uvs = Vec::with_capacity(points.len());
        for j in 0..=rows {
            for i in 0..=cols {
                uvs.push(kurbo::Point::new(rest.x0 + i as f64 / cols as f64 * rest.width(), rest.y0 + j as f64 / rows as f64 * rest.height()));
            }
        }
        let mut tris = Vec::with_capacity(cols * rows * 6);
        for j in 0..rows {
            for i in 0..cols {
                let a = (j * (cols + 1) + i) as u32;
                let (b, c) = (a + 1, a + (cols + 1) as u32);
                tris.extend_from_slice(&[a, b, c + 1, a, c + 1, c]);
            }
        }
        WarpMesh { transform, rest, points, uvs, tris }
    }

    /// Whether the mesh is well formed: one uv per point, whole triangles, every index in range.
    pub fn is_valid(&self) -> bool {
        self.uvs.len() == self.points.len() && !self.tris.is_empty() && self.tris.len() % 3 == 0 && self.tris.iter().all(|&i| (i as usize) < self.points.len()) && self.points.len() <= u16::MAX as usize
    }
}

/// Rostrum patch (round 8): one stamp of a sprite — `transform` maps sprite px (around its centre) to the
/// scene, `color` is the tint (rgb, white = none) and opacity (a) multiplied into the sprite.
#[derive(Clone, Copy, Debug)]
pub struct SpriteInstance {
    pub transform: Affine,
    pub color: [f32; 4],
}

/// Abstraction for drawing a 2D scene
pub trait PaintScene: RenderContext {
    /// Removes all content from the scene
    fn reset(&mut self);

    /// Pushes a new layer clipped by the specified shape and composed with previous layers using the specified blend mode.
    /// The fill rule determines which parts of the clip shape are inside the clipping region.
    /// Every drawing command after this call will be clipped by the shape until the layer is popped.
    /// However, the transforms are not saved or modified by the layer stack.
    #[allow(clippy::too_many_arguments)]
    fn push_layer(
        &mut self,
        fill: Fill,
        blend: impl Into<BlendMode>,
        alpha: f32,
        transform: Affine,
        clip: &impl Shape,
        filter: Option<Arc<Filter>>,
        backdrop_filter: Option<Arc<Filter>>,
    );

    /// Pushes a new clip layer clipped by the specified shape.
    /// The fill rule determines which parts of the clip shape are inside the clipping region.
    /// Every drawing command after this call will be clipped by the shape until the layer is popped.
    /// However, the transforms are not saved or modified by the layer stack.
    fn push_clip_layer(&mut self, fill: Fill, transform: Affine, clip: &impl Shape);

    /// Pops the current layer.
    fn pop_layer(&mut self);

    /// Rostrum proof patch: map every following draw by `m` (row-major 4x4 for column vectors, applied
    /// before each draw's own affine) until the matching pop. Backends without 3D ignore it.
    fn push_transform_3d(&mut self, _m: [f64; 16]) {}
    fn pop_transform_3d(&mut self) {}

    /// Rostrum patch (round 8): a sprite (`content`, recorded in this scene's space; `to_sprite` maps that space to
    /// sprite px, `bounds` is what it covers there) stamped once per instance. The default replays the vectors
    /// per instance with the colour multiplied in; GPU backends draw all stamps as one textured mesh.
    fn draw_instances(&mut self, content: &Scene, to_sprite: Affine, _bounds: Rect, instances: &[SpriteInstance])
    where
        Self: Sized,
    {
        for inst in instances {
            recording::replay_tinted(self, content, inst.transform * to_sprite, inst.color);
        }
    }

    /// Rostrum patch (round 8): `content` (recorded in this scene's space) drawn as an image on a warped mesh.
    /// Backends without meshes draw it unwarped.
    fn draw_warped(&mut self, content: &Scene, _mesh: &WarpMesh) {
        self.append_scene(content.clone(), Affine::IDENTITY);
    }

    /// Rostrum patch (round 10): the picture the backend holds (motion blur's summed sub-frames) drawn at device
    /// pixels, inside whatever layers are pushed; false when it holds none (the caller then draws as usual).
    fn draw_held(&mut self) -> bool {
        false
    }

    /// Rostrum patch (E2): the backend's kept picture `k` (a run of still layers drawn once for a motion-blurred
    /// frame) drawn at device pixels, inside whatever layers are pushed; false when it has none.
    fn draw_cached(&mut self, _k: usize) -> bool {
        false
    }

    /// Rostrum patch (motion-blur buckets): kept picture `k` moved by `m` (an affine in device px: a, b, c, d, e, f as
    /// CSS `matrix()`), its edges stretched past where it was drawn; false when it has none.
    fn draw_cached_moved(&mut self, _k: usize, _m: [f64; 6]) -> bool {
        false
    }

    /// Rostrum patch (streak blur): kept picture `k` averaged over `moves` (each as `draw_cached_moved`'s `m`, 1..=128
    /// of them) in one draw, the streak a layer leaves moving through the shutter, only over `rect` (x0, y0, x1, y1 in
    /// the canvas's device px) when given; false when it has none or can't.
    fn draw_cached_streak(&mut self, _k: usize, _moves: &[[f64; 6]], _rect: Option<[f32; 4]>) -> bool {
        false
    }

    /// Rostrum patch (E3): a layer whose content is captured as one picture, then drawn as each glow (the picture
    /// with the glow's filter, at its strength, added: `plus-lighter`, under the glow's clip), then as itself: in a
    /// layer with `alpha`, `blend` (normal when None) and `filter` under `clip`, or as it is when `clip` is None (no
    /// layer). Clips are in `transform`'s space. Popped with `pop_layer`. False when the backend can't (nothing is
    /// pushed; the caller draws each glow as its own layer of the content).
    #[allow(clippy::too_many_arguments)]
    fn push_glow_layer(
        &mut self,
        _glows: &[(Arc<Filter>, f32, Rect)],
        _alpha: f32,
        _blend: Option<BlendMode>,
        _transform: Affine,
        _clip: Option<Rect>,
        _filter: Option<Arc<Filter>>,
    ) -> bool {
        false
    }

    /// Strokes a shape using the specified style and brush.
    fn stroke<'a>(
        &mut self,
        style: &Stroke,
        transform: Affine,
        brush: impl Into<PaintRef<'a>>,
        brush_transform: Option<Affine>,
        shape: &impl Shape,
    );

    /// Fills a shape using the specified style and brush.
    fn fill<'a>(
        &mut self,
        style: Fill,
        transform: Affine,
        brush: impl Into<PaintRef<'a>>,
        brush_transform: Option<Affine>,
        shape: &impl Shape,
    );

    /// Draws a run of glyphs
    #[allow(clippy::too_many_arguments)]
    fn draw_glyphs<'a, 's: 'a>(
        &'s mut self,
        font: &'a FontData,
        font_size: f32,
        hint: bool,
        normalized_coords: &'a [NormalizedCoord],
        embolden: kurbo::Vec2,
        style: impl Into<StyleRef<'a>>,
        brush: impl Into<PaintRef<'a>>,
        brush_alpha: f32,
        transform: Affine,
        glyph_transform: Option<Affine>,
        glyphs: impl Iterator<Item = Glyph> + Clone,
    );

    /// Draw a rounded rectangle blurred with a gaussian filter.
    fn draw_box_shadow(
        &mut self,
        transform: Affine,
        rect: Rect,
        brush: Color,
        radius: f64,
        std_dev: f64,
    );

    // --- Provided methods

    /// Append a recorded Scene Fragment to the current scene
    fn append_scene(&mut self, scene: Scene, scene_transform: Affine) {
        for cmd in scene.commands {
            match cmd {
                RenderCommand::PushLayer(cmd) => self.push_layer(
                    cmd.fill,
                    cmd.blend,
                    cmd.alpha,
                    scene_transform * cmd.transform,
                    &cmd.clip,
                    cmd.filter,
                    cmd.backdrop_filter,
                ),
                RenderCommand::PushClipLayer(cmd) => {
                    self.push_clip_layer(cmd.fill, scene_transform * cmd.transform, &cmd.clip)
                }
                RenderCommand::PopLayer => self.pop_layer(),
                RenderCommand::Stroke(cmd) => self.stroke(
                    &cmd.style,
                    scene_transform * cmd.transform,
                    match cmd.brush {
                        Paint::Solid(alpha_color) => Paint::Solid(alpha_color),
                        Paint::Gradient(ref gradient) => Paint::Gradient(gradient),
                        Paint::Image(ref image) => Paint::Image(image.as_ref()),
                        Paint::Resource(id) => Paint::Resource(id),
                        Paint::Custom(ref custom) => Paint::Custom(custom.as_ref()),
                    },
                    cmd.brush_transform,
                    &cmd.shape,
                ),
                RenderCommand::Fill(cmd) => self.fill(
                    cmd.fill,
                    scene_transform * cmd.transform,
                    match cmd.brush {
                        Paint::Solid(alpha_color) => Paint::Solid(alpha_color),
                        Paint::Gradient(ref gradient) => Paint::Gradient(gradient),
                        Paint::Image(ref image) => Paint::Image(image.as_ref()),
                        Paint::Resource(id) => Paint::Resource(id),
                        Paint::Custom(ref custom) => Paint::Custom(custom.as_ref()),
                    },
                    cmd.brush_transform,
                    &cmd.shape,
                ),
                RenderCommand::GlyphRun(cmd) => self.draw_glyphs(
                    &cmd.font_data,
                    cmd.font_size,
                    cmd.hint,
                    &cmd.normalized_coords,
                    cmd.embolden,
                    &cmd.style,
                    match cmd.brush {
                        Paint::Solid(alpha_color) => Paint::Solid(alpha_color),
                        Paint::Gradient(ref gradient) => Paint::Gradient(gradient),
                        Paint::Image(ref image) => Paint::Image(image.as_ref()),
                        Paint::Resource(id) => Paint::Resource(id),
                        Paint::Custom(ref custom) => Paint::Custom(custom.as_ref()),
                    },
                    cmd.brush_alpha,
                    scene_transform * cmd.transform,
                    cmd.glyph_transform,
                    cmd.glyphs.into_iter(),
                ),
                RenderCommand::BoxShadow(cmd) => self.draw_box_shadow(
                    scene_transform * cmd.transform,
                    cmd.rect,
                    cmd.brush,
                    cmd.radius,
                    cmd.std_dev,
                ),
                // Rostrum patch (round 11): recorded warps and 3D transforms replay as themselves.
                cmd @ (RenderCommand::Warped(_) | RenderCommand::PushTransform3d(_) | RenderCommand::PopTransform3d) => {
                    recording::replay_structural(self, cmd, scene_transform)
                }
            }
        }
    }

    /// Utility method to draw an image at it's natural size. For more advanced image drawing use the `fill` method
    fn draw_image(&mut self, image: ImageBrushRef, transform: Affine) {
        self.fill(
            Fill::NonZero,
            transform,
            image,
            None,
            &Rect::new(
                0.0,
                0.0,
                image.image.width as f64,
                image.image.height as f64,
            ),
        );
    }
}

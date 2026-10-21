use std::sync::Arc;

use crate::{Filter, Glyph, NormalizedCoord, Paint, PaintRef, PaintScene, RenderContext};
use kurbo::{Affine, BezPath, Rect, Shape, Stroke};
use peniko::{BlendMode, Color, Fill, FontData, Style, StyleRef};

#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};

const DEFAULT_TOLERANCE: f64 = 0.1;

#[derive(Clone, Debug, PartialEq)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub enum RenderCommand<Font = FontData, Brush = Paint> {
    /// Pushes a new layer clipped by the specified shape and composed with previous layers using the specified blend mode.
    /// Every drawing command after this call will be clipped by the shape until the layer is popped.
    /// However, the transforms are not saved or modified by the layer stack.
    PushLayer(LayerCommand),
    /// Pushes a new clip layer clipped by the specified shape.
    /// Every drawing command after this call will be clipped by the shape until the layer is popped.
    /// However, the transforms are not saved or modified by the layer stack.
    PushClipLayer(ClipCommand),
    /// Pops the current layer.
    PopLayer,
    /// Strokes a shape using the specified style and brush.
    Stroke(StrokeCommand<Brush>),
    /// Fills a shape using the specified style and brush.
    Fill(FillCommand<Brush>),
    /// Draws a run of glyphs
    GlyphRun(GlyphRunCommand<Font, Brush>),
    /// Draw a rounded rectangle blurred with a gaussian filter.
    BoxShadow(BoxShadowCommand),
    /// Rostrum patch (round 11): a recording drawn on a warped mesh (`PaintScene::draw_warped`), kept as a
    /// command so a warp inside a recording (a warped element in a warped group, a warped sprite) still warps.
    #[cfg_attr(feature = "serde", serde(skip))]
    Warped(WarpedCommand),
    /// Rostrum patch (round 11): `PaintScene::push_transform_3d` / `pop_transform_3d`, recorded (a 3D tilt
    /// inside a recording was dropped).
    #[cfg_attr(feature = "serde", serde(skip))]
    PushTransform3d([f64; 16]),
    #[cfg_attr(feature = "serde", serde(skip))]
    PopTransform3d,
}

/// Rostrum patch (round 11): `content` (in the recording's space) drawn on `mesh`.
#[derive(Clone, Debug, PartialEq)]
pub struct WarpedCommand {
    pub content: Scene,
    pub mesh: crate::WarpMesh,
}

/// Rostrum patch (round 11): a 2D affine as a row-major 4×4 (for column vectors).
fn affine4(a: Affine) -> [f64; 16] {
    let [xx, yx, xy, yy, x0, y0] = a.as_coeffs();
    [xx, xy, 0.0, x0, yx, yy, 0.0, y0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
}

fn mul4(a: &[f64; 16], b: &[f64; 16]) -> [f64; 16] {
    let mut out = [0.0; 16];
    for r in 0..4 {
        for c in 0..4 {
            out[r * 4 + c] = (0..4).map(|k| a[r * 4 + k] * b[k * 4 + c]).sum();
        }
    }
    out
}

/// Rostrum patch (round 11): a 3D base matrix `m` recorded in a space that `transform` maps on: T · m · T⁻¹,
/// so that (T · m · T⁻¹) · (T · A) = T · (m · A) for every draw's affine A.
pub fn conjugate_3d(transform: Affine, m: &[f64; 16]) -> [f64; 16] {
    if transform == Affine::IDENTITY || transform.determinant().abs() < 1e-12 {
        return *m;
    }
    mul4(&mul4(&affine4(transform), m), &affine4(transform.inverse()))
}

impl RenderCommand {
    /// Apply the specific transform to the command
    fn apply_transform(mut self, transform: Affine) -> Self {
        match &mut self {
            RenderCommand::PushLayer(cmd) => cmd.transform = transform * cmd.transform,
            RenderCommand::PushClipLayer(cmd) => cmd.transform = transform * cmd.transform,
            RenderCommand::PopLayer => {}
            RenderCommand::Stroke(cmd) => cmd.transform = transform * cmd.transform,
            RenderCommand::Fill(cmd) => cmd.transform = transform * cmd.transform,
            RenderCommand::GlyphRun(cmd) => cmd.transform = transform * cmd.transform,
            RenderCommand::BoxShadow(cmd) => cmd.transform = transform * cmd.transform,
            RenderCommand::Warped(cmd) => {
                let content = std::mem::take(&mut cmd.content.commands);
                cmd.content.commands = content.into_iter().map(|c| c.apply_transform(transform)).collect();
                cmd.mesh.transform = transform * cmd.mesh.transform;
            }
            RenderCommand::PushTransform3d(m) => *m = conjugate_3d(transform, m),
            RenderCommand::PopTransform3d => {}
        };

        self
    }
}

/// Pushes a new layer clipped by the specified shape and composed with previous layers using the specified blend mode.
/// Every drawing command after this call will be clipped by the shape until the layer is popped.
/// However, the transforms are not saved or modified by the layer stack.
#[derive(Clone, Debug, PartialEq)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct LayerCommand {
    #[cfg_attr(feature = "serde", serde(default))]
    pub fill: Fill,
    pub blend: BlendMode,
    pub alpha: f32,
    pub transform: Affine,
    #[cfg_attr(feature = "serde", serde(with = "svg_path"))]
    pub clip: BezPath, // TODO: more shape options
    pub filter: Option<Arc<Filter>>,
    pub backdrop_filter: Option<Arc<Filter>>,
}

/// Pushes a new clip layer clipped by the specified shape.
/// Every drawing command after this call will be clipped by the shape until the layer is popped.
/// However, the transforms are not saved or modified by the layer stack.
#[derive(Clone, Debug, PartialEq)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct ClipCommand {
    #[cfg_attr(feature = "serde", serde(default))]
    pub fill: Fill,
    pub transform: Affine,
    #[cfg_attr(feature = "serde", serde(with = "svg_path"))]
    pub clip: BezPath, // TODO: more shape options
}

/// Strokes a shape using the specified style and brush.
#[derive(Clone, Debug, PartialEq)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct StrokeCommand<Brush = Paint> {
    pub style: Stroke,
    pub transform: Affine,
    pub brush: Brush, // TODO: review ownership to avoid cloning. Should brushes be a "resource"?
    pub brush_transform: Option<Affine>,
    #[cfg_attr(feature = "serde", serde(with = "svg_path"))]
    pub shape: BezPath, // TODO: more shape options
}

/// Fills a shape using the specified style and brush.
#[derive(Clone, Debug, PartialEq)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct FillCommand<Brush = Paint> {
    pub fill: Fill,
    pub transform: Affine,
    pub brush: Brush, // TODO: review ownership to avoid cloning. Should brushes be a "resource"?
    pub brush_transform: Option<Affine>,
    #[cfg_attr(feature = "serde", serde(with = "svg_path"))]
    pub shape: BezPath, // TODO: more shape options
}

/// Draws a run of glyphs
#[derive(Clone, Debug, PartialEq)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct GlyphRunCommand<Font = FontData, Brush = Paint> {
    pub font_data: Font,
    pub font_size: f32,
    pub hint: bool,
    pub normalized_coords: Vec<NormalizedCoord>,
    #[cfg_attr(feature = "serde", serde(default = "Default::default"))]
    pub embolden: kurbo::Vec2,
    pub style: Style,
    pub brush: Brush,
    pub brush_alpha: f32,
    pub transform: Affine,
    pub glyph_transform: Option<Affine>,
    pub glyphs: Vec<Glyph>,
}

/// Draw a box shadow around a box
#[derive(Clone, Debug, PartialEq)]
#[cfg_attr(feature = "serde", derive(Serialize, Deserialize))]
pub struct BoxShadowCommand {
    pub transform: Affine,
    pub rect: Rect,
    pub brush: Color,
    pub radius: f64,
    pub std_dev: f64,
}

/// A recording of a Scene or Scene Fragment stored as plain data types that can be stored
/// and passed around.
#[derive(Clone, Debug, PartialEq)]
pub struct Scene {
    pub tolerance: f64,
    pub commands: Vec<RenderCommand>,
}

impl Default for Scene {
    fn default() -> Self {
        Self {
            tolerance: DEFAULT_TOLERANCE,
            commands: Vec::new(),
        }
    }
}

impl Scene {
    /// Create a new empty
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_tolerance(tolerance: f64) -> Self {
        Self {
            tolerance,
            commands: Vec::new(),
        }
    }

    fn convert_paint(&mut self, paint_ref: PaintRef<'_>) -> Paint {
        match paint_ref {
            Paint::Solid(color) => Paint::Solid(color),
            Paint::Gradient(gradient) => Paint::Gradient(gradient.clone()),
            Paint::Image(image) => Paint::Image(image.to_owned()),
            // TODO: handle this somehow
            Paint::Resource(id) => Paint::Resource(id),
            Paint::Custom(_) => Paint::Solid(Color::TRANSPARENT),
        }
    }
}

impl RenderContext for Scene {}
impl PaintScene for Scene {
    fn reset(&mut self) {
        self.commands.clear()
    }

    fn push_layer(
        &mut self,
        fill: Fill,
        blend: impl Into<BlendMode>,
        alpha: f32,
        transform: Affine,
        clip: &impl Shape,
        filter: Option<Arc<Filter>>,
        backdrop_filter: Option<Arc<Filter>>,
    ) {
        let blend = blend.into();
        let clip = clip.into_path(self.tolerance);
        let layer = LayerCommand {
            fill,
            blend,
            alpha,
            transform,
            clip,
            filter,
            backdrop_filter,
        };
        self.commands.push(RenderCommand::PushLayer(layer));
    }

    fn push_clip_layer(&mut self, fill: Fill, transform: Affine, clip: &impl Shape) {
        let clip = clip.into_path(self.tolerance);
        let layer = ClipCommand {
            fill,
            transform,
            clip,
        };
        self.commands.push(RenderCommand::PushClipLayer(layer));
    }

    fn pop_layer(&mut self) {
        self.commands.push(RenderCommand::PopLayer);
    }

    fn stroke<'a>(
        &mut self,
        style: &Stroke,
        transform: Affine,
        paint_ref: impl Into<PaintRef<'a>>,
        brush_transform: Option<Affine>,
        shape: &impl Shape,
    ) {
        let shape = shape.into_path(self.tolerance);
        let brush = self.convert_paint(paint_ref.into());
        let stroke = StrokeCommand {
            style: style.clone(),
            transform,
            brush,
            brush_transform,
            shape,
        };
        self.commands.push(RenderCommand::Stroke(stroke));
    }

    fn fill<'a>(
        &mut self,
        style: Fill,
        transform: Affine,
        paint: impl Into<PaintRef<'a>>,
        brush_transform: Option<Affine>,
        shape: &impl Shape,
    ) {
        let shape = shape.into_path(self.tolerance);
        let brush = self.convert_paint(paint.into());
        let fill = FillCommand {
            fill: style,
            transform,
            brush,
            brush_transform,
            shape,
        };
        self.commands.push(RenderCommand::Fill(fill));
    }

    fn draw_glyphs<'a, 's: 'a>(
        &'a mut self,
        font: &'a FontData,
        font_size: f32,
        hint: bool,
        normalized_coords: &'a [NormalizedCoord],
        embolden: kurbo::Vec2,
        style: impl Into<StyleRef<'a>>,
        paint_ref: impl Into<PaintRef<'a>>,
        brush_alpha: f32,
        transform: Affine,
        glyph_transform: Option<Affine>,
        glyphs: impl Iterator<Item = Glyph>,
    ) {
        let brush = self.convert_paint(paint_ref.into());
        let glyph_run = GlyphRunCommand {
            font_data: font.clone(),
            font_size,
            hint,
            normalized_coords: normalized_coords.to_vec(),
            embolden,
            style: style.into().to_owned(),
            brush,
            brush_alpha,
            transform,
            glyph_transform,
            glyphs: glyphs.into_iter().collect(),
        };
        self.commands.push(RenderCommand::GlyphRun(glyph_run));
    }

    fn draw_box_shadow(
        &mut self,
        transform: Affine,
        rect: Rect,
        brush: Color,
        radius: f64,
        std_dev: f64,
    ) {
        let box_shadow = BoxShadowCommand {
            transform,
            rect,
            brush,
            radius,
            std_dev,
        };
        self.commands.push(RenderCommand::BoxShadow(box_shadow));
    }

    fn push_transform_3d(&mut self, m: [f64; 16]) {
        self.commands.push(RenderCommand::PushTransform3d(m));
    }

    fn pop_transform_3d(&mut self) {
        self.commands.push(RenderCommand::PopTransform3d);
    }

    fn draw_warped(&mut self, content: &Scene, mesh: &crate::WarpMesh) {
        self.commands.push(RenderCommand::Warped(WarpedCommand { content: content.clone(), mesh: mesh.clone() }));
    }

    fn append_scene(&mut self, scene: Scene, scene_transform: Affine) {
        self.commands.extend(
            scene
                .commands
                .into_iter()
                .map(|cmd| cmd.apply_transform(scene_transform)),
        );
    }
}

/// Serde helper for serializing `BezPath` as an SVG path string.
#[cfg(feature = "serde")]
mod svg_path {
    use kurbo::BezPath;
    use serde::{self, Deserialize, Deserializer, Serializer};

    use crate::svg_path_parser;

    pub fn serialize<S>(path: &BezPath, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&path.to_svg())
    }

    pub fn deserialize<'de, D>(deserializer: D) -> Result<BezPath, D::Error>
    where
        D: Deserializer<'de>,
    {
        let s = String::deserialize(deserializer)?;
        svg_path_parser::parse_svg_path(&s).map_err(serde::de::Error::custom)
    }
}

/// Rostrum patch (round 8): a recording replayed under `transform` with its colours multiplied by `color`
/// (rgb: a tint, a: opacity). Inside a layer the layer carries the opacity, so its contents are not faded twice.
pub fn replay_tinted<S: PaintScene>(scene: &mut S, rec: &Scene, transform: Affine, color: [f32; 4]) {
    let [tr, tg, tb, alpha] = color;
    let tint = |c: Color, a: f32| {
        let [r, g, b, ca] = c.components;
        Color::new([r * tr, g * tg, b * tb, ca * a])
    };
    let paint = |p: &Paint, a: f32| -> Paint {
        match p {
            Paint::Solid(c) => Paint::Solid(tint(*c, a)),
            Paint::Gradient(g) => {
                let mut g = g.clone();
                for stop in g.stops.iter_mut() {
                    stop.color = stop.color.map_in(peniko::color::ColorSpaceTag::Srgb, |r, gg, b, ca| [r * tr, gg * tg, b * tb, ca * a]);
                }
                Paint::Gradient(g)
            }
            Paint::Image(i) => Paint::Image(i.clone().multiply_alpha(a)),
            other => other.clone(),
        }
    };
    let mut depth = 0usize;
    for cmd in &rec.commands {
        let a = if depth == 0 { alpha } else { 1.0 };
        match cmd {
            RenderCommand::PushLayer(c) => {
                scene.push_layer(c.fill, c.blend, c.alpha * a, transform * c.transform, &c.clip, c.filter.clone(), c.backdrop_filter.clone());
                depth += 1;
            }
            RenderCommand::PushClipLayer(c) => {
                scene.push_clip_layer(c.fill, transform * c.transform, &c.clip);
                depth += 1;
            }
            RenderCommand::PopLayer => {
                scene.pop_layer();
                depth = depth.saturating_sub(1);
            }
            RenderCommand::Fill(c) => scene.fill(c.fill, transform * c.transform, &paint(&c.brush, a), c.brush_transform, &c.shape),
            RenderCommand::Stroke(c) => scene.stroke(&c.style, transform * c.transform, &paint(&c.brush, a), c.brush_transform, &c.shape),
            RenderCommand::GlyphRun(c) => scene.draw_glyphs(&c.font_data, c.font_size, c.hint, &c.normalized_coords, c.embolden, &c.style, &paint(&c.brush, 1.0), c.brush_alpha * a, transform * c.transform, c.glyph_transform, c.glyphs.iter().copied()),
            RenderCommand::BoxShadow(c) => scene.draw_box_shadow(transform * c.transform, c.rect, tint(c.brush, a), c.radius, c.std_dev),
            // A warp inside a sprite keeps its mesh (untinted: the mesh draws the recording as an image).
            RenderCommand::Warped(_) | RenderCommand::PushTransform3d(_) | RenderCommand::PopTransform3d => {
                replay_structural(scene, cmd.clone(), transform)
            }
        }
    }
}

/// Rostrum patch (round 11): replays a recorded warp or 3D push / pop under `transform`.
pub(crate) fn replay_structural<S: PaintScene + ?Sized>(scene: &mut S, cmd: RenderCommand, transform: Affine) {
    match cmd.apply_transform(transform) {
        RenderCommand::Warped(c) => scene.draw_warped(&c.content, &c.mesh),
        RenderCommand::PushTransform3d(m) => scene.push_transform_3d(m),
        RenderCommand::PopTransform3d => scene.pop_transform_3d(),
        _ => {}
    }
}

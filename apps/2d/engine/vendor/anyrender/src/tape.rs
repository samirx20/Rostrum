//! Rostrum patch (export round 5): a frame's paint calls kept as they were made, to be made again on another thread.
//!
//! An export's drawing workers lay out and walk their frames on the processor and record each walk on a `Tape`; one
//! thread owns the graphics card and plays every tape on its surface (`play`). Playing makes exactly the calls the walk
//! made, with the same arguments (shapes kept as the backend reads them: `Kept`), so the picture is the one painting
//! the page straight onto the card gives, bit for bit. Unlike `Scene` nothing is turned into paths or approximated.
//!
//! Calls whose answer depends on the backend (a kept or held picture, a glow captured as one picture) cannot be
//! recorded: the tape answers "can't", notes why (`unfit`), and the caller paints that frame straight on a card.

use std::sync::Arc;

use kurbo::{Affine, BezPath, Circle, Line, PathEl, Point, Rect, RoundedRect, Shape, Stroke};
use peniko::{BlendMode, Color, Fill, FontData, Style};

use crate::{Filter, Glyph, NormalizedCoord, Paint, PaintRef, PaintScene, RenderContext, Scene, SpriteInstance, WarpMesh};

/// A shape as a backend reads it: as itself when it is one of kurbo's special shapes, else its outline at each
/// tolerance the Skia backend asks for (0.1 for drawing, 0.01 for clips) and its bounds.
#[derive(Clone, Debug)]
pub enum Kept {
    Rect(Rect),
    Rounded(RoundedRect),
    Line(Line),
    Circle(Circle),
    /// A shape that is a path already (`as_path_slice`): every tolerance gives these elements.
    Path(BezPath),
    /// Any other shape: its elements at 0.1 and at 0.01, and its bounds.
    Flat { coarse: BezPath, fine: BezPath, bounds: Rect, area: f64 },
}

impl Kept {
    pub fn of(shape: &impl Shape) -> Kept {
        if let Some(r) = shape.as_rect() {
            Kept::Rect(r)
        } else if let Some(r) = shape.as_rounded_rect() {
            Kept::Rounded(r)
        } else if let Some(l) = shape.as_line() {
            Kept::Line(l)
        } else if let Some(c) = shape.as_circle() {
            Kept::Circle(c)
        } else if let Some(p) = shape.as_path_slice() {
            Kept::Path(BezPath::from_vec(p.to_vec()))
        } else {
            Kept::Flat { coarse: shape.to_path(0.1), fine: shape.to_path(0.01), bounds: shape.bounding_box(), area: shape.area() }
        }
    }

    fn outline(&self, tolerance: f64) -> BezPath {
        match self {
            Kept::Rect(r) => r.to_path(tolerance),
            Kept::Rounded(r) => r.to_path(tolerance),
            Kept::Line(l) => l.to_path(tolerance),
            Kept::Circle(c) => c.to_path(tolerance),
            Kept::Path(p) => p.clone(),
            // The backend asks only for 0.1 and 0.01; the nearer of the two otherwise.
            Kept::Flat { coarse, fine, .. } => if tolerance >= 0.03 { coarse.clone() } else { fine.clone() },
        }
    }
}

impl Shape for Kept {
    type PathElementsIter<'iter> = std::vec::IntoIter<PathEl>;

    fn path_elements(&self, tolerance: f64) -> Self::PathElementsIter<'_> {
        self.outline(tolerance).into_elements().into_iter()
    }

    fn to_path(&self, tolerance: f64) -> BezPath {
        self.outline(tolerance)
    }

    fn area(&self) -> f64 {
        match self {
            Kept::Rect(r) => r.area(),
            Kept::Rounded(r) => r.area(),
            Kept::Line(l) => l.area(),
            Kept::Circle(c) => c.area(),
            Kept::Path(p) => p.area(),
            Kept::Flat { area, .. } => *area,
        }
    }

    fn perimeter(&self, accuracy: f64) -> f64 {
        self.outline(0.1).perimeter(accuracy)
    }

    fn winding(&self, pt: Point) -> i32 {
        match self {
            Kept::Rect(r) => r.winding(pt),
            Kept::Rounded(r) => r.winding(pt),
            Kept::Line(l) => l.winding(pt),
            Kept::Circle(c) => c.winding(pt),
            Kept::Path(p) => p.winding(pt),
            Kept::Flat { fine, .. } => fine.winding(pt),
        }
    }

    fn bounding_box(&self) -> Rect {
        match self {
            Kept::Rect(r) => r.bounding_box(),
            Kept::Rounded(r) => r.bounding_box(),
            Kept::Line(l) => l.bounding_box(),
            Kept::Circle(c) => c.bounding_box(),
            Kept::Path(p) => p.bounding_box(),
            Kept::Flat { bounds, .. } => *bounds,
        }
    }

    fn as_line(&self) -> Option<Line> {
        if let Kept::Line(l) = self { Some(*l) } else { None }
    }

    fn as_rect(&self) -> Option<Rect> {
        if let Kept::Rect(r) = self { Some(*r) } else { None }
    }

    fn as_rounded_rect(&self) -> Option<RoundedRect> {
        if let Kept::Rounded(r) = self { Some(*r) } else { None }
    }

    fn as_circle(&self) -> Option<Circle> {
        if let Kept::Circle(c) = self { Some(*c) } else { None }
    }

    fn as_path_slice(&self) -> Option<&[PathEl]> {
        if let Kept::Path(p) = self { Some(p.elements()) } else { None }
    }
}

/// One paint call and its arguments.
#[derive(Clone, Debug)]
enum Call {
    Reset,
    Layer { fill: Fill, blend: BlendMode, alpha: f32, transform: Affine, clip: Kept, filter: Option<Arc<Filter>>, backdrop: Option<Arc<Filter>> },
    ClipLayer { fill: Fill, transform: Affine, clip: Kept },
    Pop,
    Push3d([f64; 16]),
    Pop3d,
    Instances { content: Scene, to_sprite: Affine, bounds: Rect, instances: Vec<SpriteInstance> },
    Warped { content: Scene, mesh: WarpMesh },
    Stroke { style: Stroke, transform: Affine, brush: Paint, brush_transform: Option<Affine>, shape: Kept },
    Fill { fill: Fill, transform: Affine, brush: Paint, brush_transform: Option<Affine>, shape: Kept },
    #[allow(clippy::type_complexity)]
    Glyphs { font: FontData, size: f32, hint: bool, coords: Vec<NormalizedCoord>, embolden: kurbo::Vec2, style: Style, brush: Paint, brush_alpha: f32, transform: Affine, glyph_transform: Option<Affine>, glyphs: Vec<Glyph> },
    BoxShadow { transform: Affine, rect: Rect, brush: Color, radius: f64, std_dev: f64 },
}

/// A frame's paint calls, in order (see the module's words).
#[derive(Clone, Debug, Default)]
pub struct Tape {
    calls: Vec<Call>,
    /// Why this frame can't be played from its tape (the first call that needed the backend's own answer).
    pub unfit: Option<&'static str>,
}

impl Tape {
    pub fn new() -> Tape {
        Tape::default()
    }

    pub fn len(&self) -> usize {
        self.calls.len()
    }

    pub fn is_empty(&self) -> bool {
        self.calls.is_empty()
    }

    fn unfit(&mut self, why: &'static str) -> bool {
        self.unfit.get_or_insert(why);
        false
    }

    /// Makes every recorded call on `scene`, in order, with its arguments.
    pub fn play<S: PaintScene>(&self, scene: &mut S) {
        for call in &self.calls {
            match call {
                Call::Reset => scene.reset(),
                Call::Layer { fill, blend, alpha, transform, clip, filter, backdrop } => scene.push_layer(*fill, *blend, *alpha, *transform, clip, filter.clone(), backdrop.clone()),
                Call::ClipLayer { fill, transform, clip } => scene.push_clip_layer(*fill, *transform, clip),
                Call::Pop => scene.pop_layer(),
                Call::Push3d(m) => scene.push_transform_3d(*m),
                Call::Pop3d => scene.pop_transform_3d(),
                Call::Instances { content, to_sprite, bounds, instances } => scene.draw_instances(content, *to_sprite, *bounds, instances),
                Call::Warped { content, mesh } => scene.draw_warped(content, mesh),
                Call::Stroke { style, transform, brush, brush_transform, shape } => scene.stroke(style, *transform, brush.as_ref(), *brush_transform, shape),
                Call::Fill { fill, transform, brush, brush_transform, shape } => scene.fill(*fill, *transform, brush.as_ref(), *brush_transform, shape),
                Call::Glyphs { font, size, hint, coords, embolden, style, brush, brush_alpha, transform, glyph_transform, glyphs } => {
                    scene.draw_glyphs(font, *size, *hint, coords, *embolden, style, brush.as_ref(), *brush_alpha, *transform, *glyph_transform, glyphs.iter().copied())
                }
                Call::BoxShadow { transform, rect, brush, radius, std_dev } => scene.draw_box_shadow(*transform, *rect, *brush, *radius, *std_dev),
            }
        }
    }
}

/// A paint call's brush, owned. A backend's own custom paint has no owned form: the tape is unfit.
fn owned(tape: &mut Tape, p: PaintRef<'_>) -> Paint {
    match p {
        Paint::Solid(c) => Paint::Solid(c),
        Paint::Gradient(g) => Paint::Gradient(g.clone()),
        Paint::Image(i) => Paint::Image(i.to_owned()),
        Paint::Resource(id) => Paint::Resource(id),
        Paint::Custom(_) => {
            tape.unfit("a custom paint");
            Paint::Solid(Color::TRANSPARENT)
        }
    }
}

impl RenderContext for Tape {}

impl PaintScene for Tape {
    fn reset(&mut self) {
        self.calls.push(Call::Reset);
    }

    fn push_layer(&mut self, fill: Fill, blend: impl Into<BlendMode>, alpha: f32, transform: Affine, clip: &impl Shape, filter: Option<Arc<Filter>>, backdrop_filter: Option<Arc<Filter>>) {
        // A filter that writes the comp cache's buffers is written on the frame's own card, before its reply.
        if filter.iter().chain(backdrop_filter.iter()).any(|f| !f.taps.is_empty()) {
            self.unfit("a filter writing the comp cache");
        }
        self.calls.push(Call::Layer { fill, blend: blend.into(), alpha, transform, clip: Kept::of(clip), filter, backdrop: backdrop_filter });
    }

    fn push_clip_layer(&mut self, fill: Fill, transform: Affine, clip: &impl Shape) {
        self.calls.push(Call::ClipLayer { fill, transform, clip: Kept::of(clip) });
    }

    fn pop_layer(&mut self) {
        self.calls.push(Call::Pop);
    }

    fn push_transform_3d(&mut self, m: [f64; 16]) {
        self.calls.push(Call::Push3d(m));
    }

    fn pop_transform_3d(&mut self) {
        self.calls.push(Call::Pop3d);
    }

    fn draw_instances(&mut self, content: &Scene, to_sprite: Affine, bounds: Rect, instances: &[SpriteInstance]) {
        self.calls.push(Call::Instances { content: content.clone(), to_sprite, bounds, instances: instances.to_vec() });
    }

    fn draw_warped(&mut self, content: &Scene, mesh: &WarpMesh) {
        self.calls.push(Call::Warped { content: content.clone(), mesh: mesh.clone() });
    }

    fn draw_held(&mut self) -> bool {
        self.unfit("a held picture")
    }

    fn draw_cached(&mut self, _k: usize) -> bool {
        self.unfit("a kept picture")
    }

    fn draw_cached_moved(&mut self, _k: usize, _m: [f64; 6]) -> bool {
        self.unfit("a kept picture")
    }

    fn draw_cached_streak(&mut self, _k: usize, _moves: &[[f64; 6]], _rect: Option<[f32; 4]>, _blend: BlendMode) -> bool {
        self.unfit("a streak")
    }

    fn begin_kept(&mut self, _k: usize) -> bool {
        self.unfit("a picture to keep")
    }

    fn push_glow_layer(&mut self, _glows: &[(Arc<Filter>, f32, Rect)], _alpha: f32, _blend: Option<BlendMode>, _transform: Affine, _clip: Option<Rect>, _filter: Option<Arc<Filter>>) -> bool {
        self.unfit("a glow")
    }

    fn stroke<'a>(&mut self, style: &Stroke, transform: Affine, brush: impl Into<PaintRef<'a>>, brush_transform: Option<Affine>, shape: &impl Shape) {
        let brush = owned(self, brush.into());
        self.calls.push(Call::Stroke { style: style.clone(), transform, brush, brush_transform, shape: Kept::of(shape) });
    }

    fn fill<'a>(&mut self, style: Fill, transform: Affine, brush: impl Into<PaintRef<'a>>, brush_transform: Option<Affine>, shape: &impl Shape) {
        let brush = owned(self, brush.into());
        self.calls.push(Call::Fill { fill: style, transform, brush, brush_transform, shape: Kept::of(shape) });
    }

    fn draw_glyphs<'a, 's: 'a>(
        &'s mut self,
        font: &'a FontData,
        font_size: f32,
        hint: bool,
        normalized_coords: &'a [NormalizedCoord],
        embolden: kurbo::Vec2,
        style: impl Into<peniko::StyleRef<'a>>,
        brush: impl Into<PaintRef<'a>>,
        brush_alpha: f32,
        transform: Affine,
        glyph_transform: Option<Affine>,
        glyphs: impl Iterator<Item = Glyph> + Clone,
    ) {
        let brush = owned(self, brush.into());
        self.calls.push(Call::Glyphs {
            font: font.clone(),
            size: font_size,
            hint,
            coords: normalized_coords.to_vec(),
            embolden,
            style: style.into().to_owned(),
            brush,
            brush_alpha,
            transform,
            glyph_transform,
            glyphs: glyphs.collect(),
        });
    }

    fn draw_box_shadow(&mut self, transform: Affine, rect: Rect, brush: Color, radius: f64, std_dev: f64) {
        self.calls.push(Call::BoxShadow { transform, rect, brush, radius, std_dev });
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A shape the backend reads as a path at 0.1 and 0.01 reads the same through its kept form.
    #[test]
    fn a_kept_shape_reads_as_the_shape() {
        let e = kurbo::Ellipse::new((10.0, 20.0), (30.0, 7.0), 0.3);
        let k = Kept::of(&e);
        assert_eq!(k.to_path(0.1), e.to_path(0.1));
        assert_eq!(k.to_path(0.01), e.to_path(0.01));
        assert_eq!(k.bounding_box(), e.bounding_box());
        let r = RoundedRect::new(0.0, 0.0, 10.0, 5.0, 2.0);
        assert_eq!(Kept::of(&r).as_rounded_rect(), Some(r));
        assert_eq!(Kept::of(&Rect::new(0.0, 0.0, 1.0, 1.0)).as_rect(), Some(Rect::new(0.0, 0.0, 1.0, 1.0)));
    }

    #[test]
    fn a_tape_is_sent_to_another_thread() {
        fn send<T: Send>() {}
        send::<Tape>();
    }
}

//! G4 power windows (docs/phase1/GRADING.md §3.2): shapes that give a layer's matte a coverage by position.
//!
//! Coordinates are fractions of the frame (x of the width, y of the height); every length in px below is `fraction ×
//! frame size`, a soft edge is a fraction of the frame HEIGHT. A window is one of
//! - `Ellipse { centre, size, rotation }` (size = full width and height, rotation degrees clockwise);
//! - `Linear { from, to, width }`: the band of points within `width / 2` of the line through `from` and `to`;
//! - `Gradient { from, to }`: a ramp, coverage 1 at `from`, 0 at `to`, linear between, held beyond (no edge, so no `soft`);
//! - `Polygon(points)` and `Bezier(nodes)` (closed; a node is a point and its in / out handles as offsets, flattened
//!   into [`BEZIER_STEPS`] points a segment).
//!
//! `transform` (`pan`, `scale`, `rotate`) moves the whole window about its pivot (ellipse centre, middle of a line,
//! centre of the bounding box of a polygon), in px: scale and rotation act on the px shape, pan is a fraction of the frame.
//!
//! Edge: with `d` the distance in px from the shape's edge, positive inside (exact for lines and polygons; the first-order
//! estimate `k0 (k0 − 1) / k1` for an ellipse), coverage = `smoothstep(−o, i, d)` with `i`, `o` = the inner and outer soft
//! widths, at least 0.5 px each (an antialiased hard edge). Per window: invert (`1 − c`), then `opacity ×`. Windows
//! combine in list order from nothing: add `max(acc, c)`, subtract `acc (1 − c)`, intersect `acc c`; the first window
//! must be an add. The combined window coverage is dithered (triangular, ±`dither`, a hash of the pixel) where it is
//! partial, so the soft edge has no 8-bit bands. The matte then multiplies it into the qualifier's coverage (matte.rs).
//!
//! The GPU twin is window_sksl.rs; both read the same [`Window::slots`], so the two evaluate one parameter set.
use super::smoothstep;

/// Most windows in one layer's matte.
pub const MAX_WINDOWS: usize = 8;
/// Flattened points of one polygon or bezier.
pub const MAX_POINTS: usize = 256;
/// Points a bezier segment is flattened to.
pub const BEZIER_STEPS: usize = 12;

/// A bezier node: its point and in / out handles (offsets from the point).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Node {
    pub p: [f32; 2],
    pub hin: [f32; 2],
    pub hout: [f32; 2],
}

#[derive(Clone, Debug, PartialEq)]
pub enum Shape {
    Ellipse { centre: [f32; 2], size: [f32; 2], rotation: f32 },
    Linear { from: [f32; 2], to: [f32; 2], width: f32 },
    Gradient { from: [f32; 2], to: [f32; 2] },
    Polygon(Vec<[f32; 2]>),
    Bezier(Vec<Node>),
}

/// How a window joins those before it.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub enum Mode {
    #[default]
    Add,
    Subtract,
    Intersect,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Window {
    pub shape: Shape,
    pub mode: Mode,
    /// Inner and outer soft width, fractions of the frame height.
    pub soft: [f32; 2],
    pub invert: bool,
    pub opacity: f32,
    pub pan: [f32; 2],
    pub scale: [f32; 2],
    /// Degrees clockwise.
    pub rotate: f32,
}

/// What the generated shader is built for (the structure): the shape and how many points.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Ellipse,
    Band,
    Ramp,
    Poly(usize),
}

fn flatten(nodes: &[Node]) -> Vec<[f32; 2]> {
    let mut out = vec![];
    for (i, a) in nodes.iter().enumerate() {
        let b = &nodes[(i + 1) % nodes.len()];
        let (p0, p1, p2, p3) = (a.p, [a.p[0] + a.hout[0], a.p[1] + a.hout[1]], [b.p[0] + b.hin[0], b.p[1] + b.hin[1]], b.p);
        for s in 0..BEZIER_STEPS {
            let (t, u) = (s as f32 / BEZIER_STEPS as f32, 1.0 - s as f32 / BEZIER_STEPS as f32);
            out.push(std::array::from_fn(|k| u * u * u * p0[k] + 3.0 * u * u * t * p1[k] + 3.0 * u * t * t * p2[k] + t * t * t * p3[k]));
        }
    }
    out
}

impl Window {
    pub fn new(shape: Shape) -> Window {
        Window { shape, mode: Mode::Add, soft: [0.0; 2], invert: false, opacity: 1.0, pan: [0.0; 2], scale: [1.0; 2], rotate: 0.0 }
    }

    pub fn kind(&self) -> Kind {
        match &self.shape {
            Shape::Ellipse { .. } => Kind::Ellipse,
            Shape::Linear { .. } => Kind::Band,
            Shape::Gradient { .. } => Kind::Ramp,
            Shape::Polygon(p) => Kind::Poly(p.len()),
            Shape::Bezier(n) => Kind::Poly(n.len() * BEZIER_STEPS),
        }
    }

    fn pivot(&self) -> [f32; 2] {
        match &self.shape {
            Shape::Ellipse { centre, .. } => *centre,
            Shape::Linear { from, to, .. } | Shape::Gradient { from, to } => [(from[0] + to[0]) / 2.0, (from[1] + to[1]) / 2.0],
            Shape::Polygon(_) | Shape::Bezier(_) => {
                let pts = self.points();
                let (lo, hi) = pts.iter().fold(([f32::MAX; 2], [f32::MIN; 2]), |(lo, hi), p| (std::array::from_fn(|k| lo[k].min(p[k])), std::array::from_fn(|k| hi[k].max(p[k]))));
                [(lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0]
            }
        }
    }

    /// The polygon's points (a bezier flattened), fractions.
    pub fn points(&self) -> Vec<[f32; 2]> {
        match &self.shape {
            Shape::Polygon(p) => p.clone(),
            Shape::Bezier(n) => flatten(n),
            _ => vec![],
        }
    }

    /// The parameters as uniform slots (the layout the shader reads, window_sksl.rs): the 11 common ones (soft in, soft out, opacity, pan, scale, cos, sin, pivot), then the shape's: ellipse
    /// centre ×2, semi axes ×2, cos, sin of its total rotation; band from ×2, to ×2, width; ramp from ×2, to ×2; polygon points ×2 each.
    pub fn slots(&self) -> Vec<f32> {
        let (s, c) = self.rotate.to_radians().sin_cos();
        let pv = self.pivot();
        let mut v = vec![self.soft[0], self.soft[1], self.opacity, self.pan[0], self.pan[1], self.scale[0], self.scale[1], c, s, pv[0], pv[1]];
        match &self.shape {
            Shape::Ellipse { centre, size, rotation } => {
                let (s, c) = (rotation + self.rotate).to_radians().sin_cos();
                v.extend([centre[0], centre[1], size[0] / 2.0, size[1] / 2.0, c, s]);
            }
            Shape::Linear { from, to, width } => v.extend([from[0], from[1], to[0], to[1], *width]),
            Shape::Gradient { from, to } => v.extend([from[0], from[1], to[0], to[1]]),
            _ => v.extend(self.points().into_iter().flatten()),
        }
        v
    }

    /// The coverage at the centre of pixel (`x`, `y`) of a `w × h` frame, before the mode joins it (the CPU twin of window_sksl.rs).
    pub fn coverage(&self, x: usize, y: usize, w: usize, h: usize) -> f64 {
        self.eval(&self.slots().iter().map(|v| *v as f64).collect::<Vec<_>>(), x, y, w, h)
    }

    /// [`Window::coverage`] with the slots made once (`slots()` as f64).
    fn eval(&self, s: &[f64], x: usize, y: usize, w: usize, h: usize) -> f64 {
        let (sz, q) = ([w as f64, h as f64], [x as f64 + 0.5, y as f64 + 0.5]);
        let place = |i: usize| -> [f64; 2] {
            let v = [(s[i] - s[9]) * sz[0] * s[5], (s[i + 1] - s[10]) * sz[1] * s[6]];
            [s[9] * sz[0] + s[3] * sz[0] + s[7] * v[0] - s[8] * v[1], s[10] * sz[1] + s[4] * sz[1] + s[8] * v[0] + s[7] * v[1]]
        };
        let edge = |d: f64| smoothstep(-(s[1] * sz[1]).max(0.5), (s[0] * sz[1]).max(0.5), d);
        let c = match self.kind() {
            Kind::Ellipse => {
                let c = place(11);
                let r = [s[13] * sz[0] * s[5], s[14] * sz[1] * s[6]];
                let v = [q[0] - c[0], q[1] - c[1]];
                let u = [s[15] * v[0] + s[16] * v[1], -s[16] * v[0] + s[15] * v[1]];
                let k0 = ((u[0] / r[0]).powi(2) + (u[1] / r[1]).powi(2)).sqrt();
                let k1 = ((u[0] / (r[0] * r[0])).powi(2) + (u[1] / (r[1] * r[1])).powi(2)).sqrt();
                edge(if k1 < 1e-6 { r[0].min(r[1]) } else { -(k0 * (k0 - 1.0) / k1) })
            }
            Kind::Band => {
                let (a, b) = (place(11), place(13));
                let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
                let dist = ((q[0] - a[0]) * -dy + (q[1] - a[1]) * dx).abs() / (dx * dx + dy * dy).sqrt().max(1e-9);
                edge(s[15] * sz[1] * (s[5] + s[6]) / 4.0 - dist)
            }
            Kind::Ramp => {
                let (a, b) = (place(11), place(13));
                let (dx, dy) = (b[0] - a[0], b[1] - a[1]);
                (1.0 - ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / (dx * dx + dy * dy).max(1e-9)).clamp(0.0, 1.0)
            }
            Kind::Poly(n) => {
                let (mut dm, mut inside) = (f64::MAX, false);
                let mut pa = place(11 + 2 * (n - 1));
                for k in 0..n {
                    let pb = place(11 + 2 * k);
                    let (ex, ey) = (pb[0] - pa[0], pb[1] - pa[1]);
                    let t = (((q[0] - pa[0]) * ex + (q[1] - pa[1]) * ey) / (ex * ex + ey * ey).max(1e-12)).clamp(0.0, 1.0);
                    dm = dm.min(((q[0] - pa[0] - ex * t).powi(2) + (q[1] - pa[1] - ey * t).powi(2)).sqrt());
                    if (pa[1] > q[1]) != (pb[1] > q[1]) && q[0] < (pb[0] - pa[0]) * (q[1] - pa[1]) / (pb[1] - pa[1]) + pa[0] {
                        inside = !inside;
                    }
                    pa = pb;
                }
                edge(if inside { dm } else { -dm })
            }
        };
        (if self.invert { 1.0 - c } else { c }) * s[2]
    }

    /// Loud errors for what no frame can show (the spec's own errors name the window).
    pub fn check(&self, at: &str) -> Result<(), String> {
        let fin = |p: &[f32]| p.iter().all(|v| v.is_finite());
        let ok = match &self.shape {
            Shape::Ellipse { centre, size, rotation } => fin(centre) && size.iter().all(|v| *v > 0.0 && v.is_finite()) && rotation.is_finite(),
            Shape::Linear { from, to, width } => fin(from) && fin(to) && from != to && *width > 0.0 && width.is_finite(),
            Shape::Gradient { from, to } => fin(from) && fin(to) && from != to,
            Shape::Polygon(p) => p.len() >= 3 && p.iter().all(|p| fin(p)),
            Shape::Bezier(n) => n.len() >= 2 && n.iter().all(|n| fin(&n.p) && fin(&n.hin) && fin(&n.hout)),
        };
        let what = match &self.shape {
            Shape::Ellipse { .. } => "an ellipse needs a finite centre and a size above 0",
            Shape::Linear { .. } => "a linear window needs two different points and a width above 0",
            Shape::Gradient { .. } => "a gradient window needs two different points",
            Shape::Polygon(_) => "a polygon needs 3 or more finite points",
            Shape::Bezier(_) => "a bezier window needs 2 or more nodes, all finite",
        };
        if !ok {
            return Err(format!("{at}: {what}"));
        }
        if let Kind::Poly(n) = self.kind() {
            if n > MAX_POINTS {
                return Err(format!("{at}: a polygon has at most {} points ({} bezier nodes); got {n} flattened points", MAX_POINTS, MAX_POINTS / BEZIER_STEPS));
            }
        }
        if matches!(self.shape, Shape::Gradient { .. }) && self.soft != [0.0; 2] {
            return Err(format!("{at}: a gradient window has no soft edge (its ramp is its softness; move `to` away from `from`)"));
        }
        if !(self.soft.iter().all(|v| *v >= 0.0 && v.is_finite()) && (0.0..=1.0).contains(&self.opacity) && self.scale.iter().all(|v| *v > 0.0 && v.is_finite()) && fin(&self.pan) && self.rotate.is_finite()) {
            return Err(format!("{at}: soft is 0 or more (fractions of the frame height), opacity 0 … 1, scale above 0, pan and rotate finite numbers"));
        }
        Ok(())
    }
}

/// The deterministic dither noise of pixel (`x`, `y`) in 0 … 1 (interleaved gradient noise; window_sksl.rs has the same).
pub fn noise(x: f32, y: f32) -> f32 {
    let f = |v: f32| v - v.floor();
    f(52.982_918 * f(0.067_110_56 * x + 0.005_837_15 * y))
}

/// The windows' combined coverage on a `w × h` frame, dithered by `dither` (0: none; 1 / 255 for an 8-bit output).
pub fn coverage_image(ws: &[Window], w: usize, h: usize, dither: f32) -> Vec<f32> {
    let mut out = Vec::with_capacity(w * h);
    let slots: Vec<Vec<f64>> = ws.iter().map(|win| win.slots().iter().map(|v| *v as f64).collect()).collect();
    for y in 0..h {
        for x in 0..w {
            let mut acc = 0.0f64;
            for (win, s) in ws.iter().zip(&slots) {
                let c = win.eval(s, x, y, w, h);
                acc = match win.mode {
                    Mode::Add => acc.max(c),
                    Mode::Subtract => acc * (1.0 - c),
                    Mode::Intersect => acc * c,
                };
            }
            let mut a = acc as f32;
            if a > 0.0 && a < 1.0 && dither > 0.0 {
                a = (a + (noise(x as f32, y as f32) + noise(x as f32 + 37.0, y as f32 + 17.0) - 1.0) * dither).clamp(0.0, 1.0);
            }
            out.push(a);
        }
    }
    out
}

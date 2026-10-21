//! Scopes (docs/phase1/GRADING.md §5, §7.2): what a frame measures as, as data an agent reads (`measure`) and as
//! pictures drawn by our own code (`draw`). One implementation; the renderer feeds it the F16 frame the compositor
//! produced (before the 8-bit output step), the CLI feeds it image files.
//!
//! A [`Frame`] holds pixels in one [`Domain`]: `Display` (the picture after the view: sRGB-encoded Rec.709 for SDR,
//! PQ Rec.2020 for HDR; 1.0 = white), `AcesCg` (scene linear) or `AcesCct` (log). Percentiles, zones, histogram,
//! parade, clipping and balance are in the frame's domain; the vectorscope, skin line and gamut numbers are the
//! picture's Rec.709 view of the same light (sRGB-coded, as a 709 vectorscope shows it).
pub mod compare;
pub mod draw;
mod font;
pub mod measure;

use crate::convert::gamut_matrix;
use crate::matrix::{self, Mat3};
use crate::pipeline::{Pipeline, Working};
use crate::{Curve, Rgb};
use serde_json::Value;

/// What a pixel's numbers mean.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Domain {
    /// After the view. SDR: sRGB-coded Rec.709 (1.0 = 100 nits). HDR: PQ-coded Rec.2020 (1.0 = 10 000 nits).
    Display { hdr: bool },
    AcesCg,
    AcesCct,
}

fn m3(a: &str, b: &str) -> Mat3 {
    gamut_matrix(a, b).expect("registered gamuts")
}
fn mul(m: &Mat3, c: Rgb) -> Rgb {
    matrix::apply(m, c.map(f64::from)).map(|v| v as f32)
}

impl Domain {
    pub fn parse(id: &str, hdr: bool) -> Result<Domain, String> {
        match id {
            "display" => Ok(Domain::Display { hdr }),
            "acescg" => Ok(Domain::AcesCg),
            "acescct" => Ok(Domain::AcesCct),
            o => Err(format!("space is display, acescg or acescct; got `{o}`")),
        }
    }
    pub fn id(self) -> &'static str {
        match self {
            Domain::Display { .. } => "display",
            Domain::AcesCg => "acescg",
            Domain::AcesCct => "acescct",
        }
    }
    /// The luma weights of this domain's values (Rec.709 on display code, AP1 on ACEScg / ACEScct).
    pub fn luma_weights(self) -> [f32; 3] {
        match self {
            Domain::Display { .. } => [0.2126, 0.7152, 0.0722],
            _ => [0.272_228_7, 0.674_081_8, 0.053_689_5],
        }
    }
    pub fn luma(self, c: Rgb) -> f32 {
        let w = self.luma_weights();
        w[0] * c[0] + w[1] * c[1] + w[2] * c[2]
    }
    /// The value that counts as white: 1.0 on SDR display, 1000 nits on HDR, scene 1.0 on ACEScg / ACEScct.
    pub fn white(self) -> f32 {
        match self {
            Domain::Display { hdr: false } | Domain::AcesCg => 1.0,
            Domain::Display { hdr: true } => Curve::Pq100.encode(10.0),
            Domain::AcesCct => Curve::AcesCct.encode(1.0),
        }
    }
    /// The picture's light in linear Rec.709 (1.0 = SDR white; HDR graphics white 203 nits is 1.0).
    pub fn to_lin709(self, c: Rgb) -> Rgb {
        match self {
            Domain::Display { hdr: false } => c.map(|x| Curve::Srgb.decode(x)),
            Domain::Display { hdr: true } => mul(&m3("lin_rec2020", "lin_rec709"), c.map(|x| Curve::Pq100.decode(x) / crate::pipeline::HDR_GRAPHICS_WHITE)),
            Domain::AcesCg => mul(&m3("acescg", "lin_rec709"), c),
            Domain::AcesCct => mul(&m3("acescg", "lin_rec709"), c.map(|x| Curve::AcesCct.decode(x))),
        }
    }
    /// `to_lin709` with its matrix made once, for loops over pixels.
    pub fn to_lin709_fn(self) -> impl Fn(Rgb) -> Rgb + Copy {
        let m = match self {
            Domain::Display { hdr: true } => m3("lin_rec2020", "lin_rec709"),
            Domain::AcesCg | Domain::AcesCct => m3("acescg", "lin_rec709"),
            Domain::Display { hdr: false } => matrix::IDENTITY,
        };
        move |c| match self {
            Domain::Display { hdr: false } => c.map(|x| Curve::Srgb.decode(x)),
            Domain::Display { hdr: true } => mul(&m, c.map(|x| Curve::Pq100.decode(x) / crate::pipeline::HDR_GRAPHICS_WHITE)),
            Domain::AcesCg => mul(&m, c),
            Domain::AcesCct => mul(&m, c.map(|x| Curve::AcesCct.decode(x))),
        }
    }
    /// The picture as a Rec.709 vectorscope sees it: sRGB-coded Rec.709 of its light (the values themselves on SDR display).
    pub fn d709_fn(self) -> impl Fn(Rgb) -> Rgb + Copy {
        let lin = self.to_lin709_fn();
        move |c| if self == (Domain::Display { hdr: false }) { c } else { lin(c).map(|x| Curve::Srgb.encode(x)) }
    }
    /// The inverse of `to_lin709`.
    pub fn from_lin709(self, l: Rgb) -> Rgb {
        match self {
            Domain::Display { hdr: false } => l.map(|x| Curve::Srgb.encode(x)),
            Domain::Display { hdr: true } => mul(&m3("lin_rec709", "lin_rec2020"), l).map(|x| Curve::Pq100.encode(x * crate::pipeline::HDR_GRAPHICS_WHITE)),
            Domain::AcesCg => mul(&m3("lin_rec709", "acescg"), l),
            Domain::AcesCct => mul(&m3("lin_rec709", "acescg"), l).map(|x| Curve::AcesCct.encode(x)),
        }
    }
    /// `from_lin709` with its matrix made once.
    pub fn from_lin709_fn(self) -> impl Fn(Rgb) -> Rgb + Copy {
        let m = match self {
            Domain::Display { hdr: true } => m3("lin_rec709", "lin_rec2020"),
            Domain::AcesCg | Domain::AcesCct => m3("lin_rec709", "acescg"),
            Domain::Display { hdr: false } => matrix::IDENTITY,
        };
        move |l| match self {
            Domain::Display { hdr: false } => l.map(|x| Curve::Srgb.encode(x)),
            Domain::Display { hdr: true } => mul(&m, l).map(|x| Curve::Pq100.encode(x * crate::pipeline::HDR_GRAPHICS_WHITE)),
            Domain::AcesCg => mul(&m, l),
            Domain::AcesCct => mul(&m, l).map(|x| Curve::AcesCct.encode(x)),
        }
    }
    /// This domain's value → `to`'s (through linear Rec.709; negatives are kept).
    pub fn convert(self, to: Domain, c: Rgb) -> Rgb {
        if self == to { c } else { to.from_lin709(self.to_lin709(c)) }
    }
    /// A pixel of a renderer's working space (colour pipeline `p`, the compositor's rules) in this domain: `Display`
    /// is the picture after the view (unclamped: over-range and out-of-gamut values stay visible), the others are the
    /// scene light the working space holds.
    pub fn from_working(self, p: &Pipeline, w: Rgb) -> Rgb {
        match self {
            Domain::Display { hdr } => {
                let l = p.display_linear(w);
                if hdr { l.map(|x| Curve::Pq100.encode(x)) } else { l.map(|x| Curve::Srgb.encode(x)) }
            }
            Domain::AcesCg | Domain::AcesCct => {
                let cg = match p.working {
                    Working::AcesCg => w,
                    Working::LinearDisplay => mul(&m3("lin_rec709", "acescg"), w),
                    Working::Display => mul(&m3("lin_rec709", "acescg"), w.map(|x| Curve::Srgb.decode(x))),
                };
                if self == Domain::AcesCct { cg.map(|x| Curve::AcesCct.encode(x)) } else { cg }
            }
        }
    }
}

/// A frame to measure: `px` (row-major, top row first) in `domain`.
pub struct Frame {
    pub width: usize,
    pub height: usize,
    pub domain: Domain,
    pub px: Vec<Rgb>,
}

impl Frame {
    pub fn new(width: usize, height: usize, domain: Domain, px: Vec<Rgb>) -> Frame {
        assert_eq!(px.len(), width * height, "a frame holds width × height pixels");
        Frame { width, height, domain, px }
    }
    /// The same picture in another domain.
    pub fn to(&self, domain: Domain) -> Frame {
        let (a, b) = (self.domain.to_lin709_fn(), domain.from_lin709_fn());
        Frame { width: self.width, height: self.height, domain, px: if self.domain == domain { self.px.clone() } else { self.px.iter().map(|&c| b(a(c))).collect() } }
    }
}

/// The part of the frame a scope reads: the whole frame, a rectangle in frame fractions, or power windows (G4, grade/window.rs:
/// `{ "windows": [window] }`, the matte spec's window forms), which `resolve` turns into a `Mask` for the frame's size.
#[derive(Clone, Debug, PartialEq)]
pub enum Region {
    Full,
    Rect { x: f32, y: f32, w: f32, h: f32 },
    /// The windows, before the frame size is known.
    Windows(Vec<crate::grade::Window>),
    /// Coverage at frame size (0 = out, 255 = in: the windows' combined coverage of at least 1/2).
    Mask { width: usize, height: usize, coverage: Vec<u8> },
}

impl Region {
    /// `null` / absent: the whole frame; `{ x, y, w, h }` or `[x, y, w, h]` in fractions of the frame.
    pub fn parse(v: &Value) -> Result<Region, String> {
        let nums: Vec<f64> = match v {
            Value::Null => return Ok(Region::Full),
            Value::Array(a) => a.iter().filter_map(Value::as_f64).collect(),
            Value::Object(o) if o.contains_key("windows") => {
                if o.len() > 1 {
                    return Err("a window region is { windows: [window] } alone".into());
                }
                let list = o["windows"].as_array().filter(|a| !a.is_empty()).ok_or("region.windows is a list of windows (the matte spec's forms)")?;
                let ws = list.iter().enumerate().map(|(i, w)| crate::grade::Window::from_spec(w, &format!("region window {}", i + 1))).collect::<Result<Vec<_>, _>>()?;
                if ws[0].mode != crate::grade::Mode::Add {
                    return Err("region window 1 must be an `add`".into());
                }
                return Ok(Region::Windows(ws));
            }
            Value::Object(o) => {
                if let Some(bad) = o.keys().find(|k| !["x", "y", "w", "h"].contains(&k.as_str())) {
                    return Err(format!("region takes x, y, w, h (fractions of the frame); got `{bad}` (or windows: [..])"));
                }
                ["x", "y", "w", "h"].iter().map(|k| o.get(*k).and_then(Value::as_f64).unwrap_or(f64::NAN)).collect()
            }
            _ => return Err("region is { x, y, w, h } in fractions of the frame".into()),
        };
        if nums.len() != 4 || nums.iter().any(|n| !n.is_finite()) {
            return Err("region is { x, y, w, h }: four numbers, fractions of the frame (0..1)".into());
        }
        let (x, y, w, h) = (nums[0] as f32, nums[1] as f32, nums[2] as f32, nums[3] as f32);
        if x < 0.0 || y < 0.0 || w <= 0.0 || h <= 0.0 || x + w > 1.0001 || y + h > 1.0001 {
            return Err(format!("region [{x}, {y}, {w}, {h}] must lie inside the frame (x, y >= 0; w, h > 0; x + w and y + h <= 1)"));
        }
        Ok(Region::Rect { x, y, w, h })
    }
    /// Windows become the mask of a `width × height` frame (not dithered: a region is in or out); anything else is itself.
    pub fn resolve(&self, width: usize, height: usize) -> Region {
        match self {
            Region::Windows(ws) => Region::Mask { width, height, coverage: crate::grade::window_coverage(ws, width, height, 0.0).iter().map(|c| if *c >= 0.5 { 255 } else { 0 }).collect() },
            r => r.clone(),
        }
    }
    /// The pixel rectangle to loop over `(x0, y0, x1, y1)` (end exclusive) for a frame of this size.
    pub fn bounds(&self, width: usize, height: usize) -> (usize, usize, usize, usize) {
        match self {
            Region::Rect { x, y, w, h } => {
                let (x0, y0) = ((x * width as f32).round() as usize, (y * height as f32).round() as usize);
                let x1 = (((x + w) * width as f32).round() as usize).min(width);
                let y1 = (((y + h) * height as f32).round() as usize).min(height);
                let (x0, y0) = (x0.min(width.saturating_sub(1)), y0.min(height.saturating_sub(1)));
                (x0, y0, x1.max(x0 + 1).min(width), y1.max(y0 + 1).min(height))
            }
            _ => (0, 0, width, height),
        }
    }
    pub fn contains(&self, x: usize, y: usize) -> bool {
        match self {
            Region::Mask { width, coverage, .. } => coverage.get(y * width + x).is_some_and(|&c| c > 0),
            _ => true,
        }
    }
    pub fn as_json(&self) -> Option<Value> {
        match self {
            Region::Rect { x, y, w, h } => Some(serde_json::json!([x, y, w, h])),
            Region::Windows(w) => Some(serde_json::json!({ "windows": w.len() })),
            Region::Mask { coverage, .. } => Some(serde_json::json!({ "window": { "coveragePct": (1000.0 * coverage.iter().filter(|c| **c > 0).count() as f64 / coverage.len().max(1) as f64).round() / 10.0 } })),
            Region::Full => None,
        }
    }
}

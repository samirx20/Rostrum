//! The compositor's colour rules (docs/phase0/COLOUR_WAVE_B.md): what a layer's pixels become in the working
//! space, and what the working space becomes at the output. One place, used by every renderer that composites
//! (the Motion renderer for Motion, the Video Editor and standalone 3D; 3D thumbnails).
//!
//! Working spaces:
//! - `Display`: display-encoded values (the sRGB curve, Rec.709 primaries), graphics white = 1.0. What browsers
//!   blend in and what every render before Wave B used. HDR targets keep graphics white at 1.0 (= 203 nits,
//!   BT.2408) and carry highlights above it, wide-gamut colours as negatives (F16 holds both).
//! - `LinearDisplay`: the same light, linear (Motion's `blend: "linear"`).
//! - `AcesCg`: scene-referred ACEScg linear (the Video Editor's `blend: "linear"`); display-referred layers enter
//!   through the inverse view, so they leave through the forward view as they came in.
use crate::convert::gamut_matrix;
use crate::matrix::{self, Mat3};
use crate::spaces::Space;
use crate::view::{Target, View};
use crate::{Curve, Rgb};

/// Graphics white in HDR (BT.2408 reference white, 203 nits) in units of 100 nits.
pub const HDR_GRAPHICS_WHITE: f32 = 2.03;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Working {
    Display,
    LinearDisplay,
    AcesCg,
}

/// Output encodings by id, and the targets each can show.
const OUTPUTS: &[(&str, Target)] = &[
    ("srgb_display", Target::Sdr),
    ("rec1886_rec709", Target::Sdr),
    ("p3d65_display", Target::Sdr),
    ("rec2100_pq", Target::Hdr1000),
];

pub fn output_ids() -> impl Iterator<Item = &'static str> {
    OUTPUTS.iter().map(|o| o.0)
}

/// A layer's colour: display-referred (`"display"`) or a scene-referred `rostrum-color` space id.
#[derive(Clone, Copy, Debug)]
pub enum Input {
    Display,
    Scene { decode: Curve, to_acescg: Mat3 },
}

impl Input {
    pub fn parse(id: &str) -> Result<Input, String> {
        if id == "display" {
            return Ok(Input::Display);
        }
        let s = Space::get(id).ok_or_else(|| format!("unknown input colour space `{id}` (\"display\" or a rostrum-color space id)"))?;
        Ok(Input::Scene { decode: s.curve, to_acescg: gamut_matrix(s.gamut, "acescg")? })
    }
}

#[derive(Clone, Copy)]
pub struct Pipeline {
    pub working: Working,
    pub view: &'static View,
    pub target: Target,
    /// Rec.709 display linear ↔ the target's display primaries (identity for SDR).
    to_target: Mat3,
    from_target: Mat3,
    rec709_acescg: Mat3,
}

fn mat(m: &Mat3, c: Rgb) -> Rgb {
    matrix::apply(m, c.map(f64::from)).map(|v| v as f32)
}

impl Pipeline {
    pub fn new(working: Working, view: &str, target: Target) -> Result<Pipeline, String> {
        let v = View::resolve(view, target)?;
        let to_target = match target {
            Target::Sdr => matrix::IDENTITY,
            Target::Hdr1000 => gamut_matrix("lin_rec709", "lin_rec2020")?.map(|r| r.map(|x| x * HDR_GRAPHICS_WHITE as f64)),
        };
        Ok(Pipeline { working, view: v, target, to_target, from_target: matrix::inverse(&to_target), rec709_acescg: gamut_matrix("lin_rec709", "acescg")? })
    }

    /// Display-encoded code (graphics) → working.
    pub fn display_in(&self, c: Rgb) -> Rgb {
        match self.working {
            Working::Display => c,
            Working::LinearDisplay => c.map(|x| Curve::Srgb.decode(x)),
            Working::AcesCg => self.view.inverse(mat(&self.to_target, c.map(|x| Curve::Srgb.decode(x))), self.target),
        }
    }


    /// Display-encoded code → the scene light (ACEScg) this pipeline's view shows as that code, whatever the working space: a 3D
    /// scene's background as authored, laid under its light before its grade and view (assets.rs `bg`).
    pub fn display_to_scene(&self, c: Rgb) -> Rgb {
        self.view.inverse(mat(&self.to_target, c.map(|x| Curve::Srgb.decode(x))), self.target)
    }

    /// Display-encoded code → its light in the working space, as Skia draws an sRGB colour (decode, then the
    /// gamut matrix), before any view: what a picture of a display-referred clip becomes when the clip's own layer
    /// filter applies the inverse view (the compositor's linear blend; `View::sksl_display_in`).
    pub fn display_light(&self, c: Rgb) -> Rgb {
        let lin = c.map(|x| Curve::Srgb.decode(x));
        match self.working {
            Working::Display => c,
            Working::LinearDisplay => lin,
            Working::AcesCg => mat(&self.rec709_acescg, lin),
        }
    }

    /// ACEScg (a scene-referred layer after its input transform) → working.
    pub fn scene_in(&self, acescg: Rgb) -> Rgb {
        let disp = || mat(&self.from_target, self.view.forward(acescg, self.target));
        match self.working {
            Working::Display => disp().map(|x| Curve::Srgb.encode(x)),
            Working::LinearDisplay => disp(),
            Working::AcesCg => acescg,
        }
    }

    /// One pixel of a layer with colour `input` → working.
    pub fn layer_in(&self, input: &Input, c: Rgb) -> Rgb {
        match input {
            Input::Display => self.display_in(c),
            Input::Scene { decode, to_acescg } => self.scene_in(mat(to_acescg, c.map(|x| decode.decode(x)))),
        }
    }

    /// Working → display linear in the target's primaries (1.0 = 100 nits).
    pub fn display_linear(&self, w: Rgb) -> Rgb {
        match self.working {
            Working::Display => mat(&self.to_target, w.map(|x| Curve::Srgb.decode(x))),
            Working::LinearDisplay => mat(&self.to_target, w),
            Working::AcesCg => self.view.forward(w, self.target),
        }
    }

    /// The output encoding `id` for this pipeline's target.
    pub fn output(&self, id: &str) -> Result<Output, String> {
        let &(_, target) = OUTPUTS.iter().find(|o| o.0 == id).ok_or_else(|| format!("unknown output `{id}` (one of {})", output_ids().collect::<Vec<_>>().join(", ")))?;
        if target != self.target {
            return Err(format!("output `{id}` shows the {target:?} target, but the pipeline renders {:?}", self.target));
        }
        let s = Space::get(id).expect("every output id is a registered space");
        let from = if target == Target::Sdr { "lin_rec709" } else { "lin_rec2020" };
        let identity = self.working == Working::Display && id == "srgb_display";
        Ok(Output { pipeline: *self, matrix: gamut_matrix(from, s.gamut)?, encode: s.curve, identity })
    }
}

/// Working → output code values in [0, 1] (straight alpha, before quantisation).
#[derive(Clone, Copy)]
pub struct Output {
    pub pipeline: Pipeline,
    matrix: Mat3,
    encode: Curve,
    /// Display working space shown on an sRGB display: the values already are the output (exact by construction).
    pub identity: bool,
}

impl Output {
    pub fn apply(&self, w: Rgb) -> Rgb {
        if self.identity {
            return w.map(|x| x.clamp(0.0, 1.0));
        }
        let d = mat(&self.matrix, self.pipeline.display_linear(w));
        d.map(|x| if x.is_nan() { 0.0 } else { self.encode.encode(x.max(0.0)).clamp(0.0, 1.0) })
    }
}

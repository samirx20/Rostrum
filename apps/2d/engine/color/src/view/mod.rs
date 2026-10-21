//! View transforms (docs/phase0/COLOUR_WAVE_B.md): scene-linear ACEScg → display linear in the target's
//! primaries (1.0 = 100 nits, so `hdr1000` peaks at 10.0), and back. Ids are the contract's.
//!   neutral   Khronos PBR Neutral (the default), with a BT.2408-style HDR generalisation (neutral.rs)
//!   aces2     ACES 2.0 output transform, analytic (aces2/)
//!   agx       AgX (Filament matrices, three.js sigmoid), SDR (agx.rs)
//!   standard  no tone curve: clip and encode only, SDR
//!   aces-legacy  three.js's ACES filmic fit, SDR, for old `.trd`s (legacy.rs)
//! Every view has an inverse; neutral, agx and aces-legacy are defined on linear Rec.709, so ACEScg is
//! converted with the crate's own matrices on the way in and out.
use crate::Rgb;
use crate::convert::gamut_matrix;
use std::sync::OnceLock;

mod aces2;
mod agx;
mod legacy;
mod neutral;
pub mod sksl;
mod target;

pub use sksl::Sksl;
pub use target::Target;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Kind {
    Neutral,
    Aces2,
    Agx,
    AcesLegacy,
    Standard,
}

#[derive(Debug)]
pub struct View {
    pub id: &'static str,
    /// The targets this view defines; anything else is a loud error.
    pub targets: &'static [Target],
    kind: Kind,
}

const VIEWS: &[View] = &[
    View { id: "neutral", targets: &Target::ALL, kind: Kind::Neutral },
    View { id: "aces2", targets: &Target::ALL, kind: Kind::Aces2 },
    View { id: "agx", targets: &[Target::Sdr], kind: Kind::Agx },
    View { id: "standard", targets: &[Target::Sdr], kind: Kind::Standard },
    View { id: "aces-legacy", targets: &[Target::Sdr], kind: Kind::AcesLegacy },
];

/// f32 3×3, row-major, applied as `M · v`.
pub(crate) type M3 = [[f32; 3]; 3];
pub(crate) const IDENTITY: M3 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]];

pub(crate) fn mul(m: &M3, v: Rgb) -> Rgb {
    m.map(|r| r[0] * v[0] + r[1] * v[1] + r[2] * v[2])
}

/// f32 3×3, column-major (GLSL `mat3`, as three.js, Filament and rostrum-3d spell their constants).
pub(crate) type M3c = [[f32; 3]; 3];

pub(crate) fn mulc(c: &M3c, v: Rgb) -> Rgb {
    [0, 1, 2].map(|i| c[0][i] * v[0] + c[1][i] * v[1] + c[2][i] * v[2])
}

/// The inverse (computed in f64), also column-major: inversion commutes with transposition.
pub(crate) fn inv_cols(m: &M3c) -> M3c {
    crate::matrix::inverse(&m.map(|r| r.map(|v| v as f64))).map(|r| r.map(|v| v as f32))
}

/// The crate's own matrices between ACEScg, linear Rec.709 and the targets' display gamuts.
pub(crate) struct Mats {
    pub cg_709: M3,
    pub r709_cg: M3,
    pub r709_2020: M3,
    pub r2020_709: M3,
}

pub(crate) fn mats() -> &'static Mats {
    static M: OnceLock<Mats> = OnceLock::new();
    M.get_or_init(|| {
        let m = |s, d| gamut_matrix(s, d).expect("built-in gamut").map(|r| r.map(|v| v as f32));
        Mats {
            cg_709: m("acescg", "lin_rec709"),
            r709_cg: m("lin_rec709", "acescg"),
            r709_2020: m("lin_rec709", "lin_rec2020"),
            r2020_709: m("lin_rec2020", "lin_rec709"),
        }
    })
}

impl View {
    pub fn get(id: &str) -> Option<&'static View> {
        VIEWS.iter().find(|v| v.id == id)
    }
    pub fn ids() -> impl Iterator<Item = &'static str> {
        VIEWS.iter().map(|v| v.id)
    }
    /// The view for a document setting, or a loud error: unknown id, or a target the view does not define
    /// (naming the views that do).
    pub fn resolve(id: &str, target: Target) -> Result<&'static View, String> {
        let v = View::get(id).ok_or_else(|| {
            format!("unknown view `{id}` (known: {})", View::ids().collect::<Vec<_>>().join(", "))
        })?;
        v.check(target).map(|_| v)
    }
    pub fn supports(&self, target: Target) -> bool {
        self.targets.contains(&target)
    }
    /// `Ok` when this view defines `target`; else the error naming the views that do.
    pub fn check(&self, target: Target) -> Result<(), String> {
        if self.supports(target) {
            return Ok(());
        }
        let ok: Vec<_> = VIEWS.iter().filter(|v| v.supports(target)).map(|v| v.id).collect();
        Err(format!("view `{}` has no `{}` target; views with one: {}", self.id, target.id(), ok.join(", ")))
    }
    fn must(&self, target: Target) {
        if let Err(e) = self.check(target) {
            panic!("{e}");
        }
    }
    /// ACEScg (scene linear) → display linear in `target`'s primaries. Panics on a target the view lacks
    /// (use `resolve` / `check` first).
    pub fn forward(&self, acescg: Rgb, target: Target) -> Rgb {
        self.must(target);
        self.fwd(acescg, target)
    }
    /// Display linear in `target`'s primaries → ACEScg.
    pub fn inverse(&self, display: Rgb, target: Target) -> Rgb {
        self.must(target);
        self.inv(display, target)
    }
    pub fn forward_all(&self, px: &mut [Rgb], target: Target) {
        self.must(target);
        px.iter_mut().for_each(|p| *p = self.fwd(*p, target));
    }
    pub fn inverse_all(&self, px: &mut [Rgb], target: Target) {
        self.must(target);
        px.iter_mut().for_each(|p| *p = self.inv(*p, target));
    }

    fn fwd(&self, c: Rgb, t: Target) -> Rgb {
        let m = mats();
        match self.kind {
            Kind::Neutral => neutral::forward(mul(&m.cg_709, c), t),
            Kind::Aces2 => aces2::Aces2::get(t).forward(c),
            Kind::Agx => agx::forward(mul(&m.cg_709, c)),
            Kind::AcesLegacy => legacy::forward(mul(&m.cg_709, c)),
            Kind::Standard => mul(&m.cg_709, c).map(|v| v.clamp(0.0, 1.0)),
        }
    }
    fn inv(&self, d: Rgb, t: Target) -> Rgb {
        let m = mats();
        match self.kind {
            Kind::Neutral => mul(&m.r709_cg, neutral::inverse(d, t)),
            Kind::Aces2 => aces2::Aces2::get(t).inverse(d),
            Kind::Agx => mul(&m.r709_cg, agx::inverse(d)),
            Kind::AcesLegacy => mul(&m.r709_cg, legacy::inverse(d)),
            Kind::Standard => mul(&m.r709_cg, d),
        }
    }
}

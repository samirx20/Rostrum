//! The gamut and colour-space registry. Ids follow ORACLE.md. Every gamut reaches the ACES white
//! (D60) through the CAT OCIO's ACES studio config uses for it, so any `src → dst` matrix goes through
//! that hub exactly as OCIO's reference space does.
use crate::matrix::{self, Cat, Mat3, Primaries};
use crate::tf::Curve;

pub const D65: [f64; 2] = [0.3127, 0.3290];
pub const ACES_WHITE: [f64; 2] = [0.32168, 0.33767];

/// A set of primaries plus how it adapts to the ACES white (`None` when it already is D60).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Gamut {
    pub id: &'static str,
    /// `None`: the gamut is CIE XYZ itself (under `white`).
    pub primaries: Option<Primaries>,
    pub white: [f64; 2],
    pub cat: Option<Cat>,
}

const fn g(id: &'static str, r: [f64; 2], gr: [f64; 2], b: [f64; 2], w: [f64; 2], cat: Option<Cat>) -> Gamut {
    Gamut { id, primaries: Some(Primaries { r, g: gr, b, w }), white: w, cat }
}
const BFD: Option<Cat> = Some(Cat::Bradford);
const C02: Option<Cat> = Some(Cat::Cat02);

/// The CAT per gamut is what OCIO's built-ins use (pinned by the golden `matrix.*` cases to 5e-9):
/// Bradford for display / working gamuts, RED and Panasonic; CAT02 for Sony, ARRI, Blackmagic and Canon.
pub const GAMUTS: &[Gamut] = &[
    g("aces2065", [0.7347, 0.2653], [0.0, 1.0], [0.0001, -0.077], ACES_WHITE, None), // SMPTE ST 2065-1
    g("acescg", [0.713, 0.293], [0.165, 0.830], [0.128, 0.044], ACES_WHITE, None), // Academy S-2014-004
    g("lin_rec709", [0.64, 0.33], [0.30, 0.60], [0.15, 0.06], D65, BFD), // BT.709-6
    g("lin_rec2020", [0.708, 0.292], [0.170, 0.797], [0.131, 0.046], D65, BFD), // BT.2020-2
    g("lin_p3d65", [0.680, 0.320], [0.265, 0.690], [0.150, 0.060], D65, BFD), // SMPTE EG 432-1
    Gamut { id: "xyz_d65", primaries: None, white: D65, cat: BFD },
    g("sgamut3", [0.730, 0.280], [0.140, 0.855], [0.100, -0.050], D65, C02), // Sony S-Log3 summary
    g("sgamut3cine", [0.766, 0.275], [0.225, 0.800], [0.089, -0.087], D65, C02),
    g("awg3", [0.6840, 0.3130], [0.2210, 0.8480], [0.0861, -0.1020], D65, C02), // ARRI LogC3 paper
    g("awg4", [0.7347, 0.2653], [0.1424, 0.8576], [0.0991, -0.0308], D65, C02), // ARRI LogC4 spec
    g("rwg", [0.780308, 0.304253], [0.121595, 1.493994], [0.095612, -0.084589], D65, BFD), // RED paper
    g("bmd_wg5", [0.717_721_5, 0.317_118_1], [0.228_041, 0.861_569], [0.100_584_1, -0.082_045_2],
      [0.312_717, 0.329_031_2], C02), // Blackmagic Gen 5 colour science
    g("cinema_gamut", [0.74, 0.27], [0.17, 1.14], [0.08, -0.10], D65, C02), // Canon Cinema Gamut
    g("vgamut", [0.730, 0.280], [0.165, 0.840], [0.100, -0.030], D65, BFD), // Panasonic V-Gamut
];

impl Gamut {
    pub fn get(id: &str) -> Option<&'static Gamut> {
        GAMUTS.iter().find(|g| g.id == id)
    }
    /// RGB → XYZ under this gamut's own white.
    pub fn to_xyz(&self) -> Mat3 {
        self.primaries.as_ref().map_or(matrix::IDENTITY, matrix::rgb_to_xyz)
    }
    /// RGB → XYZ under the ACES white (the hub every conversion passes through).
    pub fn to_hub(&self) -> Mat3 {
        match self.cat {
            Some(cat) => matrix::mul(&cat.adapt(self.white, ACES_WHITE), &self.to_xyz()),
            None => self.to_xyz(),
        }
    }
    /// The linear RGB matrix `self → dst`.
    pub fn matrix_to(&self, dst: &Gamut) -> Mat3 {
        matrix::mul(&matrix::inverse(&dst.to_hub()), &self.to_hub())
    }
}

/// A colour space: a gamut plus the curve its code values are in.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Space {
    pub id: &'static str,
    pub gamut: &'static str,
    pub curve: Curve,
}

const fn s(id: &'static str, gamut: &'static str, curve: Curve) -> Space {
    Space { id, gamut, curve }
}

/// Encoded spaces (OCIO's ACES studio config names in the comments). Every gamut id is also a linear space.
pub const SPACES: &[Space] = &[
    s("acescc", "acescg", Curve::AcesCc),                         // ACES - ACEScc
    s("acescct", "acescg", Curve::AcesCct),                       // ACES - ACEScct
    s("srgb_tex", "lin_rec709", Curve::Srgb),                     // sRGB Encoded Rec.709 (sRGB)
    s("rec709_display", "lin_rec709", Curve::Bt1886),             // Rec.1886 Rec.709 - Display
    s("rec1886_rec709", "lin_rec709", Curve::Bt1886),             // Rec.1886 Rec.709 - Display
    s("srgb_display", "lin_rec709", Curve::Srgb),                 // sRGB - Display
    s("p3d65_display", "lin_p3d65", Curve::Srgb),                 // Display P3 - Display
    s("st2084_p3d65_display", "lin_p3d65", Curve::Pq100),         // ST2084-P3-D65 - Display
    s("rec2100_pq", "lin_rec2020", Curve::Pq100),                 // Rec.2100-PQ - Display
    s("slog3_sgamut3", "sgamut3", Curve::SLog3),                  // S-Log3 S-Gamut3
    s("slog3_sgamut3cine", "sgamut3cine", Curve::SLog3),          // S-Log3 S-Gamut3.Cine
    s("logc3_awg3", "awg3", Curve::LogC3),                        // ARRI LogC3 (EI800)
    s("logc4_awg4", "awg4", Curve::LogC4),                        // ARRI LogC4
    s("log3g10_rwg", "rwg", Curve::Log3G10),                      // Log3G10 REDWideGamutRGB
    s("bmdfilm5_bmd_wg5", "bmd_wg5", Curve::BmdFilm5),             // BMDFilm WideGamut Gen5
    s("clog2_cinema_gamut", "cinema_gamut", Curve::CLog2),        // CanonLog2 CinemaGamut D55
    s("clog3_cinema_gamut", "cinema_gamut", Curve::CLog3),        // CanonLog3 CinemaGamut D55
    s("vlog_vgamut", "vgamut", Curve::VLog),                      // V-Log V-Gamut
    s("applelog_rec2020", "lin_rec2020", Curve::AppleLog),        // Apple Log (Rec.2020 primaries)
];

impl Space {
    /// An encoded space by id, or any gamut id as its linear space.
    pub fn get(id: &str) -> Option<Space> {
        SPACES.iter().copied().find(|s| s.id == id)
            .or_else(|| Gamut::get(id).map(|g| Space { id: g.id, gamut: g.id, curve: Curve::Linear }))
    }
    pub fn gamut(&self) -> &'static Gamut {
        Gamut::get(self.gamut).expect("registry spaces name registered gamuts")
    }
}

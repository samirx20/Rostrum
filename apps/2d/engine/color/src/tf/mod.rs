//! Transfer functions: `encode` is linear → code, `decode` is code → linear, per channel in f32 (maths
//! in f64). Out-of-range input follows OCIO's own behaviour (the golden vectors pin it down).
mod aces;
mod camera;
mod display;
mod sksl;

/// Every curve Rostrum knows. Ids are ORACLE.md's `tf.<id>` names.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Curve {
    Linear,
    Srgb,
    Rec709,
    Bt1886,
    /// ST 2084, linear 1.0 = 10 000 nits.
    Pq,
    /// ST 2084 for displays whose linear 1.0 = 100 nits (OCIO's `ST2084 - Display` spaces).
    Pq100,
    Hlg,
    AcesCc,
    AcesCct,
    SLog3,
    LogC3,
    LogC4,
    Log3G10,
    BmdFilm5,
    CLog2,
    CLog3,
    VLog,
    AppleLog,
}

type F = fn(f64) -> f64;

/// (curve, id, encode, decode): the one table everything dispatches through.
const TABLE: [(Curve, &str, F, F); 18] = [
    (Curve::Linear, "linear", |x| x, |x| x),
    (Curve::Srgb, "srgb", display::srgb_enc, display::srgb_dec),
    (Curve::Rec709, "rec709", display::rec709_enc, display::rec709_dec),
    (Curve::Bt1886, "bt1886", display::bt1886_enc, display::bt1886_dec),
    (Curve::Pq, "pq", display::pq_enc, display::pq_dec),
    (Curve::Pq100, "pq100", |x| display::pq_enc(x * 0.01), |y| display::pq_dec(y) * 100.0),
    (Curve::Hlg, "hlg", display::hlg_enc, display::hlg_dec),
    (Curve::AcesCc, "acescc", aces::acescc_enc, aces::acescc_dec),
    (Curve::AcesCct, "acescct", aces::acescct_enc, aces::acescct_dec),
    (Curve::SLog3, "slog3", camera::slog3_enc, camera::slog3_dec),
    (Curve::LogC3, "logc3", camera::logc3_enc, camera::logc3_dec),
    (Curve::LogC4, "logc4", camera::logc4_enc, camera::logc4_dec),
    (Curve::Log3G10, "log3g10", camera::log3g10_enc, camera::log3g10_dec),
    (Curve::BmdFilm5, "bmdfilm5", camera::bmdfilm5_enc, camera::bmdfilm5_dec),
    (Curve::CLog2, "clog2", camera::clog2_enc, camera::clog2_dec),
    (Curve::CLog3, "clog3", camera::clog3_enc, camera::clog3_dec),
    (Curve::VLog, "vlog", camera::vlog_enc, camera::vlog_dec),
    (Curve::AppleLog, "applelog", camera::applelog_enc, camera::applelog_dec),
];

impl Curve {
    fn row(self) -> &'static (Curve, &'static str, F, F) {
        TABLE.iter().find(|r| r.0 == self).expect("every curve has a row")
    }
    /// All curves, in table order.
    pub fn all() -> impl Iterator<Item = Curve> {
        TABLE.iter().map(|r| r.0)
    }
    pub fn id(self) -> &'static str {
        self.row().1
    }
    pub fn from_id(id: &str) -> Option<Curve> {
        TABLE.iter().find(|r| r.1 == id).map(|r| r.0)
    }
    /// Linear → code.
    pub fn encode(self, x: f32) -> f32 {
        (self.row().2)(x as f64) as f32
    }
    /// Code → linear.
    pub fn decode(self, y: f32) -> f32 {
        (self.row().3)(y as f64) as f32
    }
    pub(crate) fn encode64(self, x: f64) -> f64 {
        (self.row().2)(x)
    }
    pub(crate) fn decode64(self, y: f64) -> f64 {
        (self.row().3)(y)
    }
}

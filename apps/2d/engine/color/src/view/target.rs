//! The display a view renders for: peak, primaries, and the 10-bit code its error budgets use.
use crate::tf::Curve;

/// Where the view's display light goes.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Target {
    /// 100 nits peak, Rec.709 display primaries.
    Sdr,
    /// 1000 nits peak in a Rec.2020 container (graphics white 203 nits = 2.03).
    Hdr1000,
}

impl Target {
    pub const ALL: [Target; 2] = [Target::Sdr, Target::Hdr1000];
    pub fn id(self) -> &'static str {
        match self {
            Target::Sdr => "sdr",
            Target::Hdr1000 => "hdr1000",
        }
    }
    pub fn from_id(id: &str) -> Option<Target> {
        Target::ALL.into_iter().find(|t| t.id() == id)
    }
    /// Display-linear peak (1.0 = 100 nits).
    pub fn peak(self) -> f32 {
        match self {
            Target::Sdr => 1.0,
            Target::Hdr1000 => 10.0,
        }
    }
    /// The gamut id of the display-linear values (`spaces`).
    pub fn gamut(self) -> &'static str {
        match self {
            Target::Sdr => "lin_rec709",
            Target::Hdr1000 => "lin_rec2020",
        }
    }
    /// The 10-bit code curve the targets' error budgets are measured in (BT.1886 2.4, or PQ).
    pub fn curve(self) -> Curve {
        match self {
            Target::Sdr => Curve::Bt1886,
            Target::Hdr1000 => Curve::Pq100,
        }
    }
    /// Display linear half a 10-bit code below the peak: inverses that only approach the peak cap here.
    pub fn cap(self) -> f32 {
        let c = self.curve();
        c.decode(c.encode(self.peak()) - 0.5 / 1023.0)
    }
}

//! The mix bus' channel layouts (docs/NATIVE_ENGINE.md § Surround): stereo (the default), 5.1 and
//! 7.1. A layout is a table — channel names in file order (the WAVE_FORMAT_EXTENSIBLE mask order, so
//! the bed is written as it is held), each speaker's azimuth on the ring (degrees, negative left; 0 is
//! front centre; None for the LFE), its BS.1770 loudness weight and its WAV mask bit — read by the
//! panner, the effects, the master stage, the fold-downs and the writer. No stage assumes two channels.
//!
//! 5.1 is BS.2051 System B (0+5+0: L/R ±30°, C, LFE, Ls/Rs ±110°), mask 0x3F (FL FR FC LFE BL BR), the
//! layout AAC carries; 7.1 is System I (0+7+0: + sides ±90°, rears ±135°), mask 0x63F, whose file
//! order puts the rears (BL BR) before the sides (SL SR): L R C LFE Lrs Rrs Ls Rs.

pub mod binaural;
pub mod fold;
pub mod panner;

use serde::Deserialize;

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default, Deserialize)]
pub enum Layout {
    #[default]
    #[serde(rename = "stereo")]
    Stereo,
    #[serde(rename = "5.1")]
    Surround51,
    #[serde(rename = "7.1")]
    Surround71,
}

/// A channel: its name, its azimuth (None: the LFE) and its WAV mask bit.
pub struct Speaker {
    pub name: &'static str,
    pub az: Option<f64>,
    pub bit: u32,
}

const fn sp(name: &'static str, az: f64, bit: u32) -> Speaker {
    Speaker { name, az: Some(az), bit }
}
const LFE: Speaker = Speaker { name: "LFE", az: None, bit: 0x8 };

const STEREO: [Speaker; 2] = [sp("L", -30.0, 0x1), sp("R", 30.0, 0x2)];
const S51: [Speaker; 6] = [sp("L", -30.0, 0x1), sp("R", 30.0, 0x2), sp("C", 0.0, 0x4), LFE, sp("Ls", -110.0, 0x10), sp("Rs", 110.0, 0x20)];
const S71: [Speaker; 8] = [sp("L", -30.0, 0x1), sp("R", 30.0, 0x2), sp("C", 0.0, 0x4), LFE, sp("Lrs", -135.0, 0x10), sp("Rrs", 135.0, 0x20), sp("Ls", -90.0, 0x200), sp("Rs", 90.0, 0x400)];

impl Layout {
    pub fn speakers(self) -> &'static [Speaker] {
        match self {
            Layout::Stereo => &STEREO,
            Layout::Surround51 => &S51,
            Layout::Surround71 => &S71,
        }
    }
    pub fn channels(self) -> usize {
        self.speakers().len()
    }
    pub fn name(self) -> &'static str {
        match self {
            Layout::Stereo => "stereo",
            Layout::Surround51 => "5.1",
            Layout::Surround71 => "7.1",
        }
    }
    pub fn parse(s: &str) -> Result<Layout, String> {
        match s {
            "stereo" => Ok(Layout::Stereo),
            "5.1" => Ok(Layout::Surround51),
            "7.1" => Ok(Layout::Surround71),
            _ => Err(format!("unknown layout {s:?} (stereo, 5.1, 7.1)")),
        }
    }
    /// The layout a file of `channels` holds (the engine's own beds).
    pub fn of_channels(channels: usize) -> Result<Layout, String> {
        [Layout::Stereo, Layout::Surround51, Layout::Surround71].into_iter().find(|l| l.channels() == channels).ok_or(format!("{channels} channels is not a layout the engine writes (2, 6, 8)"))
    }
    pub fn mask(self) -> u32 {
        self.speakers().iter().map(|s| s.bit).sum()
    }
    pub fn lfe(self) -> Option<usize> {
        self.speakers().iter().position(|s| s.az.is_none())
    }
    /// BS.1770-4 channel weights: 1.41 (+1.5 dB) for speakers 60°–120° off centre, 0 for the LFE, else 1.
    pub fn weights(self) -> Vec<f64> {
        self.speakers().iter().map(|s| match s.az { None => 0.0, Some(a) if (60.0..=120.0).contains(&a.abs()) => 1.41, _ => 1.0 }).collect()
    }
    /// Left/right partner channels (ping-pong delays bounce inside a pair); the rest (C, LFE) are alone.
    pub fn pairs(self) -> Vec<(usize, usize)> {
        let sp = self.speakers();
        (0..sp.len()).filter_map(|i| { let a = sp[i].az?; (a < 0.0).then(|| sp.iter().position(|o| o.az == Some(-a)).map(|j| (i, j))).flatten() }).collect()
    }
}

/// The bed as slices, for the channel-generic stages.
pub fn slices(bed: &mut [Vec<f32>]) -> Vec<&mut [f32]> {
    bed.iter_mut().map(|c| c.as_mut_slice()).collect()
}

/// The fold-down matrix `to` × `from` (rows: output channels): ITU-R BS.775 — 5.1 → stereo
/// Lo = L + 0.7071 C + 0.7071 Ls (LFE dropped); 7.1 → 5.1 Ls = 0.7071 (Ls + Lrs), power-preserving;
/// 7.1 → stereo through 5.1. Other directions are an error (an upmix is not a fold-down).
pub fn downmix(from: Layout, to: Layout) -> Result<Vec<Vec<f64>>, String> {
    const H: f64 = std::f64::consts::FRAC_1_SQRT_2;
    let eye = |n: usize| (0..n).map(|i| (0..n).map(|j| if i == j { 1.0 } else { 0.0 }).collect()).collect::<Vec<Vec<f64>>>();
    let s51_st = vec![vec![1.0, 0.0, H, 0.0, H, 0.0], vec![0.0, 1.0, H, 0.0, 0.0, H]];
    let s71_51 = vec![
        vec![1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        vec![0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        vec![0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        vec![0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
        vec![0.0, 0.0, 0.0, 0.0, H, 0.0, H, 0.0],
        vec![0.0, 0.0, 0.0, 0.0, 0.0, H, 0.0, H],
    ];
    let mul = |a: &Vec<Vec<f64>>, b: &Vec<Vec<f64>>| a.iter().map(|row| (0..b[0].len()).map(|j| row.iter().enumerate().map(|(k, v)| v * b[k][j]).sum()).collect()).collect();
    Ok(match (from, to) {
        (f, t) if f == t => eye(f.channels()),
        (Layout::Surround51, Layout::Stereo) => s51_st,
        (Layout::Surround71, Layout::Surround51) => s71_51,
        (Layout::Surround71, Layout::Stereo) => mul(&s51_st, &s71_51),
        (f, t) => return Err(format!("no fold-down from {} to {} (a fold-down goes to fewer channels)", f.name(), t.name())),
    })
}

/// Applies a matrix to a bed.
pub fn apply(m: &[Vec<f64>], bed: &[Vec<f32>]) -> Vec<Vec<f32>> {
    let n = bed.first().map_or(0, |c| c.len());
    m.iter().map(|row| (0..n).map(|i| row.iter().zip(bed).map(|(g, c)| g * c[i] as f64).sum::<f64>() as f32).collect()).collect()
}

/// `rostrum-sound layouts`: the layout table, which TypeScript's surround.ts mirrors (a test compares them).
pub fn layouts_cmd() -> Result<(), String> {
    let all = [Layout::Stereo, Layout::Surround51, Layout::Surround71];
    println!("{}", serde_json::Value::Object(all.iter().map(|l| (l.name().to_string(), serde_json::json!(l.speakers().iter().map(|s| (s.name, s.az)).collect::<Vec<_>>()))).collect()));
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn layouts_are_written_in_mask_order_with_their_weights() {
        assert_eq!(Layout::Stereo.mask(), 0x3);
        assert_eq!(Layout::Surround51.mask(), 0x3F);
        assert_eq!(Layout::Surround71.mask(), 0x63F);
        for l in [Layout::Surround51, Layout::Surround71] {
            let bits: Vec<u32> = l.speakers().iter().map(|s| s.bit).collect();
            assert!(bits.windows(2).all(|w| w[0] < w[1]), "{bits:?}");
        }
        assert_eq!(Layout::Surround51.weights(), vec![1.0, 1.0, 1.0, 0.0, 1.41, 1.41]);
        assert_eq!(Layout::Surround71.weights(), vec![1.0, 1.0, 1.0, 0.0, 1.0, 1.0, 1.41, 1.41]);
        assert_eq!(Layout::Surround71.pairs(), vec![(0, 1), (4, 5), (6, 7)]);
        assert_eq!(Layout::Surround51.lfe(), Some(3));
    }

    #[test]
    fn the_itu_fold_downs_use_the_standard_coefficients() {
        let m = downmix(Layout::Surround51, Layout::Stereo).unwrap();
        assert_eq!(m[0], vec![1.0, 0.0, std::f64::consts::FRAC_1_SQRT_2, 0.0, std::f64::consts::FRAC_1_SQRT_2, 0.0]);
        let m = downmix(Layout::Surround71, Layout::Stereo).unwrap();
        // 7.1 → 5.1 → stereo: each surround at 0.5 into its side, the centre at 0.7071, no LFE.
        assert!((m[0][4] - 0.5).abs() < 1e-12 && (m[0][6] - 0.5).abs() < 1e-12 && m[0][3] == 0.0 && m[1][4] == 0.0);
        assert!(downmix(Layout::Stereo, Layout::Surround51).is_err());
    }
}

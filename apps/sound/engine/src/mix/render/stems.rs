//! The stems written: each kept track (and bus) read from its tape block by block, through the master's whole
//! gain (the very gain the mix took: fader, lane, fades, glue, loudness gain, limiter; mastergain.rs), so they add
//! up to the mix wherever the master's effects, reverb, time warps, a loop's wrap and the safety clip did not act.
//! Every file is written as it goes (the stems side by side, a core each) and measured as written: what the
//! hand-off says of a stem is the file's own loudness and peaks (the true peak: TruePeak, below). When the stems written hold everything that reaches
//! the master, their sum is checked against the mix on the way.

use std::path::PathBuf;

use super::stats::Mix;
use crate::analysis::loudness::{sample_peaks, Lufs};
use crate::mix::tape::{Tape, BLOCK};
use crate::mix::wavwriter::WavWriter;

/// Below this nothing is heard (−80 dBFS): a stem's last audible frame (the hand-off trims the silent end by it).
const AUDIBLE: f32 = 1e-4;

/// One stem to write: a bus or not, its name, its tape, its file.
pub struct StemFile<'a> {
    pub bus: bool,
    pub name: String,
    pub tape: &'a Tape,
    pub path: PathBuf,
}

/// A written stem's own figures.
pub struct StemMeter {
    pub lufs: f64,
    pub true_peak: f64,
    /// Sample peak (linear) and the samples past full scale (a float file holds them; a fixed-point copy would clip).
    pub peak: f64,
    pub over: usize,
    /// The frame after the last one above −80 dBFS (0: silent).
    pub last_audible: usize,
}

pub struct Written {
    pub meters: Vec<StemMeter>,
    /// The largest |sum of the stems − mix| over every sample, when the stems hold all that reaches the master.
    pub max_difference: Option<f64>,
}

/// A stem's true peak (4× oversampled, the costly measure), read block by block only on the stretches within 6 dB of
/// its loudest sample so far: a quieter stretch cannot hold its highest peak. Each sample's peak is taken with the 8
/// samples before and after it, so the value is the whole-signal measure's (analysis/loudness.rs sample_peaks).
struct TruePeak {
    /// The last frames of the blocks so far: `held` of them answered (the context before), the rest not yet.
    carry: Vec<Vec<f32>>,
    held: usize,
    loudest: f32,
    db: f64,
}

const TP_STRETCH: usize = 2048;
const TP_CONTEXT: usize = 8;

impl TruePeak {
    fn new(nch: usize) -> TruePeak {
        TruePeak { carry: vec![vec![]; nch], held: 0, loudest: 0.0, db: -120.0 }
    }

    /// The next block (`last`: the signal ends with it).
    fn push(&mut self, block: &[Vec<f32>], last: bool) {
        let j: Vec<Vec<f32>> = self.carry.iter().zip(block).map(|(c, b)| [c.as_slice(), b].concat()).collect();
        let len = j.first().map_or(0, Vec::len);
        let upto = if last { len } else { len.saturating_sub(TP_CONTEXT) };
        let top = |a: usize, b: usize| j.iter().fold(0.0f32, |m, c| c[a..b].iter().fold(m, |m, v| m.max(v.abs())));
        self.loudest = self.loudest.max(top(self.held.min(upto), upto));
        for s in (self.held..upto).step_by(TP_STRETCH) {
            let e = (s + TP_STRETCH).min(upto);
            if self.loudest < 1e-6 || top(s, e) < 0.5 * self.loudest {
                continue;
            }
            let (a, b) = (s.saturating_sub(TP_CONTEXT), (e + TP_CONTEXT).min(len));
            let p = sample_peaks(&j.iter().map(|c| &c[a..b]).collect::<Vec<_>>());
            self.db = self.db.max(20.0 * p[s - a..e - a].iter().fold(1e-9f64, |m, v| m.max(*v)).log10());
        }
        let keep = upto.saturating_sub(TP_CONTEXT);
        self.carry = j.iter().map(|c| c[keep..].to_vec()).collect();
        self.held = upto - keep;
    }
}

struct One {
    w: Option<WavWriter>,
    lufs: Option<Lufs>,
    tp: TruePeak,
    peak: f64,
    over: usize,
    last: usize,
}

/// Writes each stem, `mix.gain.total` frames long (from song frame `mix.gain.offset`: a range), at rate `sr`.
pub fn write(mix: &Mix, files: &[StemFile], sr: u32) -> Result<Written, String> {
    if files.is_empty() {
        return Ok(Written { meters: vec![], max_difference: None });
    }
    let gain = mix.gain.as_ref().ok_or("the mix has no master gain for its stems")?;
    let (total, weights) = (gain.total, mix.layout.weights());
    let covered = !mix.inputs.is_empty() && mix.inputs.iter().all(|(bus, name)| files.iter().any(|f| f.bus == *bus && &f.name == name));
    let summed: Vec<bool> = files.iter().map(|f| covered && mix.inputs.iter().any(|(bus, name)| f.bus == *bus && &f.name == name)).collect();
    let mut ones = files
        .iter()
        .map(|f| {
            let nch = f.tape.channels();
            Ok(One { w: Some(WavWriter::create(&f.path, nch, total, mix.layout, sr)?), lufs: Some(Lufs::new(nch, &weights, sr as f64)), tp: TruePeak::new(nch), peak: 0.0, over: 0, last: 0 })
        })
        .collect::<Result<Vec<_>, String>>()?;
    let mut diff = 0.0f64;
    for at in (0..total).step_by(BLOCK) {
        let n = BLOCK.min(total - at);
        let g = gain.stem_block(at, n)?;
        let jobs: Vec<(&mut One, &StemFile, bool)> = ones.iter_mut().zip(files).zip(&summed).map(|((o, f), s)| (o, f, *s)).collect();
        let blocks = crate::mix::par::map(jobs, |(o, f, keep)| -> Result<Option<Vec<Vec<f32>>>, String> {
            let mut block = f.tape.read(gain.offset + at, n)?;
            block.iter_mut().for_each(|c| c.iter_mut().zip(&g).for_each(|(v, g)| *v *= g));
            let refs: Vec<&[f32]> = block.iter().map(|c| c.as_slice()).collect();
            o.lufs.as_mut().expect("measuring").push(&refs);
            let mut loudest = 0.0f64;
            for i in 0..n {
                let top = block.iter().fold(0.0f32, |m, c| m.max(c[i].abs()));
                loudest = loudest.max(top as f64);
                o.over += block.iter().filter(|c| c[i].abs() > 1.0).count();
                if top > AUDIBLE {
                    o.last = at + i + 1;
                }
            }
            o.peak = o.peak.max(loudest);
            o.tp.push(&block, at + n == total);
            o.w.as_mut().expect("writing").write(&block)?;
            Ok(keep.then_some(block))
        });
        if covered {
            let mut sum: Option<Vec<Vec<f64>>> = None;
            for b in blocks.into_iter().collect::<Result<Vec<_>, String>>()?.into_iter().flatten() {
                let s = sum.get_or_insert_with(|| vec![vec![0.0; n]; b.len()]);
                s.iter_mut().zip(&b).for_each(|(s, c)| s.iter_mut().zip(c).for_each(|(s, v)| *s += *v as f64));
            }
            if let Some(sum) = sum {
                for (s, m) in sum.iter().zip(mix.read(at, n)?) {
                    diff = s.iter().zip(&m).fold(diff, |d, (s, m)| d.max((s - *m as f64).abs()));
                }
            }
        } else {
            blocks.into_iter().collect::<Result<Vec<_>, String>>()?;
        }
    }
    let mut meters = vec![];
    for o in ones.iter_mut() {
        o.w.take().expect("writing").finish()?;
        meters.push(StemMeter { lufs: o.lufs.take().expect("measuring").finish(), true_peak: o.tp.db, peak: o.peak, over: o.over, last_audible: o.last });
    }
    Ok(Written { meters, max_difference: covered.then_some(diff) })
}

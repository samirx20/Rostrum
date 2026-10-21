//! What a plugin is set to, as the document stores it (S4 follow-up): its saved state — the bytes the
//! plugin itself writes, carried in the document as base64 so a render is the same on any machine
//! whatever presets are installed — and its parameters, each a number or an envelope over song time
//! (the effect-envelope model, [[seconds, value], …]). Both plugin formats (clap/, vst3/)
//! read parameter changes from `Automation`: every value at the first block, then an envelope's
//! value every 32 samples whenever it moves, timed to the sample.

use crate::mix::schedule::Param;

const B64: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

pub fn base64(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len().div_ceil(3) * 4);
    for c in bytes.chunks(3) {
        let n = (c[0] as u32) << 16 | (*c.get(1).unwrap_or(&0) as u32) << 8 | *c.get(2).unwrap_or(&0) as u32;
        for k in 0..4 {
            out.push(if k <= c.len() { B64[(n >> (18 - 6 * k)) as usize & 63] as char } else { '=' });
        }
    }
    out
}

pub fn unbase64(s: &str) -> Result<Vec<u8>, String> {
    let mut out = Vec::with_capacity(s.len() / 4 * 3);
    let (mut acc, mut bits) = (0u32, 0u32);
    for ch in s.bytes().filter(|c| !c.is_ascii_whitespace() && *c != b'=') {
        let v = B64.iter().position(|&b| b == ch).ok_or("a plugin state is base64; it has other characters")? as u32;
        acc = acc << 6 | v;
        bits += 6;
        if bits >= 8 {
            bits -= 8;
            out.push((acc >> bits) as u8);
        }
    }
    Ok(out)
}

const STEP: usize = 32;

/// Parameter changes for a render that starts at song time `at` (seconds).
pub struct Automation<'a> {
    params: &'a [(u32, Param)],
    at: f64,
    sr: f64,
    last: Vec<Option<f64>>,
}

impl<'a> Automation<'a> {
    pub fn new(params: &'a [(u32, Param)], at: f64, sr: f64) -> Self {
        Automation { params, at, sr, last: vec![None; params.len()] }
    }

    /// The changes inside the block [pos, pos + n): (offset in the block, parameter id, value).
    pub fn block(&mut self, pos: usize, n: usize) -> Vec<(u32, u32, f64)> {
        let mut out = vec![];
        for (k, (id, p)) in self.params.iter().enumerate() {
            let offsets: Vec<usize> = match p {
                Param::Value(_) if self.last[k].is_some() => continue,
                Param::Value(_) => vec![0],
                Param::Envelope(_) => (0..n).filter(|o| (pos + o) % STEP == 0 || *o == 0).collect(),
            };
            for o in offsets {
                let v = p.at(self.at + (pos + o) as f64 / self.sr);
                if self.last[k] != Some(v) {
                    self.last[k] = Some(v);
                    out.push((o as u32, *id, v));
                }
            }
        }
        out.sort_by_key(|c| c.0);
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base64_round_trips_every_length() {
        for n in 0..10 {
            let b: Vec<u8> = (0..n as u8).map(|i| i.wrapping_mul(37).wrapping_add(200)).collect();
            assert_eq!(unbase64(&base64(&b)).unwrap(), b);
        }
        assert_eq!(base64(b"Rostrum"), "Um9zdHJ1bQ==");
        assert!(unbase64("no!").is_err());
    }

    #[test]
    fn constants_are_set_once_and_envelopes_follow_song_time_to_the_sample() {
        // A cutoff ramp 0.2 → 0.8 over 1 s of song, the clip starting at 0.5 s; a constant resonance.
        let params = vec![(7u32, Param::Envelope(vec![[0.0, 0.2], [1.0, 0.8]])), (9u32, Param::Value(0.3))];
        let mut a = Automation::new(&params, 0.5, 1000.0);
        let first = a.block(0, 64);
        let near = |c: (u32, u32, f64), o: u32, id: u32, v: f64| c.0 == o && c.1 == id && (c.2 - v).abs() < 1e-9;
        assert!(near(first[0], 0, 7, 0.5) && near(first[1], 0, 9, 0.3) && near(first[2], 32, 7, 0.2 + 0.6 * 0.532), "{first:?}");
        let second = a.block(64, 64);
        assert!(second.iter().all(|c| c.1 == 7), "the constant is not sent again");
        assert!(near(second[0], 0, 7, 0.2 + 0.6 * 0.564), "{second:?}");
        // Past the envelope's end it holds and nothing more is sent.
        let mut late = Automation::new(&params, 2.0, 1000.0);
        late.block(0, 64);
        assert!(late.block(64, 64).is_empty());
    }
}

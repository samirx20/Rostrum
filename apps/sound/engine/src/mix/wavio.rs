//! The engine's own files: 32-bit float WAV of a bed. Stereo is the plain IEEE-float format (as every
//! render before surround); more channels are WAVE_FORMAT_EXTENSIBLE with the layout's channel mask
//! (bed/), so players and ffmpeg place each channel on its speaker.

use crate::bed::Layout;

const FLOAT_GUID: [u8; 16] = [3, 0, 0, 0, 0, 0, 0x10, 0, 0x80, 0, 0, 0xaa, 0, 0x38, 0x9b, 0x71];

/// A bed as a float WAV.
pub fn write(chs: &[Vec<f32>], layout: Layout, sr: u32) -> Vec<u8> {
    let n = chs.first().map_or(0, |c| c.len());
    let mut w = header(chs.len(), n, layout, sr);
    w.reserve(n * chs.len() * 4);
    for i in 0..n {
        for c in chs {
            w.extend_from_slice(&c[i].to_le_bytes());
        }
    }
    w
}

/// The header of a float WAV of `nch` channels and `n` frames (wavwriter.rs streams the samples after it).
pub fn header(nch: usize, n: usize, layout: Layout, sr: u32) -> Vec<u8> {
    let nch = nch as u32;
    let data = (n * nch as usize * 4) as u32;
    let ext = nch > 2;
    let fmt_len: u32 = if ext { 40 } else { 16 };
    let mut w = Vec::with_capacity(28 + fmt_len as usize);
    w.extend_from_slice(b"RIFF");
    w.extend_from_slice(&(20 + fmt_len + data).to_le_bytes());
    w.extend_from_slice(b"WAVEfmt ");
    w.extend_from_slice(&fmt_len.to_le_bytes());
    w.extend_from_slice(&(if ext { 0xFFFEu16 } else { 3 }).to_le_bytes());
    w.extend_from_slice(&(nch as u16).to_le_bytes());
    w.extend_from_slice(&sr.to_le_bytes());
    w.extend_from_slice(&(sr * 4 * nch).to_le_bytes());
    w.extend_from_slice(&((4 * nch) as u16).to_le_bytes());
    w.extend_from_slice(&32u16.to_le_bytes());
    if ext {
        w.extend_from_slice(&22u16.to_le_bytes());
        w.extend_from_slice(&32u16.to_le_bytes());
        w.extend_from_slice(&layout.mask().to_le_bytes());
        w.extend_from_slice(&FLOAT_GUID);
    }
    w.extend_from_slice(b"data");
    w.extend_from_slice(&data.to_le_bytes());
    w
}

/// A mono float WAV (a microphone take): one channel has the plain header, no layout mask.
pub fn write_mono(x: &[f32], sr: u32) -> Vec<u8> {
    write(&[x.to_vec()], Layout::Stereo, sr)
}

/// A float WAV the engine wrote: its channels and rate.
pub fn read(path: &str) -> Result<(Vec<Vec<f32>>, f64), String> {
    let b = std::fs::read(path).map_err(|e| format!("{path}: {e}"))?;
    let u16_at = |i: usize| u16::from_le_bytes([b[i], b[i + 1]]);
    let u32_at = |i: usize| u32::from_le_bytes([b[i], b[i + 1], b[i + 2], b[i + 3]]);
    let bad = || format!("{path}: not a 32-bit float WAV written by the engine");
    if b.len() < 12 || &b[0..4] != b"RIFF" || &b[8..12] != b"WAVE" {
        return Err(bad());
    }
    let (mut o, mut fmt, mut data) = (12usize, None, None);
    while o + 8 <= b.len() {
        let len = u32_at(o + 4) as usize;
        match &b[o..o + 4] {
            b"fmt " => fmt = Some(o + 8),
            b"data" => data = Some((o + 8, len.min(b.len() - o - 8))),
            _ => {}
        }
        o += 8 + len + len % 2;
    }
    let (f, (d, len)) = (fmt.ok_or_else(bad)?, data.ok_or_else(bad)?);
    let float = u16_at(f) == 3 || (u16_at(f) == 0xFFFE && b[f + 24..f + 40] == FLOAT_GUID);
    if !float || u16_at(f + 14) != 32 {
        return Err(bad());
    }
    let (nch, sr) = (u16_at(f + 2) as usize, u32_at(f + 4) as f64);
    let frames = len / (4 * nch);
    let at = |k: usize| f32::from_le_bytes([b[d + k * 4], b[d + k * 4 + 1], b[d + k * 4 + 2], b[d + k * 4 + 3]]);
    Ok(((0..nch).map(|c| (0..frames).map(|i| at(i * nch + c)).collect()).collect(), sr))
}

/// Raw little-endian f32 samples (a PCM file the host decoded, weights).
pub fn f32_le(bytes: &[u8]) -> Vec<f32> {
    bytes.chunks_exact(4).map(|b| f32::from_le_bytes([b[0], b[1], b[2], b[3]])).collect()
}

/// A stereo float WAV the engine wrote (the render's own output): left, right, rate.
pub fn read_stereo(path: &str) -> Result<(Vec<f32>, Vec<f32>, f64), String> {
    let (mut chs, sr) = read(path)?;
    if chs.len() != 2 {
        return Err(format!("{path}: {} channels; inspect reads a stereo clip", chs.len()));
    }
    let r = chs.pop().unwrap_or_default();
    Ok((chs.pop().unwrap_or_default(), r, sr))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_bed_round_trips_and_stereo_keeps_the_plain_header() {
        let st = vec![vec![0.5f32, -0.25], vec![0.125, 1.0]];
        let w = write(&st, Layout::Stereo, 48000);
        assert_eq!(w.len(), 44 + 16, "the 44-byte header every reader of a stereo render expects");
        let p = std::env::temp_dir().join("rostrum-wavio-test.wav");
        let six: Vec<Vec<f32>> = (0..6).map(|c| vec![c as f32 * 0.1, -(c as f32) * 0.1]).collect();
        std::fs::write(&p, write(&six, Layout::Surround51, 48000)).unwrap();
        let (back, sr) = read(p.to_str().unwrap()).unwrap();
        assert_eq!((back, sr), (six, 48000.0));
        let b = std::fs::read(&p).unwrap();
        assert_eq!(u32::from_le_bytes([b[40], b[41], b[42], b[43]]), 0x3F, "the 5.1 channel mask");
    }

    #[test]
    fn mono_wav_header() {
        let w = write_mono(&[0.25, -0.25], 48000);
        assert_eq!(&w[..4], b"RIFF");
        assert_eq!(u16::from_le_bytes([w[22], w[23]]), 1);
        assert_eq!(u32::from_le_bytes([w[24], w[25], w[26], w[27]]), 48000);
        assert_eq!(u32::from_le_bytes([w[40], w[41], w[42], w[43]]), 8);
        assert_eq!(w.len(), 52);
    }
}

//! Ours against the `ebur128` crate (libebur128's port, MIT) on real clips and known signals: the table
//! behind docs/OSS_REUSE.md row 3 (printed with `cargo test ebur128_parity -- --nocapture`).
use super::loudness::{integrated_lufs_n, integrated_lufs_own, true_peak_db_n};
use super::loudstats::stats_n;
use ebur128::{EbuR128, Mode};

fn pcm_wav(path: &std::path::Path) -> Option<(Vec<Vec<f32>>, f64)> {
    let b = std::fs::read(path).ok()?;
    if b.len() < 44 || &b[0..4] != b"RIFF" {
        return None;
    }
    let (mut o, mut fmt, mut data) = (12usize, None, None);
    while o + 8 <= b.len() {
        let len = u32::from_le_bytes(b[o + 4..o + 8].try_into().ok()?) as usize;
        match &b[o..o + 4] {
            b"fmt " => fmt = Some(o + 8),
            b"data" => data = Some((o + 8, len.min(b.len() - o - 8))),
            _ => {}
        }
        o += 8 + len + len % 2;
    }
    let (f, (d, len)) = (fmt?, data?);
    let tag = u16::from_le_bytes([b[f], b[f + 1]]);
    let nch = u16::from_le_bytes([b[f + 2], b[f + 3]]) as usize;
    let sr = u32::from_le_bytes(b[f + 4..f + 8].try_into().ok()?) as f64;
    let bits = u16::from_le_bytes([b[f + 14], b[f + 15]]) as usize;
    if ![16, 24, 32].contains(&bits) || nch == 0 || nch > 2 || !(tag == 1 || tag == 3 || tag == 0xFFFE) {
        return None;
    }
    let bytes = bits / 8;
    let frames = len / (bytes * nch);
    let sample = |k: usize| -> f32 {
        let p = d + k * bytes;
        match bits {
            32 if tag == 3 || tag == 0xFFFE => f32::from_le_bytes(b[p..p + 4].try_into().unwrap()),
            16 => i16::from_le_bytes([b[p], b[p + 1]]) as f32 / 32768.0,
            24 => (i32::from_le_bytes([0, b[p], b[p + 1], b[p + 2]]) >> 8) as f32 / 8388608.0,
            _ => 0.0,
        }
    };
    Some(((0..nch).map(|c| (0..frames).map(|i| sample(i * nch + c)).collect()).collect(), sr))
}

fn walk(dir: &std::path::Path, out: &mut Vec<std::path::PathBuf>) {
    let Ok(rd) = std::fs::read_dir(dir) else { return };
    for e in rd.flatten() {
        let p = e.path();
        if p.is_dir() {
            walk(&p, out);
        } else if p.extension().is_some_and(|x| x == "wav") && e.metadata().map(|m| m.len() > 150_000).unwrap_or(false) {
            out.push(p);
        }
    }
}

/// Integrated, max momentary, max short-term, LRA, true peak: ours then ebur128's.
fn measure(chs: &[Vec<f32>], weights: &[f64], sr: f64) -> ([f64; 5], [f64; 5]) {
    let refs: Vec<&[f32]> = chs.iter().map(|c| c.as_slice()).collect();
    let st = stats_n(&refs, weights, sr);
    let swapped = integrated_lufs_n(&refs, weights, sr);
    assert!((swapped - integrated_lufs_own(&refs, weights, sr)).abs() < 1e-6, "integrated_lufs_n (ebur128) against our own");
    let ours = [integrated_lufs_own(&refs, weights, sr), st.max_momentary, st.max_short_term, st.lra, true_peak_db_n(&refs)];
    let mut e = EbuR128::new(chs.len() as u32, sr as u32, Mode::I | Mode::S | Mode::M | Mode::LRA | Mode::TRUE_PEAK).unwrap();
    let (mut mm, mut ms) = (f64::NEG_INFINITY, f64::NEG_INFINITY);
    let hop = (sr * 0.1) as usize;
    let n = chs[0].len();
    for s in (0..n).step_by(hop) {
        let end = (s + hop).min(n);
        let planar: Vec<&[f32]> = chs.iter().map(|c| &c[s..end]).collect();
        e.add_frames_planar_f32(&planar).unwrap();
        if end - s == hop {
            mm = mm.max(e.loudness_momentary().unwrap());
            if end >= (sr * 3.0) as usize {
                ms = ms.max(e.loudness_shortterm().unwrap());
            }
        }
    }
    let tp = (0..chs.len()).map(|c| e.true_peak(c as u32).unwrap()).fold(0.0, f64::max);
    (ours, [e.loudness_global().unwrap(), mm, ms, e.loudness_range().unwrap(), 20.0 * tp.max(1e-9).log10()])
}

/// Pink-ish noise (Voss-McCartney, 8 rows) from a splitmix64 stream, `level` peak-ish.
fn noise(n: usize, seed: u64, level: f32) -> Vec<f32> {
    let mut s = seed;
    let mut next = move || {
        s = s.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = s;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        ((z ^ (z >> 31)) as f64 / u64::MAX as f64) * 2.0 - 1.0
    };
    let mut rows = [0.0f64; 8];
    (0..n)
        .map(|i| {
            for (k, r) in rows.iter_mut().enumerate() {
                if i % (1 << k) == 0 {
                    *r = next();
                }
            }
            (rows.iter().sum::<f64>() / 8.0 * 2.0) as f32 * level
        })
        .collect()
}

#[test]
fn ebur128_parity_table() {
    let mut clips: Vec<(String, Vec<Vec<f32>>, f64, Vec<f64>)> = vec![];
    let root = std::path::PathBuf::from(std::env::var("USERPROFILE").unwrap_or_default()).join(".rostrum/assets/sounds");
    for d in ["bigcat-cello", "drawbar-organ", "dsmolken-bass", "studio-kit", "vsco2-strings", "salamander-piano", "growlybass", "kenney-impact", "bigsoundbank", "muldjord-kit", "vcsl-sax", "wurlitzer", "freepats-guitar", "owlish"] {
        let mut v = vec![];
        walk(&root.join(d), &mut v);
        v.sort();
        let Some(p) = v.get(v.len() / 2).cloned() else { continue };
        if let Some((c, sr)) = pcm_wav(&p) {
            let w = vec![1.0; c.len()];
            clips.push((p.strip_prefix(&root).unwrap().to_string_lossy().replace('\\', "/"), c, sr, w));
        }
    }
    let sr = 48000.0;
    let tone: Vec<f32> = (0..(sr as usize * 12)).map(|i| (2.0 * std::f64::consts::PI * 997.0 * i as f64 / sr).sin() as f32 * 0.1).collect();
    clips.push(("sine 997 Hz -20 dBFS stereo 12 s".into(), vec![tone.clone(), tone], sr, vec![1.0; 2]));
    clips.push(("pink noise stereo 20 s".into(), (0..2).map(|c| noise(sr as usize * 20, 5 + c, 0.12)).collect(), sr, vec![1.0; 2]));
    clips.push(("pink noise stereo 15 s, 44.1 kHz".into(), (0..2).map(|c| noise(44100 * 15, 9 + c, 0.3)).collect(), 44100.0, vec![1.0; 2]));
    let scenes: Vec<f32> = noise(sr as usize * 40, 77, 1.0).iter().enumerate().map(|(i, v)| v * if (i / (sr as usize * 10)) % 2 == 0 { 0.02 } else { 0.25 }).collect();
    clips.push(("pink noise, 10 s quiet / 10 s loud x2 (LRA)".into(), vec![scenes.clone(), scenes], sr, vec![1.0; 2]));
    let bed: Vec<Vec<f32>> = [0.10, 0.10, 0.14, 0.2, 0.06, 0.06].iter().enumerate().map(|(c, l)| noise(sr as usize * 15, 20 + c as u64, *l)).collect();
    clips.push(("5.1 noise (L R C LFE Ls Rs) 15 s".into(), bed, sr, crate::bed::Layout::Surround51.weights()));
    println!("\n| clip | rate | measure | ours | ebur128 | diff |\n|---|---|---|---|---|---|");
    let names = ["integrated LUFS", "max momentary LUFS", "max short-term LUFS", "LRA LU", "true peak dBTP"];
    let mut worst = [0.0f64; 5];
    for (name, chs, sr, w) in &clips {
        let (ours, theirs) = measure(chs, w, *sr);
        for k in 0..5 {
            let (a, b) = (ours[k], theirs[k]);
            let d = if a.is_finite() && b.is_finite() { a - b } else { f64::NAN };
            if d.is_finite() {
                worst[k] = worst[k].max(d.abs());
            }
            println!("| {name} | {sr} | {} | {a:.2} | {b:.2} | {d:+.3} |", names[k]);
        }
    }
    println!("WORST |diff| per measure: {:?}", names.iter().zip(worst).collect::<Vec<_>>());
}

//! Binaural: the bed as heard over headphones — each speaker a virtual source, convolved with the
//! head-related impulse responses of its direction (both ears), the ears summed. The HRIRs are the
//! SADIE II database's KEMAR (subject D2; University of York, Apache-2.0: data/SADIE-II-NOTICE.txt),
//! at the bed's speaker directions on the horizontal plane (0°, ±30°, ±90°, ±110°, ±135°) and
//! 44.1 / 48 / 96 kHz, energy-normalised so the front pair averages unit energy
//! (data/hrir_sadie2_d2.bin, 74 KB, built from the WAV release). The LFE reaches both ears at its
//! +10 dB playback gain, as from a subwoofer.

use crate::bed::Layout;

static DATA: &[u8] = include_bytes!("../../data/hrir_sadie2_d2.bin");

/// Left- and right-ear responses of one direction (degrees, negative left).
struct Hrir {
    az: f64,
    ears: [Vec<f64>; 2],
}

fn set(rate: u32) -> Result<Vec<Hrir>, String> {
    let u32_at = |o: usize| u32::from_le_bytes([DATA[o], DATA[o + 1], DATA[o + 2], DATA[o + 3]]);
    let f32_at = |o: usize| f32::from_le_bytes([DATA[o], DATA[o + 1], DATA[o + 2], DATA[o + 3]]) as f64;
    let mut o = 8;
    let mut rates = vec![];
    while o + 12 <= DATA.len() {
        let (r, taps, count) = (u32_at(o), u32_at(o + 4) as usize, u32_at(o + 8) as usize);
        o += 12;
        if r == rate {
            return Ok((0..count)
                .map(|k| {
                    let at = o + k * (4 + taps * 8);
                    Hrir { az: f32_at(at), ears: [0, 1].map(|e| (0..taps).map(|i| f32_at(at + 4 + (e * taps + i) * 4)).collect()) }
                })
                .collect());
        }
        rates.push(r);
        o += count * (4 + taps * 8);
    }
    Err(format!("binaural renders at {rates:?} Hz (the HRIR set's rates); this mix is at {rate} Hz"))
}

/// The bed folded to two ears.
pub fn render(bed: &[Vec<f32>], layout: Layout, sr: f64) -> Result<[Vec<f32>; 2], String> {
    let hrirs = set(sr as u32)?;
    let n = bed.first().map_or(0, |c| c.len());
    let mut ears = [vec![0.0f64; n], vec![0.0f64; n]];
    for (c, s) in layout.speakers().iter().enumerate() {
        match s.az {
            None => {
                // The LFE: +10 dB in band, at both ears alike.
                for e in ears.iter_mut() {
                    for i in 0..n {
                        e[i] += bed[c][i] as f64 * 3.1623;
                    }
                }
            }
            Some(az) => {
                let h = hrirs.iter().find(|h| (h.az - az).abs() < 0.5).ok_or(format!("no HRIR at {az}°"))?;
                for (e, ir) in ears.iter_mut().zip(&h.ears) {
                    for (i, v) in crate::fx::convolve::convolve(&bed[c], ir).into_iter().enumerate() {
                        e[i] += v;
                    }
                }
            }
        }
    }
    Ok(ears.map(|e| e.into_iter().map(|v| v as f32).collect()))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn a_left_speaker_is_louder_in_the_left_ear_and_every_rate_loads() {
        for rate in [44100, 48000, 96000] {
            assert_eq!(set(rate).unwrap().len(), 9);
        }
        assert!(set(22050).is_err());
        let n = 4800;
        let mut seed = 0x2545F4914F6CDD1Du64;
        let noise: Vec<f32> = (0..n).map(|_| { seed ^= seed << 13; seed ^= seed >> 7; seed ^= seed << 17; (seed as f64 / u64::MAX as f64 * 2.0 - 1.0) as f32 }).collect();
        let mut bed = vec![vec![0.0f32; n]; 6];
        bed[4] = noise.clone(); // Ls, −110°
        let [l, r] = render(&bed, Layout::Surround51, 48000.0).unwrap();
        let e = |x: &[f32]| x.iter().map(|v| (*v as f64).powi(2)).sum::<f64>();
        assert!(e(&l) > 4.0 * e(&r), "Ls is heard on the left: {} vs {}", e(&l), e(&r));
        // The front centre reaches both ears alike, at about the input's energy.
        let mut bed = vec![vec![0.0f32; n]; 6];
        bed[2] = noise.clone();
        let [l, r] = render(&bed, Layout::Surround51, 48000.0).unwrap();
        let ratio = e(&l) / e(&r);
        assert!((0.7..1.4).contains(&ratio), "{ratio}");
        let gain = (e(&l) + e(&r)) / 2.0 / e(&noise);
        assert!((0.25..4.0).contains(&gain), "{gain}");
    }
}

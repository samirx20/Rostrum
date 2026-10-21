//! A mix as the live output plays it (transport.rs): interleaved frames of `channels` channels whose
//! speakers are the WAVE channel-mask bits `mask` (stereo 0x3, a 5.1 bed 0x3F, 7.1 0x63F), so the
//! stream can place each channel on the device's own speaker (monitor.rs channel_map).

#[derive(Clone, Debug, PartialEq)]
pub struct Frames {
    pub channels: usize,
    pub mask: u32,
    /// `channels` samples per frame, interleaved.
    pub data: Vec<f32>,
}

impl Frames {
    /// Channel buffers (one per speaker, in mask order) as frames.
    pub fn from_channels(chs: &[Vec<f32>], mask: u32) -> Frames {
        let n = chs.iter().map(Vec::len).min().unwrap_or(0);
        let mut data = Vec::with_capacity(n * chs.len());
        for i in 0..n {
            data.extend(chs.iter().map(|c| c[i]));
        }
        Frames { channels: chs.len().max(1), mask, data }
    }

    pub fn stereo(frames: &[[f32; 2]]) -> Frames {
        Frames { channels: 2, mask: 0x3, data: frames.iter().flatten().copied().collect() }
    }

    /// Frames (not samples).
    pub fn len(&self) -> usize {
        self.data.len() / self.channels
    }

    pub fn frame(&self, i: usize) -> Option<&[f32]> {
        self.data.get(i * self.channels..(i + 1) * self.channels)
    }
}

/// A mix decoded at `from` Hz, played at `to` Hz (band-limited sinc, each channel alike: rubato's
/// asynchronous resampler with an anti-alias cutoff, so content above the new Nyquist is filtered out
/// instead of folding back), when the device will not run at the mix's rate (transport::resample is
/// this on stereo frames). The output is `floor(len * to / from)` frames, the delay trimmed.
pub fn resample(mix: &Frames, from: f64, to: f64) -> Frames {
    let (ch, len) = (mix.channels, mix.len());
    if from == to || len == 0 {
        return mix.clone();
    }
    let n = (len as f64 * to / from).floor() as usize;
    let data = match sinc(mix, from, to, n) {
        Some(d) => d,
        None => cubic(mix, from, to).data,
    };
    Frames { channels: ch, mask: mix.mask, data }
}

fn sinc(mix: &Frames, from: f64, to: f64, n: usize) -> Option<Vec<f32>> {
    use audioadapter_buffers::owned::InterleavedOwned;
    use rubato::{calculate_cutoff, Async, FixedAsync, Resampler, SincInterpolationParameters, SincInterpolationType, WindowFunction};
    let (ch, len) = (mix.channels, mix.len());
    let window = WindowFunction::BlackmanHarris2;
    let params = SincInterpolationParameters { sinc_len: 128, f_cutoff: Some(calculate_cutoff(128, window)), oversampling_factor: 256, interpolation: SincInterpolationType::Cubic, window };
    let mut r = Async::<f32>::new_sinc(to / from, 1.1, &params, 1024, ch, FixedAsync::Input).ok()?;
    let input = InterleavedOwned::<f32>::new_from(mix.data.clone(), ch, len).ok()?;
    let mut data = r.process_all(&input, len, None).ok()?.take_data();
    data.resize(n * ch, 0.0);
    Some(data)
}

/// The cubic interpolation the live resampler used before rubato (no low-pass: it aliases); the
/// fallback if rubato refuses a ratio, and the reference the alias test measures against.
fn cubic(mix: &Frames, from: f64, to: f64) -> Frames {
    let (ch, len) = (mix.channels, mix.len());
    let n = (len as f64 * to / from).floor() as usize;
    let at = |i: isize, c: usize| mix.data[i.clamp(0, len as isize - 1) as usize * ch + c];
    let mut data = Vec::with_capacity(n * ch);
    for k in 0..n {
        let x = k as f64 * from / to;
        let i = x.floor() as isize;
        let f = (x - i as f64) as f32;
        for c in 0..ch {
            let (a, b, cc, d) = (at(i - 1, c), at(i, c), at(i + 1, c), at(i + 2, c));
            data.push(b + 0.5 * f * (cc - a + f * (2.0 * a - 5.0 * b + 4.0 * cc - d + f * (3.0 * (b - cc) + d - a))));
        }
    }
    Frames { channels: ch, mask: mix.mask, data }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stereo_resampling_matches_the_transports_bit_for_bit() {
        let src: Vec<[f32; 2]> = (0..4410).map(|k| [((k as f32) * 0.013).sin(), ((k as f32) * 0.021).cos()]).collect();
        let a = crate::live::transport::resample(&src, 44100.0, 48000.0);
        let b = resample(&Frames::stereo(&src), 44100.0, 48000.0);
        assert_eq!(Frames::stereo(&a), b);
    }

    /// RMS (dBFS) of channel 0 between `a` and `b` seconds.
    fn rms_db(f: &Frames, rate: f64, a: f64, b: f64) -> f64 {
        let v: Vec<f64> = (0..f.len()).filter(|i| (*i as f64 / rate) >= a && (*i as f64 / rate) < b).map(|i| f.data[i * f.channels] as f64).collect();
        20.0 * (v.iter().map(|x| x * x).sum::<f64>() / v.len() as f64).sqrt().max(1e-12).log10()
    }

    /// A 48 kHz sweep 1 -> 23.5 kHz over 1 s, played at 44.1 kHz: past 0.9378 s the sweep is above the new
    /// Nyquist (22.05 kHz), so everything there in the output is alias. Prints the figures (README).
    #[test]
    fn a_sweep_above_the_new_nyquist_does_not_alias() {
        let (from, to) = (48000.0, 44100.0);
        let n = 48000;
        let x: Vec<f32> = (0..n).map(|i| { let t = i as f64 / from; (2.0 * std::f64::consts::PI * (1000.0 * t + 0.5 * 22500.0 * t * t)).sin() as f32 * 0.5 }).collect();
        let src = Frames { channels: 1, mask: 0x4, data: x };
        let (new, old) = (resample(&src, from, to), cubic(&src, from, to));
        let (pass_new, pass_old) = (rms_db(&new, to, 0.5, 0.6), rms_db(&old, to, 0.5, 0.6));
        let (alias_new, alias_old) = (rms_db(&new, to, 0.96, 0.985), rms_db(&old, to, 0.96, 0.985));
        println!("ALIAS passband at 12 kHz: input {:.1}, cubic {pass_old:.1}, sinc {pass_new:.1} dBFS; alias band (input above 22.05 kHz): cubic {alias_old:.1} dBFS, sinc {alias_new:.1} dBFS ({:.1} dB lower)", rms_db(&src, from, 0.5, 0.6), alias_old - alias_new);
        let input_db = rms_db(&src, from, 0.5, 0.6);
        assert!((pass_new - input_db).abs() < 0.3, "the passband keeps its level: {input_db:.1} -> {pass_new:.1}");
        assert!(alias_new < alias_old - 20.0, "alias: {alias_old:.1} -> {alias_new:.1}");
        assert_eq!(new.len(), (n as f64 * to / from) as usize);
    }

    #[test]
    fn a_bed_keeps_its_channels_and_mask() {
        let chs: Vec<Vec<f32>> = (0..6).map(|c| vec![c as f32; 2000]).collect();
        let f = Frames::from_channels(&chs, 0x3F);
        assert_eq!((f.len(), f.channels), (2000, 6));
        assert_eq!(f.frame(3).unwrap(), &[0.0, 1.0, 2.0, 3.0, 4.0, 5.0]);
        let r = resample(&f, 1000.0, 2000.0);
        assert_eq!((r.len(), r.mask), (4000, 0x3F));
        assert!(r.frame(2000).unwrap().iter().enumerate().all(|(c, v)| (*v - c as f32).abs() < 1e-3));
    }
}

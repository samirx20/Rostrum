//! Texture and ambience beds: vinyl (sparse crackle and pops over a very low, dark hiss — never a
//! noise floor), rain (a soft dark wash whose intensity drifts, with random droplets), room tone
//! and a café (murmur, the odd cup). Events come from a seeded generator: the same every render.

use std::f64::consts::PI;

use super::{Rng, Svf};

pub const PRESETS: &[&str] = &["vinyl", "rain", "room", "cafe"];

/// A short decaying event: a sine (droplet, clink) or a noise burst (crackle, pop).
struct Event { left: f64, right: f64, amp: f64, decay: f64, freq: f64, phase: f64, noise: bool }

/// Starts an event at `rate` per second on average.
fn spawn(ev: &mut Rng, events: &mut Vec<Event>, sr: f64, rate: f64, make: &mut dyn FnMut(&mut Rng) -> Event) {
    if ev.u() < rate / sr && events.len() < 32 {
        let e = make(ev);
        events.push(e);
    }
}

/// Renders the bed (one of PRESETS) for `dur` seconds, faded in and out over 150 ms; calls `out(i, left, right)`.
pub fn render(preset: &str, dur: f64, sr: f64, mut out: impl FnMut(usize, f64, f64)) {
    let len = (dur * sr).floor() as usize;
    let (mut nl, mut nr, mut ev) = (Rng(0x9e37_79b9_7f4a_7c15), Rng(0xd1b5_4a32_d192_ed03), Rng(0x2545_f491_4f6c_dd1d));
    let mut f = [Svf::default(); 8];
    let mut events: Vec<Event> = Vec::with_capacity(32);
    // Café voices: three formant-ish bands moving slowly, each with its own syllable rhythm.
    let mut talk = [(500.0f64, 0.0f64, 4.0f64); 3];
    for i in 0..len {
        let t = i as f64 / sr;
        let fade = (t / 0.15).min(1.0) * ((dur - t) / 0.15).clamp(0.0, 1.0);
        let (a, b) = (nl.n(), nr.n());
        let (mut l, mut r) = match preset {
            "vinyl" => {
                // Hiss about −50 dBFS, dark (300 Hz … 2.5 kHz): heard in the gaps, under the music.
                let (_, hl, _) = f[0].run(a, 1100.0, 1.6, sr);
                let (_, hr, _) = f[1].run(b, 1150.0, 1.6, sr);
                // Crackle: ~7 small ticks a second (most faint, a few loud), and a soft pop every couple of seconds.
                spawn(&mut ev, &mut events, sr, 7.0, &mut |g: &mut Rng| { let p = g.n() * 0.5; Event { left: 1.0 - p, right: 1.0 + p, amp: 0.025 + 0.22 * g.u().powi(5), decay: 0.00025 + 0.0004 * g.u(), freq: 0.0, phase: 0.0, noise: true } });
                spawn(&mut ev, &mut events, sr, 0.45, &mut |g: &mut Rng| Event { left: 1.0, right: 1.0, amp: 0.05 + 0.06 * g.u(), decay: 0.003, freq: 150.0 + 120.0 * g.u(), phase: 0.0, noise: false });
                (hl * 0.012, hr * 0.012)
            }
            "rain" => {
                // A dark wash whose intensity drifts, and droplets (more when it is heavier).
                let k = 0.75 + 0.15 * (2.0 * PI * 0.07 * t).sin() + 0.1 * (2.0 * PI * 0.19 * t + 1.0).sin();
                let (wl, _, _) = f[0].run(a, 2200.0, 1.2, sr);
                let (wr, _, _) = f[1].run(b, 2100.0, 1.2, sr);
                let (_, _, wl) = f[2].run(wl, 180.0, 1.2, sr);
                let (_, _, wr) = f[3].run(wr, 180.0, 1.2, sr);
                spawn(&mut ev, &mut events, sr, 45.0 * k, &mut |g: &mut Rng| { let p = g.n(); Event { left: 1.0 - p * 0.8, right: 1.0 + p * 0.8, amp: 0.008 + 0.05 * g.u().powi(3), decay: 0.002 + 0.006 * g.u(), freq: 1400.0 + 3600.0 * g.u(), phase: 0.0, noise: false } });
                (wl * 0.16 * k, wr * 0.16 * k)
            }
            "room" => {
                // Room tone: a soft low rumble and air, nothing that draws the ear.
                let (ll, _, _) = f[0].run(a, 300.0, 1.4, sr);
                let (lr, _, _) = f[1].run(b, 320.0, 1.4, sr);
                let (_, al, _) = f[2].run(a, 1500.0, 2.0, sr);
                let (_, ar, _) = f[3].run(b, 1500.0, 2.0, sr);
                (ll * 0.06 + al * 0.004, lr * 0.06 + ar * 0.004)
            }
            _ => {
                // Café: murmur (band-passed noise in speech bands, gated by syllables, moving slowly) and the odd cup.
                let (mut ml, mut mr) = (0.0, 0.0);
                for (k, v) in talk.iter_mut().enumerate() {
                    if ev.u() < 1.5 / sr {
                        *v = (350.0 + 1600.0 * ev.u(), v.1, 3.0 + 3.0 * ev.u());
                    }
                    v.1 += v.2 / sr;
                    let syl = (0.5 + 0.5 * (2.0 * PI * v.1).sin()).powi(2);
                    let (_, bl, _) = f[2 + k].run(if k % 2 == 0 { a } else { b }, v.0, 0.9, sr);
                    let pan = (k as f64 - 1.0) * 0.5;
                    ml += bl * syl * (1.0 - pan);
                    mr += bl * syl * (1.0 + pan);
                }
                let (bed, _, _) = f[0].run(a + b, 600.0, 1.4, sr);
                spawn(&mut ev, &mut events, sr, 0.3, &mut |g: &mut Rng| { let p = g.n() * 0.6; Event { left: 1.0 - p, right: 1.0 + p, amp: 0.012 + 0.02 * g.u(), decay: 0.12, freq: 2400.0 + 1800.0 * g.u(), phase: 0.0, noise: false } });
                (ml * 0.05 + bed * 0.03, mr * 0.05 + bed * 0.03)
            }
        };
        // The events, summed and aged.
        let (mut el, mut er) = (0.0, 0.0);
        for e in events.iter_mut() {
            let s = if e.noise { nl.n() } else {
                e.phase += 2.0 * PI * e.freq / sr;
                e.freq *= 1.0 - 0.6 / sr; // a droplet's pitch sinks a little
                e.phase.sin()
            };
            el += s * e.amp * e.left;
            er += s * e.amp * e.right;
            e.amp *= (-1.0 / (e.decay * sr)).exp();
        }
        events.retain(|e| e.amp > 1e-5);
        if preset == "vinyl" {
            // Crackle is bright but brief: through a gentle high-pass so it ticks rather than thumps (pops are separate, low).
            let (_, _, hl) = f[6].run(el, 700.0, 1.4, sr);
            let (_, _, hr) = f[7].run(er, 700.0, 1.4, sr);
            el = hl;
            er = hr;
        }
        l += el;
        r += er;
        out(i, l * fade, r * fade);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn take(p: &str, secs: f64) -> Vec<f64> {
        let mut x = vec![0.0; (secs * 44100.0) as usize];
        render(p, secs, 44100.0, |i, l, _| x[i] = l);
        x
    }

    #[test]
    fn vinyl_is_sparse_crackle_over_a_quiet_hiss_not_static() {
        let x = take("vinyl", 6.0);
        // The floor (the median 10 ms window) sits near −50 dBFS; the crackle is a few loud, brief ticks.
        let mut win: Vec<f64> = x.chunks(441).map(|c| (c.iter().map(|v| v * v).sum::<f64>() / c.len() as f64).sqrt()).collect();
        win.sort_by(|a, b| a.partial_cmp(b).unwrap());
        let floor = 20.0 * win[win.len() / 2].log10();
        assert!(floor < -44.0 && floor > -60.0, "floor {floor}");
        // 5 ms windows with a tick in them: sparse (a static floor would light every one).
        let ticks = x.chunks(220).filter(|c| c.iter().any(|v| v.abs() >= 0.01)).count();
        assert!(ticks > 10 && ticks < 150, "ticks {ticks} of {}", x.len() / 220);
        assert_eq!(x, take("vinyl", 6.0));
    }

    #[test]
    fn rain_drifts_and_every_bed_is_bounded() {
        for p in PRESETS {
            let x = take(p, 4.0);
            assert!(x.iter().all(|v| v.is_finite() && v.abs() < 1.0), "{p}");
            let rms = (x.iter().map(|v| v * v).sum::<f64>() / x.len() as f64).sqrt();
            assert!(rms > 1e-4, "{p} silent");
        }
    }
}

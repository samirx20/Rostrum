//! The instrument on the audio thread: each block applies the events that arrived, then sums every
//! sounding voice (and the fading stolen ones) into the output; `heard` reports each note-on's latency.

use super::{Event, Instrument, Kind, Report};

impl crate::live::wasapi::Source for Instrument {
    fn fill(&mut self, out: &mut [f32], start: u64) {
        while let Ok(e) = self.events.try_recv() {
            match e {
                Event::On { key, velocity, at } => {
                    self.on(key, velocity, start);
                    self.pending.push((key, at, crate::live::wasapi::now()));
                }
                Event::Off { key } => self.off(key, start),
            }
        }
        let frames = out.len() / 2;
        if let Kind::Layers(layers) = &mut self.kind {
            for l in layers.iter_mut() {
                l.fill(out, start);
            }
        }
        if let Kind::Plugin(p) = &mut self.kind {
            if let Err(what) = p.fill(out) {
                let _ = self.reports.send(Report::Failed { what });
            }
        }
        if let Kind::Sampler(synth, _) = &mut self.kind {
            let (l, r) = &mut self.scratch;
            l.resize(frames, 0.0);
            r.resize(frames, 0.0);
            synth.render(l, r);
            for i in 0..frames {
                out[i * 2] += l[i];
                out[i * 2 + 1] += r[i];
            }
        }
        let mut finished = vec![];
        for (k, p) in self.playing.iter_mut().enumerate() {
            for f in 0..frames {
                let Some((l, r)) = p.tick() else {
                    finished.push(k);
                    break;
                };
                out[f * 2] += l as f32;
                out[f * 2 + 1] += r as f32;
            }
        }
        for k in finished.into_iter().rev() {
            self.playing.remove(k);
        }
        let full = (0.005 * self.rate).max(1.0) as f32;
        for (p, left) in self.stolen.iter_mut() {
            for f in 0..frames {
                let Some((l, r)) = p.tick().filter(|_| *left > 0) else {
                    *left = 0;
                    break;
                };
                let g = *left as f32 / full;
                *left -= 1;
                out[f * 2] += l as f32 * g;
                out[f * 2 + 1] += r as f32 * g;
            }
        }
        self.stolen.retain(|(_, left)| *left > 0);
        for s in out.iter_mut() {
            *s *= self.volume;
        }
    }

    fn heard(&mut self, _start: u64, at: f64) {
        for (key, event, picked) in self.pending.drain(..) {
            let _ = self.reports.send(Report::Heard { key, latency: at - event, queue: picked - event });
        }
    }
}

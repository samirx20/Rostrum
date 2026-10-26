//! Keys pressed and released: a voice started (a synth note, a sampler key, an SFZ strike with legato
//! and round robin, a kit hit, each layer's), the oldest stolen past MAX_VOICES; released, its release.

use super::{Instrument, KitVoice, Kind, Playing, Report, MAX_VOICES};
use crate::instruments::synth::SynthVoice;

impl Instrument {
    pub(super) fn on(&mut self, key: u8, velocity: f64, frame: u64) {
        self.down.retain(|d| d.0 != key);
        self.down.push((key, velocity, frame));
        let freq = 440.0 * 2f64.powf((key as f64 - 69.0) / 12.0);
        match &mut self.kind {
            Kind::Synth(spec) => {
                // Seeded as a score seeds the note recorded at this frame (an analog voice's drift, phases and
                // noise): unseeded, every live note started at seed 0's phases and its bounce sounded different.
                let voice = SynthVoice::new(spec, freq, f64::INFINITY, velocity, 0.0, self.rate).seeded(crate::instruments::synth::note_seed(frame, freq));
                // A gliding synth slides from the last note played.
                let voice = match self.last_freq {
                    Some(from) => voice.gliding_from(from, freq),
                    None => voice,
                };
                self.playing.push(Playing::Synth { key, voice, i: 0, held: true });
            }
            Kind::Sampler(synth, ch) => synth.note_on(*ch, key as i32, (velocity * 127.0).round().clamp(1.0, 127.0) as i32),
            Kind::Plugin(p) => p.on(key, velocity),
            Kind::Sfz(regions, samples, legato, struck, offset) => {
                let nth = struck.entry(key).or_insert(0);
                // Legato: a key struck while another is held takes over from it in a crossfade.
                let over = *legato && self.playing.iter().any(|p| matches!(p, Playing::Sfz { voice, .. } if voice.held()));
                if over {
                    for p in self.playing.iter_mut() {
                        if let Playing::Sfz { voice, .. } = p {
                            voice.release((crate::instruments::sfz::LEGATO_FADE * self.rate) as usize, Some(crate::instruments::sfz::LEGATO_FADE));
                        }
                    }
                }
                let voices = crate::instruments::sfz::strike(regions, samples, (key as i16 + *offset as i16).clamp(0, 127) as u8, velocity, *nth, over, self.rate);
                *nth += 1;
                if voices.is_empty() {
                    let _ = self.reports.send(Report::Ignored { key });
                }
                self.playing.extend(voices.into_iter().map(|voice| Playing::Sfz { key, voice }));
            }
            Kind::Layers(layers) => {
                for l in layers.iter_mut() {
                    l.on(key, velocity, frame, self.rate);
                }
            }
            Kind::Drums(keys, kit) => match keys.get(&key.to_string()) {
                Some(name) => {
                    let mut out = vec![];
                    let k = kit.get(name).cloned().unwrap_or(KitVoice { tune: 1.0, decay: 1.0, level: 1.0, sample: None, sample_rate: None, model: None });
                    // A one-shot decoded at its own rate is read faster or slower to sound at its pitch on this device.
                    let tune = if k.sample.is_some() { k.tune * k.sample_rate.unwrap_or(self.rate) / self.rate } else { k.tune };
                    let hit = crate::mix::schedule::Voice::Drum { voice: name.clone(), start_idx: 0, velocity: velocity * k.level, pan: 0.0, tune, decay: k.decay, sample: k.sample, model: k.model };
                    if let Err(e) = crate::instruments::voices::Voice::from_schedule(&hit, usize::MAX, self.rate, &mut out) {
                        let _ = self.reports.send(Report::Failed { what: e });
                    }
                    self.playing.extend(out.into_iter().map(|voice| Playing::Drum { voice, i: 0 }));
                }
                None => {
                    let _ = self.reports.send(Report::Ignored { key });
                }
            },
        }
        self.last_freq = Some(freq);
        // Too many voices: the oldest released (else the oldest) fades out in 5 ms.
        while self.playing.len() > MAX_VOICES {
            let idx = self.playing.iter().position(|p| !p.held()).unwrap_or(0);
            let fade = (0.005 * self.rate) as u32;
            self.stolen.push((self.playing.remove(idx), fade));
        }
    }

    pub(super) fn off(&mut self, key: u8, frame: u64) {
        if let Some(at) = self.down.iter().position(|d| d.0 == key) {
            let (key, velocity, start) = self.down.remove(at);
            let _ = self.reports.send(Report::Note { key, velocity, start, end: frame });
        }
        match &mut self.kind {
            Kind::Synth(_) => {
                for p in self.playing.iter_mut() {
                    if let Playing::Synth { key: k, voice, i, held } = p {
                        if *k == key && *held {
                            voice.release(*i);
                            *held = false;
                        }
                    }
                }
            }
            Kind::Sampler(synth, ch) => synth.note_off(*ch, key as i32),
            Kind::Plugin(p) => p.off(key),
            Kind::Sfz(..) => {
                for p in self.playing.iter_mut() {
                    if let Playing::Sfz { key: k, voice } = p {
                        if *k == key {
                            voice.release(0, None);
                        }
                    }
                }
            }
            Kind::Layers(layers) => {
                for l in layers.iter_mut() {
                    l.off(key, frame, self.rate);
                }
            }
            Kind::Drums(..) => {}
        }
    }

    /// Voices sounding (a layered instrument: its layers' voices).
    #[cfg(test)]
    pub fn voices(&self) -> usize {
        self.playing.len() + self.stolen.len() + if let Kind::Layers(ls) = &self.kind { ls.iter().map(|l| l.voices()).sum() } else { 0 }
    }
}

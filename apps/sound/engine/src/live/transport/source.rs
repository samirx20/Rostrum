//! The transport on the live output (live/wasapi/ `Source`): each block takes the commands and notes
//! that came in, plays the mix (or the count-in), the metronome and the instrument, and says when it
//! is heard.

use super::{Out, Transport, CLICK};
use crate::live::instrument::Event;

impl crate::live::wasapi::Source for Transport {
    fn channels(&self) -> usize {
        self.mix.channels
    }

    fn mask(&self) -> u32 {
        self.mix.mask
    }

    fn fill(&mut self, out: &mut [f32], start: u64) {
        while let Ok(c) = self.cmds.try_recv() {
            self.command(c);
        }
        let rolling = self.playing.then(|| self.t());
        while let Ok(e) = self.notes.try_recv() {
            match e {
                Event::On { key, velocity, .. } => {
                    if let (Some(t), Some(_)) = (rolling, self.armed) {
                        self.held.retain(|h| h.0 != key);
                        self.held.push((key, velocity, t));
                    }
                }
                Event::Off { key } => {
                    if let Some(i) = self.held.iter().position(|h| h.0 == key) {
                        let (key, velocity, s) = self.held.remove(i);
                        self.note(key, velocity, s, rolling.unwrap_or(s));
                    }
                }
            }
            if let Some((_, tx)) = &self.inst {
                let _ = tx.send(e);
            }
        }
        self.blocks.push_back((start, rolling));
        if self.blocks.len() > 64 {
            self.blocks.pop_front();
        }
        let ch = self.mix.channels;
        let frames = out.len() / ch;
        let click_len = (CLICK * self.rate) as usize;
        for f in 0..frames {
            let k = start as usize + f;
            if self.count_in > 0 {
                // The count-in: the bar's clicks, then the mix rolls from where it stands.
                if (self.count_in_total - self.count_in) as f64 >= (self.count_beat as f64 * self.beat).round() {
                    self.click = Some((k, self.count_beat % self.per_bar as usize == 0));
                    self.count_beat += 1;
                }
                self.count_in -= 1;
                if self.count_in == 0 {
                    self.playing = true;
                    let _ = self.out.send(Out::Rolling(self.t()));
                }
            } else if self.playing {
                if let Some(s) = self.mix.frame(self.pos) {
                    for (o, v) in out[f * ch..(f + 1) * ch].iter_mut().zip(s) {
                        *o += v;
                    }
                }
                let b = self.beat_of(self.pos as f64);
                if b != self.last_beat {
                    self.last_beat = b;
                    if self.metronome {
                        self.click = Some((k, b.rem_euclid(self.per_bar as i64) == 0));
                    }
                }
                self.pos += 1;
                match self.looped {
                    Some((a, b)) if self.pos == b => {
                        self.end_held(b as f64 / self.rate);
                        self.pos = a;
                        self.last_beat = self.beat_of(a as f64 - 0.5);
                        let _ = self.out.send(Out::Wrapped);
                    }
                    _ if self.pos >= self.mix.len() => {
                        self.end_held(self.t());
                        self.playing = false;
                        let _ = self.out.send(Out::End);
                    }
                    _ => {}
                }
            }
            if let Some((at, _)) = self.click {
                if k >= at + click_len {
                    self.click = None;
                } else {
                    // The click and the instrument play on the front pair (L / R).
                    let c = self.click(k);
                    out[f * ch] += c;
                    out[f * ch + 1] += c;
                }
            }
        }
        if let Some((inst, _)) = &mut self.inst {
            self.scratch.clear();
            self.scratch.resize(frames * 2, 0.0);
            inst.fill(&mut self.scratch, start);
            for (f, s) in self.scratch.chunks_exact(2).enumerate() {
                out[f * ch] += s[0];
                out[f * ch + 1] += s[1];
            }
        }
    }

    fn heard(&mut self, start: u64, at: f64) {
        if let Some((inst, _)) = &mut self.inst {
            inst.heard(start, at);
        }
        if let Some(&(_, t)) = self.blocks.iter().rev().find(|b| b.0 == start) {
            let _ = self.out.send(Out::Clock { at, t });
        }
    }
}

//! The transport: a whole rendered mix played in real time on the live output (wasapi/), with
//! play / stop / seek / loop, a metronome and count-in, and a live instrument playing along. What
//! plays is the exported file itself (the engine's render, read back), so audition ≡ export. Notes
//! played while recording are taken at the mix time that sounded with them (the same output block)
//! — overdub — and kept inside a punch range when one is set. After each block the transport says
//! when that block is heard and which mix time it holds (`Out::Clock`), so a play-head readout and
//! a microphone take (record.rs packets carry the same clock) line up with what was heard.

use std::sync::mpsc::{Receiver, Sender};
use std::sync::Arc;

mod clock;
mod source;
#[cfg(test)]
mod tests;

pub use clock::{resample, Clock};

use crate::live::frames::Frames;
use crate::live::instrument::{Event, Instrument};

#[derive(Clone, Debug, PartialEq)]
pub enum Cmd {
    Play(Option<f64>),
    Stop,
    Seek(f64),
    Loop(Option<(f64, f64)>),
    Metronome(bool),
    CountIn(u32),
    /// Arm recording (with a punch range in mix seconds), or disarm.
    Record(Option<Option<(f64, f64)>>),
    /// A new render of the mix (an edit elsewhere): playback carries on from where it is.
    Load(Arc<Frames>),
}

#[derive(Debug, PartialEq)]
pub enum Out {
    /// The block holding mix time `t` (seconds; None when not rolling) reaches the speaker at `at` (QPC seconds).
    Clock { at: f64, t: Option<f64> },
    /// A recorded note: key, velocity and its span in mix seconds.
    Note { key: u8, velocity: f64, start: f64, end: f64 },
    /// Playback ran to the end (not looping) and stopped there.
    End,
    /// The loop came round (from its end to its start): a pass ended.
    Wrapped,
    /// The count-in finished and the mix began rolling at `t`.
    Rolling(f64),
}

pub struct Transport {
    /// The mix as monitored (monitor.rs): stereo, or a surround bed channel for channel.
    mix: Arc<Frames>,
    rate: f64,
    pos: usize,
    playing: bool,
    looped: Option<(usize, usize)>,
    metronome: bool,
    beat: f64,
    /// The song's beats in frames when its tempo changes (TypeScript's tempo map, src/core/tempoMap.ts); empty: every `beat` frames.
    beat_frames: Vec<usize>,
    per_bar: u32,
    /// Frames of count-in left; the click it plays.
    count_in: usize,
    count_in_total: usize,
    count_in_bars: u32,
    count_beat: usize,
    click: Option<(usize, bool)>,
    last_beat: i64,
    /// Armed: Some(punch).
    armed: Option<Option<(f64, f64)>>,
    /// Keys down that are being recorded: (key, velocity, mix start).
    held: Vec<(u8, f64, f64)>,
    inst: Option<(Instrument, Sender<Event>)>,
    scratch: Vec<f32>,
    cmds: Receiver<Cmd>,
    notes: Receiver<Event>,
    out: Sender<Out>,
    /// (stream frame, mix time) of recent blocks, for `heard`.
    blocks: std::collections::VecDeque<(u64, Option<f64>)>,
}

const CLICK: f64 = 0.03;

impl Transport {
    #[allow(clippy::too_many_arguments)]
    pub fn new(mix: Arc<Frames>, rate: u32, bpm: f64, per_bar: u32, inst: Option<(Instrument, Sender<Event>)>, cmds: Receiver<Cmd>, notes: Receiver<Event>, out: Sender<Out>) -> Transport {
        Transport {
            mix, rate: rate as f64, pos: 0, playing: false, looped: None, metronome: false, beat: 60.0 / bpm.max(20.0) * rate as f64, beat_frames: vec![], per_bar: per_bar.max(1), count_in: 0, count_in_total: 0, count_in_bars: 0, count_beat: 0, click: None, last_beat: -1,
            armed: None, held: vec![], inst, scratch: vec![], cmds, notes, out, blocks: Default::default(),
        }
    }

    /// Beat times (seconds) for a song whose tempo changes: the metronome clicks on them.
    pub fn with_beats(mut self, seconds: &[f64]) -> Transport {
        self.beat_frames = seconds.iter().map(|s| (s * self.rate).round() as usize).collect();
        self
    }

    /// Which beat (from 0) a frame falls in.
    fn beat_of(&self, pos: f64) -> i64 {
        if self.beat_frames.is_empty() { (pos / self.beat).floor() as i64 } else { self.beat_frames.partition_point(|&f| f as f64 <= pos) as i64 - 1 }
    }

    fn t(&self) -> f64 {
        self.pos as f64 / self.rate
    }

    fn frame(&self, t: f64) -> usize {
        ((t.max(0.0) * self.rate).round() as usize).min(self.mix.len())
    }

    /// Keys still down end where the recording stops (a stop, a seek, a pass of the loop).
    fn end_held(&mut self, at: f64) {
        for (key, velocity, start) in std::mem::take(&mut self.held) {
            self.note(key, velocity, start, at);
        }
    }

    fn note(&mut self, key: u8, velocity: f64, start: f64, end: f64) {
        let (from, to) = self.armed.flatten().unwrap_or((f64::MIN, f64::MAX));
        if start >= from && start < to {
            let _ = self.out.send(Out::Note { key, velocity, start, end: end.min(to).max(start) });
        }
    }

    fn command(&mut self, c: Cmd) {
        match c {
            Cmd::Play(from) => {
                if let Some(t) = from {
                    self.pos = self.frame(t);
                } else if self.pos >= self.mix.len() {
                    self.pos = 0;
                }
                self.last_beat = self.beat_of(self.pos as f64 - 0.5);
                self.count_in = (self.count_in_bars as f64 * self.per_bar as f64 * self.beat).round() as usize;
                self.count_in_total = self.count_in;
                self.count_beat = 0;
                self.playing = self.count_in == 0;
                if self.playing {
                    let _ = self.out.send(Out::Rolling(self.t()));
                }
            }
            Cmd::Stop => {
                self.end_held(self.t());
                self.playing = false;
                self.count_in = 0;
            }
            Cmd::Seek(t) => {
                self.end_held(self.t());
                self.pos = self.frame(t);
                self.last_beat = self.beat_of(self.pos as f64 - 0.5);
            }
            Cmd::Loop(l) => self.looped = l.map(|(a, b)| (self.frame(a), self.frame(b))).filter(|(a, b)| b > a),
            Cmd::Metronome(on) => self.metronome = on,
            Cmd::CountIn(bars) => self.count_in_bars = bars,
            Cmd::Record(r) => {
                if r.is_none() {
                    self.end_held(self.t());
                }
                self.armed = r;
            }
            // (The stream's channels are set when it opens: play.rs loads a mix monitored the same way.)
            Cmd::Load(mix) if mix.channels == self.mix.channels => {
                self.mix = mix;
                self.pos = self.pos.min(self.mix.len());
            }
            Cmd::Load(_) => {}
        }
    }

    fn click(&self, k: usize) -> f32 {
        match self.click {
            Some((at, accent)) if k >= at => {
                let t = (k - at) as f64 / self.rate;
                let f = if accent { 1760.0 } else { 1320.0 };
                ((2.0 * std::f64::consts::PI * f * t).sin() * (-t * 90.0).exp() * if accent { 0.35 } else { 0.22 }) as f32
            }
            _ => 0.0,
        }
    }
}

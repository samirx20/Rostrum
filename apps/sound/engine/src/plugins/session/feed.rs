//! The plugin heard while a person tweaks it: the activated processor played on the live output,
//! notes from stdin / MIDI, an effect's input looped.

use std::sync::mpsc::{Receiver, Sender};
use std::sync::{Arc, Mutex};

use super::{Note, Proc};
use crate::live::instrument::Event;
/// Plays the activated plugin on the live output: notes from stdin / MIDI, an effect's input looped.
pub(super) struct Feed {
    pub(super) slot: Arc<Mutex<Option<Box<dyn Proc>>>>,
    pub(super) notes: Receiver<Event>,
    pub(super) input: Arc<Vec<[f32; 2]>>,
    pub(super) pos: usize,
    pub(super) bufs: [Vec<f32>; 4],
    pub(super) pending: Vec<f64>,
    pub(super) heard: Sender<f64>,
    pub(super) errors: Sender<String>,
}

impl crate::live::wasapi::Source for Feed {
    fn fill(&mut self, out: &mut [f32], _start: u64) {
        let frames = out.len() / 2;
        let mut notes: Vec<Note> = vec![];
        while let Ok(e) = self.notes.try_recv() {
            match e {
                Event::On { key, velocity, at } => {
                    notes.push((0, key, velocity.max(1e-3)));
                    self.pending.push(at);
                }
                Event::Off { key } => notes.push((0, key, 0.0)),
            }
        }
        for b in self.bufs.iter_mut() {
            b.clear();
            b.resize(frames, 0.0);
        }
        let [il, ir, ol, or] = &mut self.bufs;
        if !self.input.is_empty() {
            for f in 0..frames {
                let s = self.input[self.pos];
                (il[f], ir[f]) = (s[0], s[1]);
                self.pos = (self.pos + 1) % self.input.len();
            }
        }
        let Ok(mut slot) = self.slot.lock() else { return };
        let Some(p) = slot.as_mut() else { return };
        if let Err(e) = p.process((il, ir), (ol, or), &notes) {
            let _ = self.errors.send(e);
            *slot = None;
            return;
        }
        for f in 0..frames {
            out[f * 2] += ol[f];
            out[f * 2 + 1] += or[f];
        }
    }

    fn heard(&mut self, _start: u64, at: f64) {
        for e in self.pending.drain(..) {
            let _ = self.heard.send(at - e);
        }
    }
}

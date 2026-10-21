//! Hearing yourself (input monitoring): the microphone's packets (record.rs) mixed into the transport's
//! output (transport/source.rs), off until asked (`{"hear": true}` on play.rs's stdin). The packets come
//! from the microphone thread over a bounded channel; the audio thread keeps a short queue and reads it at
//! the output's rate (linear steps when the two devices' rates differ). The queue is held short (`KEEP`):
//! when the microphone runs ahead of the output, the oldest samples go, so what you hear stays close
//! behind what you play instead of drifting later. Off, the queue is emptied every block.

use std::collections::VecDeque;
use std::sync::mpsc::{Receiver, SyncSender};

/// The longest the queue may grow before its oldest samples go, and what it is cut back to (seconds).
const MOST: f64 = 0.04;
const KEEP: f64 = 0.015;

pub struct Hear {
    rx: Receiver<Vec<f32>>,
    queue: VecDeque<f32>,
    /// Microphone samples per output frame.
    step: f64,
    phase: f64,
    mic_rate: f64,
    pub gain: f32,
}

/// The microphone side: hands a packet over (dropped when the audio thread is behind; never blocks).
pub fn send(tx: &SyncSender<Vec<f32>>, samples: &[f32]) {
    let _ = tx.try_send(samples.to_vec());
}

impl Hear {
    pub fn new(rx: Receiver<Vec<f32>>) -> Hear {
        Hear { rx, queue: VecDeque::new(), step: 1.0, phase: 0.0, mic_rate: 48000.0, gain: 0.0 }
    }

    /// The two devices' rates (once both are open).
    pub fn rates(&mut self, mic: f64, out: f64) {
        self.mic_rate = mic;
        self.step = mic / out.max(1.0);
    }

    /// At the start of a block: take the packets that came in, keep the queue short.
    pub fn pull(&mut self) {
        while let Ok(p) = self.rx.try_recv() {
            if self.gain > 0.0 {
                self.queue.extend(p);
            }
        }
        if self.gain <= 0.0 {
            self.queue.clear();
            return;
        }
        if self.queue.len() as f64 > MOST * self.mic_rate {
            let cut = self.queue.len() - (KEEP * self.mic_rate) as usize;
            self.queue.drain(..cut);
        }
    }

    /// The next output frame's sample (0 when off or the queue ran dry).
    pub fn next(&mut self) -> f32 {
        if self.gain <= 0.0 || self.queue.len() < 2 {
            return 0.0;
        }
        let (a, b) = (self.queue[0], self.queue[1]);
        let v = a + (b - a) * self.phase as f32;
        self.phase += self.step;
        let whole = self.phase.floor();
        self.phase -= whole;
        self.queue.drain(..(whole as usize).min(self.queue.len()));
        v * self.gain
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn off_is_silent_and_on_plays_the_input_without_drifting_late() {
        let (tx, rx) = std::sync::mpsc::sync_channel(64);
        let mut h = Hear::new(rx);
        h.rates(48000.0, 48000.0);
        send(&tx, &[0.5; 480]);
        h.pull();
        assert_eq!(h.next(), 0.0, "off by default");
        h.gain = 1.0;
        for _ in 0..10 {
            send(&tx, &[0.5; 480]); // 100 ms arrive at once: the queue is cut back to KEEP
        }
        h.pull();
        assert!(h.queue.len() <= (KEEP * 48000.0) as usize + 1);
        assert!((h.next() - 0.5).abs() < 1e-6);
    }
}

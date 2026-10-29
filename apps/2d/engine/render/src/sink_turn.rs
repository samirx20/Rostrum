//! One encoder shared by an export's drawing workers (export_crew.rs): each worker's sink (sink.rs `Sink::turn`)
//! hands its frames here, and a frame goes into the encoder only when every frame before it has, so the encoder
//! still gets every frame once, in frame order. Every frame is put through the output step on its worker's thread (sink.rs
//! `Pixels::converted`; a frame from the GPU's output step already is), and one that comes early is held until its turn, so a worker drawing quick frames goes on
//! while another draws a slow one (a 128-sample motion-blurred frame held up every worker: Night Bloom's busy
//! seconds and the export-speed bench spent more time waiting here than painting). A worker waits only when its frame
//! is WINDOW or more frames after the next one due (memory stays bounded: at most WINDOW frames held, 8 MB each at
//! 1080p, 8-bit). `stop` (a worker failed) wakes every waiter with that failure, so no worker waits for a frame that
//! will never come.
//!
//! An export's segment cuts (scene_export.rs `saves`): when the frame before a cut has gone in, a save mark follows it
//! (sink.rs `mark_save`), so the kept encoder finishes that segment's file while the frames after it go on coming.

use std::collections::{BTreeMap, HashMap};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Condvar, Mutex};
use std::time::Instant;

use crate::sink::{Pixels, Sink};

/// How many frames past the next one due may be held for the encoder (the lowest frame not in is always taken).
pub const WINDOW: usize = 16;

pub struct Turn {
    state: Mutex<State>,
    cv: Condvar,
    /// Its encoder takes NV12: each worker converts its frame before its turn (sink.rs `for_encoder`).
    nv12: bool,
    /// Microseconds, summed over the workers: converting frames, waiting for their turn (WINDOW), handing them to the
    /// encoder (its queue full: the encoder behind). The export's reply says them (`timing.turn`).
    spent: [AtomicU64; 3],
}

struct State {
    sink: Sink,
    /// Every frame's export position, by its document number, and how many have gone in.
    pos: HashMap<u32, usize>,
    next: usize,
    /// Frames that came before their turn, converted, by export position.
    held: BTreeMap<usize, Pixels>,
    stop: Option<String>,
    /// The files to save, by the export position they end at (the frames before it go in that file).
    saves: HashMap<usize, String>,
}

impl Turn {
    /// The export's encoder, taking frames numbered `order` (export order); `saves`: a file saved when the frames before
    /// that export position are in.
    pub fn new(sink: Sink, order: Vec<u32>, saves: HashMap<usize, String>) -> Arc<Turn> {
        let pos = order.iter().enumerate().map(|(p, &i)| (i, p)).collect();
        let nv12 = sink.wants_nv12();
        let st = State { sink, pos, next: 0, held: BTreeMap::new(), stop: None, saves };
        Arc::new(Turn { state: Mutex::new(st), cv: Condvar::new(), nv12, spent: Default::default() })
    }

    /// Whether its encoder takes NV12 (a worker's sink says so: the GPU then reads its frames back as NV12, painter.rs).
    pub fn nv12(&self) -> bool {
        self.nv12
    }

    /// Queues this frame in the encoder when its turn has come, else holds it (waiting while it is WINDOW or more
    /// frames ahead), then every held frame whose turn it now is.
    pub fn push(&self, px: Pixels) -> Result<(), String> {
        let p = {
            let st = self.state.lock().unwrap();
            let p = *st.pos.get(&px.index).ok_or_else(|| format!("frame {} is not one of the export's frames", px.index))?;
            if p < st.next || st.held.contains_key(&p) {
                return Err(format!("frame {} came twice", px.index));
            }
            p
        };
        // Converted here, off the lock, while other workers convert theirs (due or not: the one writer thread
        // converting each due frame was the export's narrowest step). Frames from the GPU's output step are ready.
        let t0 = Instant::now();
        let mut px = Some(px.for_encoder(self.nv12));
        let t1 = Instant::now();
        let mut st = self.state.lock().unwrap();
        loop {
            if let Some(why) = &st.stop {
                return Err(format!("the export stopped: {why}"));
            }
            if p < st.next + WINDOW {
                break;
            }
            st = self.cv.wait(st).unwrap();
        }
        st.held.insert(p, px.take().unwrap());
        let t2 = Instant::now();
        let mut r = Ok(());
        while let Some(px) = { let n = st.next; st.held.remove(&n) } {
            r = st.sink.push(px).and_then(|_| {
                st.next += 1;
                let next = st.next;
                match st.saves.remove(&next) {
                    Some(file) => st.sink.mark_save(&file),
                    None => Ok(()),
                }
            });
            match &r {
                Ok(()) => {}
                Err(e) => {
                    st.stop = Some(e.clone());
                    break;
                }
            }
        }
        self.cv.notify_all();
        drop(st);
        for (k, d) in [t1 - t0, t2 - t1, t2.elapsed()].iter().enumerate() {
            self.spent[k].fetch_add(d.as_micros() as u64, Ordering::Relaxed);
        }
        r
    }

    /// Seconds summed over the workers: converting, waiting for a turn, handing frames to the encoder.
    pub fn spent(&self) -> [f64; 3] {
        self.spent.each_ref().map(|a| a.load(Ordering::Relaxed) as f64 / 1e6)
    }

    /// A worker failed: every frame waiting, and every one pushed from now on, fails with `why` (the first kept).
    pub fn stop(&self, why: &str) {
        let mut st = self.state.lock().unwrap();
        st.stop.get_or_insert_with(|| why.to_string());
        st.held.clear();
        self.cv.notify_all();
    }

    /// The encoder back, once every worker's sink is gone.
    pub fn into_sink(turn: Arc<Turn>) -> Result<Sink, String> {
        let turn = Arc::try_unwrap(turn).map_err(|_| "export: a drawing worker still holds the encoder".to_string())?;
        let st = turn.state.into_inner().unwrap();
        if !st.held.is_empty() && st.stop.is_none() {
            return Err(format!("export: {} frames never reached the encoder (frame {} never came)", st.held.len(), st.next));
        }
        Ok(st.sink)
    }
}

#[cfg(test)]
mod tests {
    use std::sync::{Arc, Mutex};
    use std::time::Duration;

    use super::{Turn, WINDOW};
    use crate::sink::{Pixels, Sink, SAVE_MARK};

    /// A frame of 4 × 2 premultiplied half floats, its values made from its number.
    fn frame(index: u32) -> Pixels {
        let raw = (0..4 * 2 * 4).flat_map(|k| half::f16::from_f32(((index as usize * 7 + k) % 97) as f32 / 97.0).to_le_bytes()).collect();
        Pixels { raw, spec: crate::color::Spec::default(), width: 4, deep: false, index, ready: false, repeat: false, nv12: false }
    }

    /// Three workers push 40 frames in an order of their own (one held up on a slow frame): the encoder still gets every
    /// frame once, in order, with the bytes the writer thread would have made from each, and each segment's save mark
    /// right after its last frame.
    #[test]
    fn frames_drawn_early_are_held_and_go_in_in_order_with_the_same_bytes() {
        let kept = Arc::new(Mutex::new(vec![]));
        let n = 40u32;
        let saves = [(10, "a".to_string()), (25, "b".to_string()), (40, "c".to_string())].into();
        let turn = Turn::new(Sink::kept(kept.clone()), (100..100 + n).collect(), saves);
        let claim = std::sync::atomic::AtomicU32::new(0);
        std::thread::scope(|sc| {
            for w in 0..3 {
                let (turn, claim) = (turn.clone(), &claim);
                sc.spawn(move || loop {
                    let i = claim.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
                    if i >= n {
                        break;
                    }
                    if i == 3 || (w == 1 && i % 5 == 0) {
                        std::thread::sleep(Duration::from_millis(40)); // a slow frame
                    }
                    turn.push(frame(100 + i)).unwrap();
                });
            }
        });
        let mut got = kept.lock().unwrap();
        // each save mark right after the frame before its cut, whatever order the workers drew in
        let marks: Vec<(usize, Vec<u8>)> = got.iter().enumerate().filter(|(_, (i, _))| *i == SAVE_MARK).map(|(k, (_, p))| (k, p.clone())).collect();
        assert_eq!(marks, vec![(10, b"a".to_vec()), (26, b"b".to_vec()), (42, b"c".to_vec())]);
        got.retain(|(i, _)| *i != SAVE_MARK);
        assert_eq!(got.iter().map(|(i, _)| *i).collect::<Vec<_>>(), (100..100 + n).collect::<Vec<_>>());
        for (i, bytes) in got.iter() {
            assert_eq!(bytes, &frame(*i).converted().raw, "frame {i}");
        }
        drop(got);
        Turn::into_sink(turn).unwrap();
    }

    /// A frame WINDOW or more ahead of the next due waits (memory stays bounded) and goes on once that one is in; a stop
    /// wakes it with the failure.
    #[test]
    fn a_frame_too_far_ahead_waits_for_the_window_and_a_stop_wakes_it() {
        let kept = Arc::new(Mutex::new(vec![]));
        let turn = Turn::new(Sink::kept(kept.clone()), (0..WINDOW as u32 + 2).collect(), Default::default());
        for i in 1..WINDOW as u32 {
            turn.push(frame(i)).unwrap(); // held: 1 ..< WINDOW
        }
        let far = { let t = turn.clone(); std::thread::spawn(move || t.push(frame(WINDOW as u32))) };
        std::thread::sleep(Duration::from_millis(60));
        assert!(!far.is_finished(), "a frame WINDOW ahead went in before frame 0");
        assert!(kept.lock().unwrap().is_empty());
        turn.push(frame(0)).unwrap();
        far.join().unwrap().unwrap();
        assert_eq!(kept.lock().unwrap().len(), WINDOW + 1);
        // The last frame's turn never comes after a stop: a frame waiting past the window fails instead of hanging.
        let late = Turn::new(Sink::kept(kept.clone()), (0..WINDOW as u32 + 1).collect(), Default::default());
        let waiting = { let t = late.clone(); std::thread::spawn(move || t.push(frame(WINDOW as u32))) };
        std::thread::sleep(Duration::from_millis(30));
        late.stop("worker 2 failed");
        assert!(waiting.join().unwrap().unwrap_err().contains("worker 2 failed"));
        // A frame twice is refused.
        let twice = Turn::new(Sink::kept(kept), (0..4).collect(), Default::default());
        twice.push(frame(2)).unwrap();
        assert!(twice.push(frame(2)).unwrap_err().contains("twice"));
    }
}

//! One encoder shared by an export's drawing workers (export_crew.rs): each worker's sink (sink.rs `Sink::turn`)
//! hands its frames here, and a frame goes into the encoder only when every frame before it has, so the encoder
//! still gets every frame once, in frame order. A worker waits at most until the frames before its own are drawn
//! (each worker keeps one frame in flight: memory stays bounded). `stop` (a worker failed) wakes every waiter
//! with that failure, so no worker waits for a frame that will never come.

use std::sync::{Arc, Condvar, Mutex};

use crate::sink::{Pixels, Sink};

pub struct Turn {
    state: Mutex<State>,
    cv: Condvar,
}

struct State {
    sink: Sink,
    /// Every frame's document number in export order, and how many have gone in.
    order: Vec<u32>,
    next: usize,
    stop: Option<String>,
}

impl Turn {
    /// The export's encoder, taking frames numbered `order` (export order).
    pub fn new(sink: Sink, order: Vec<u32>) -> Arc<Turn> {
        Arc::new(Turn { state: Mutex::new(State { sink, order, next: 0, stop: None }), cv: Condvar::new() })
    }

    /// Waits for this frame's turn and queues it in the encoder.
    pub fn push(&self, px: Pixels) -> Result<(), String> {
        let mut st = self.state.lock().unwrap();
        loop {
            if let Some(why) = &st.stop {
                return Err(format!("the export stopped: {why}"));
            }
            match st.order.get(st.next) {
                Some(&due) if due == px.index => break,
                None => return Err(format!("frame {} came after the export's last frame", px.index)),
                Some(_) => st = self.cv.wait(st).unwrap(),
            }
        }
        let r = st.sink.push(px);
        match &r {
            Ok(()) => st.next += 1,
            Err(e) => st.stop = Some(e.clone()),
        }
        self.cv.notify_all();
        r
    }

    /// A worker failed: every frame waiting, and every one pushed from now on, fails with `why` (the first kept).
    pub fn stop(&self, why: &str) {
        let mut st = self.state.lock().unwrap();
        st.stop.get_or_insert_with(|| why.to_string());
        self.cv.notify_all();
    }

    /// The encoder back, once every worker's sink is gone.
    pub fn into_sink(turn: Arc<Turn>) -> Result<Sink, String> {
        let turn = Arc::try_unwrap(turn).map_err(|_| "export: a drawing worker still holds the encoder".to_string())?;
        Ok(turn.state.into_inner().unwrap().sink)
    }
}

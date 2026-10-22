//! Live output on Windows (S3): our own WASAPI stream, because cpal opens WASAPI only in classic
//! shared mode (a 10 ms period, ~42 ms note-to-speaker on Sam's laptop). Exclusive mode at the
//! device's minimum period (3 ms there) is event-driven on a "Pro Audio" (MMCSS) thread; if the
//! device is busy or refuses every format it falls back to low-latency shared mode (IAudioClient3)
//! and says so. After every block the device clock (IAudioClock) gives the moment each written frame
//! reaches the speaker, so latency is measured, not estimated. The device is device.rs, opening
//! (the period probe, the sample formats) open.rs, one stream playing stream.rs.
//!
//! The stream keeps watching the device: when its clock falls behind what was written (frames it
//! has not played pile up as added latency, under load) by more than FALL_BEHIND, the stream is
//! reopened at the next longer period that keeps real time — shared mode past 25 ms — as the
//! start-up probe does; each step is reported on stdout (`{"output": …}`) and in `Stats`.

// The COM calls here are all unsafe; the functions that make them are unsafe as a whole.
#![allow(unsafe_op_in_unsafe_fn)]

pub mod device;
pub mod open;
pub mod probe;
pub mod stream;

use std::sync::atomic::AtomicBool;
use std::sync::mpsc::Sender;
use std::sync::Arc;

use windows::core::w;
use windows::Win32::System::Com::{CoInitializeEx, COINIT_MULTITHREADED};
use windows::Win32::System::Performance::{QueryPerformanceCounter, QueryPerformanceFrequency};
use windows::Win32::System::Threading::{AvRevertMmThreadCharacteristics, AvSetMmThreadCharacteristicsW};

pub use crate::live::wasapi::device::{input, inputs, outputs};
use crate::live::wasapi::device::{describe, name, output};
use crate::live::wasapi::open::{exclusive, shared};
use crate::live::wasapi::stream::{period_frames, play, Ended, Stream};

/// Latency the device may add while running before the stream steps up its period (seconds; at least 3 periods).
pub const FALL_BEHIND: f64 = 0.03;

/// What a stream plays: blocks of `channels()` interleaved channels on the speakers `mask()` names
/// (stereo unless it says otherwise), told afterwards when each block is heard.
pub trait Source: Send + 'static {
    fn channels(&self) -> usize {
        2
    }
    /// Its channels' speakers (WAVE channel-mask bits, in order).
    fn mask(&self) -> u32 {
        0x3
    }
    /// Fills `out` (`channels()` interleaved, `out.len() / channels()` frames), the first frame being stream frame `start`.
    fn fill(&mut self, out: &mut [f32], start: u64);
    /// Stream frame `start` (the first of the block just written) reaches the speaker at `at` (seconds, the QPC clock of `now()`).
    fn heard(&mut self, _start: u64, _at: f64) {}
}

/// How a stream went: blocks written, and how many milliseconds the device fell behind (summed over
/// every reopening; `heard` times stay true either way); how often it stepped up (`steps`), and the
/// mode and period it ended in.
#[derive(Clone, Copy, Debug, Default)]
pub struct Stats {
    pub blocks: u64,
    pub dropped_ms: f64,
    pub steps: u32,
    pub mode: &'static str,
    pub period_frames: u32,
}

#[derive(Clone, Debug)]
pub struct Opened {
    pub mode: &'static str,
    pub rate: u32,
    pub period_frames: u32,
    pub format: &'static str,
    /// The device's channels (the stream writes every one; monitor.rs places the source's on them).
    pub channels: u16,
    /// The output device's name.
    pub device: String,
    /// Why exclusive mode was not used, when it was asked for and the stream fell back to shared mode.
    pub fallback: Option<String>,
}

/// Seconds on the performance counter: the clock every event and every `heard` time is on.
pub fn now() -> f64 {
    let (mut c, mut f) = (0i64, 1i64);
    unsafe {
        let _ = QueryPerformanceCounter(&mut c);
        let _ = QueryPerformanceFrequency(&mut f);
    }
    c as f64 / f as f64
}

/// Opens the default output and plays `make(rate)` until `stop`; returns once the stream runs (or failed to).
/// `exclusive: false` goes straight to shared mode. `rate`: the rate to ask for first in exclusive
/// mode (a mix's own, so it plays unresampled); else, and in shared mode, the device's.
pub fn start<S: Source>(make: impl FnOnce(u32) -> Result<S, String> + Send + 'static, stop: Arc<AtomicBool>, exclusive_mode: bool, rate: Option<u32>) -> Result<(Opened, std::thread::JoinHandle<Result<Stats, String>>), String> {
    start_on(move |d: &crate::live::monitor::Device| make(d.rate), stop, exclusive_mode, rate)
}

/// `start`, the source made knowing the device (its channels, speakers and form factor: monitor.rs).
pub fn start_on<S: Source>(make: impl FnOnce(&crate::live::monitor::Device) -> Result<S, String> + Send + 'static, stop: Arc<AtomicBool>, exclusive_mode: bool, rate: Option<u32>) -> Result<(Opened, std::thread::JoinHandle<Result<Stats, String>>), String> {
    let (tx, rx) = std::sync::mpsc::channel();
    let handle = std::thread::spawn(move || {
        let r = unsafe { run(make, &stop, exclusive_mode, rate, &tx) };
        if let Err(e) = &r {
            let _ = tx.send(Err(e.clone()));
        }
        r
    });
    match rx.recv() {
        Ok(Ok(opened)) => Ok((opened, handle)),
        Ok(Err(e)) => Err(e),
        Err(_) => Err(handle.join().map_err(|_| "the audio thread panicked".to_string())?.err().unwrap_or_else(|| "the audio thread ended".into())),
    }
}

unsafe fn run<S: Source>(make: impl FnOnce(&crate::live::monitor::Device) -> Result<S, String>, stop: &AtomicBool, exclusive_mode: bool, want: Option<u32>, ready: &Sender<Result<Opened, String>>) -> Result<Stats, String> {
    let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
    let device = output()?;
    let mut described = describe(&device)?;
    let (rate, channels, mask) = (described.rate, described.channels as u16, described.mask);
    let excl = match (exclusive_mode, want) {
        (false, _) => Err("shared mode asked for".into()),
        (true, Some(w)) if w != rate => exclusive(&device, w, channels, mask, None).map(|o| (o, w)).or_else(|_| exclusive(&device, rate, channels, mask, None).map(|o| (o, rate))),
        (true, _) => exclusive(&device, rate, channels, mask, None).map(|o| (o, rate)),
    };
    let (mut stream, rate, fallback) = match excl {
        Ok((open, rate)) => (Stream::new(open, "exclusive"), rate, None),
        Err(why) => {
            let (open, rate) = shared(&device).map_err(|e| format!("{why}; {e}"))?;
            (Stream::new(open, "shared"), rate, exclusive_mode.then_some(why))
        }
    };
    described.rate = rate;
    let mut source = make(&described)?;
    // Where each of the source's channels plays; a channel with nowhere to go fails here, loudly.
    let map = crate::live::monitor::channel_map(source.channels(), source.mask(), stream.channels as usize, mask)?;
    stream.map = map.clone();
    let mut stats = Stats::default();
    let (mut written, mut ready) = (0u64, Some((ready, name(&device), fallback)));
    let mut task = 0u32;
    let mmcss = AvSetMmThreadCharacteristicsW(w!("Pro Audio"), &mut task).ok();
    let result = loop {
        let behind = match play(&stream, rate, &mut source, stop, &mut written, &mut stats, &mut ready) {
            Ok(Ended::Stopped(behind)) => {
                stats.dropped_ms += behind * 1000.0;
                break Ok(());
            }
            Err(e) => break Err(e),
            Ok(Ended::Behind(s)) => s,
        };
        stats.dropped_ms += behind * 1000.0;
        // Step up as the start-up probe does: the next exclusive period that keeps time, else shared mode at the same rate.
        let was = (stream.mode, stream.period);
        drop(stream);
        let next = match was {
            // (A pinned period, ROSTRUM_AUDIO_PERIOD_MS, comes back the same: no longer.)
            ("exclusive", p) => exclusive(&device, rate, channels, mask, Some(p * 2)).and_then(|o| if o.4 > p { Ok(Stream::new(o, "exclusive")) } else { Err("the period is pinned (ROSTRUM_AUDIO_PERIOD_MS)".into()) }).or_else(|why| match shared(&device) {
                Ok((open, r)) if r == rate => Ok(Stream::new(open, "shared")),
                Ok((_, r)) => Err(format!("{why}; shared mode runs at {r} Hz, not {rate}")),
                Err(e) => Err(format!("{why}; {e}")),
            }),
            _ => Err("already in shared mode".to_string()),
        };
        // Nothing longer: the same again (which clears the latency it built up), and said so.
        let (next, why) = match next {
            Ok(s) => (s, None),
            Err(why) => match was.0 {
                "exclusive" => (Stream::new(exclusive(&device, rate, channels, mask, Some(was.1.min(crate::live::wasapi::open::MAX_PERIOD)))?, "exclusive"), Some(why)),
                _ => (Stream::new(shared(&device)?.0, "shared"), Some(why)),
            },
        };
        stats.steps += 1;
        let period_ms = period_frames(&next) as f64 * 1000.0 / rate as f64;
        println!("{}", serde_json::json!({ "output": { "fellBehindMs": (behind * 1e5).round() / 100.0, "reopened": next.mode, "periodMs": (period_ms * 100.0).round() / 100.0, "step": stats.steps, "noLongerPeriod": why } }));
        stream = Stream { map: map.clone(), ..next };
    };
    if let Some(h) = mmcss {
        let _ = AvRevertMmThreadCharacteristics(h);
    }
    stats.mode = stream.mode;
    stats.period_frames = period_frames(&stream);
    result.map(|_| stats)
}

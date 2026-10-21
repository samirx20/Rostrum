//! One open stream of the live output (mod.rs) playing a `Source`: event-driven blocks, and after each
//! the device clock (IAudioClock) read for the moment the block is heard and for how far the device has
//! fallen behind what was written (FALL_BEHIND: mod.rs then reopens at a longer period).

// The COM calls here are all unsafe; the functions that make them are unsafe as a whole.
#![allow(unsafe_op_in_unsafe_fn)]

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::Sender;

use windows::core::Interface;
use windows::Win32::Foundation::{CloseHandle, WAIT_OBJECT_0};
use windows::Win32::Media::Audio::*;
use windows::Win32::System::Com::CoTaskMemFree;
use windows::Win32::System::Threading::{CreateEventW, WaitForSingleObject};

use crate::live::wasapi::{Opened, Source, Stats, FALL_BEHIND};
use crate::live::wasapi::open::{write, Open, Sample};

/// One open stream: its client, format, mode and period.
pub struct Stream {
    pub client: IAudioClient,
    pub sample: Sample,
    pub format: &'static str,
    pub channels: u16,
    pub period: i64,
    pub mode: &'static str,
    /// For each device channel, the source channel it plays (monitor.rs channel_map).
    pub map: Vec<Option<usize>>,
}

impl Stream {
    pub fn new((client, sample, format, channels, period): Open, mode: &'static str) -> Stream {
        Stream { client, sample, format, channels, period, mode, map: vec![] }
    }
}

/// Why a stream stopped playing: asked to (with how far behind the device ended), or the device fell behind.
pub enum Ended {
    Stopped(f64),
    Behind(f64),
}

/// A stream's period in frames (shared mode: the engine period it runs at).
pub unsafe fn period_frames(s: &Stream) -> u32 {
    let buffer = s.client.GetBufferSize().unwrap_or(0);
    if s.mode == "exclusive" {
        return buffer;
    }
    let engine = s.client.cast::<IAudioClient3>().ok().and_then(|c| {
        let (mut p, mut f) = (std::ptr::null_mut(), 0u32);
        c.GetCurrentSharedModeEnginePeriod(&mut p, &mut f).ok().map(|_| {
            CoTaskMemFree(Some(p as *const _));
            f
        })
    });
    engine.unwrap_or(buffer)
}

pub type Ready<'a> = Option<(&'a Sender<Result<Opened, String>>, String, Option<String>)>;

/// Plays `source` on one stream until `stop`, an error, or the device falling behind by more than FALL_BEHIND.
pub unsafe fn play<S: Source>(s: &Stream, rate: u32, source: &mut S, stop: &AtomicBool, written: &mut u64, stats: &mut Stats, ready: &mut Ready) -> Result<Ended, String> {
    let event = CreateEventW(None, false, false, None).map_err(|e| e.message())?;
    let r = (|| -> Result<Ended, String> {
        s.client.SetEventHandle(event).map_err(|e| e.message())?;
        let render: IAudioRenderClient = s.client.GetService().map_err(|e| e.message())?;
        let clock: IAudioClock = s.client.GetService().map_err(|e| e.message())?;
        let freq = clock.GetFrequency().map_err(|e| e.message())? as f64;
        let buffer = s.client.GetBufferSize().map_err(|e| e.message())?;
        let src = source.channels();
        let mut block = vec![0f32; buffer as usize * src];
        // Exclusive mode wants a buffer written before it starts.
        let p = render.GetBuffer(buffer).map_err(|e| e.message())?;
        write(&block, buffer as usize, src, &s.map, s.channels as usize, s.sample, p);
        render.ReleaseBuffer(buffer, 0).map_err(|e| e.message())?;
        // This stream's clock counts from its own start: what earlier streams wrote comes first.
        let offset = *written as f64;
        *written += buffer as u64;
        s.client.Start().map_err(|e| e.message())?;
        if let Some((tx, device, fallback)) = ready.take() {
            let _ = tx.send(Ok(Opened { mode: s.mode, rate, period_frames: period_frames(s), format: s.format, channels: s.channels, device, fallback }));
        }
        // How far the device lags what was written, at its least (the first blocks) and now: added latency.
        let (mut base, mut blocks, mut behind) = (f64::MAX, 0u64, 0.0f64);
        let limit = FALL_BEHIND.max(3.0 * period_frames(s) as f64 / rate as f64);
        while !stop.load(Ordering::Relaxed) {
            if WaitForSingleObject(event, 2000) != WAIT_OBJECT_0 {
                return Err("the audio device stopped asking for samples (no buffer event in 2 s)".into());
            }
            let n = if s.mode == "exclusive" { buffer } else { buffer - s.client.GetCurrentPadding().unwrap_or(buffer) };
            if n == 0 {
                continue;
            }
            let frames = &mut block[..n as usize * src];
            frames.fill(0.0);
            source.fill(frames, *written);
            let p = render.GetBuffer(n).map_err(|e| format!("GetBuffer: {}", e.message()))?;
            write(frames, n as usize, src, &s.map, s.channels as usize, s.sample, p);
            render.ReleaseBuffer(n, 0).map_err(|e| format!("ReleaseBuffer: {}", e.message()))?;
            // Where the device is now (and when): frame `written` is heard (written − position) frames later.
            let (mut pos, mut qpc) = (0u64, 0u64);
            if clock.GetPosition(&mut pos, Some(&mut qpc)).is_ok() {
                let lag = *written as f64 - (offset + pos as f64 / freq * rate as f64);
                blocks += 1;
                stats.blocks += 1;
                if blocks <= 20 {
                    base = base.min(lag);
                } else {
                    behind = ((lag - base) / rate as f64).max(0.0);
                }
                source.heard(*written, qpc as f64 * 1e-7 + lag / rate as f64);
                if behind > limit {
                    *written += n as u64;
                    return Ok(Ended::Behind(behind));
                }
            }
            *written += n as u64;
        }
        Ok(Ended::Stopped(behind))
    })();
    let _ = s.client.Stop();
    let _ = CloseHandle(event);
    r
}

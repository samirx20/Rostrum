//! `rostrum-sound record <out.wav> [--seconds <s>]`: a voiceover take from the default microphone.
//! WASAPI shared-mode capture at the device's own rate, folded to mono, written as a 32-bit float
//! WAV when the take ends: on a stdin line `stop` (or {"stop": true}), at the end of stdin, or after
//! --seconds. Out on stdout, one JSON object per line: {"ready": {rate, channels, device}} once the
//! microphone runs, {"level": {t, peakDb}} every 100 ms (a meter), {"done": {file, seconds, peakDb}}.
//! `open` is the microphone itself, packets timed on the output's clock: the transport (transport.rs)
//! records with it while the mix plays (overdub).

#![allow(unsafe_op_in_unsafe_fn)]

use std::io::BufRead;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

use windows::core::GUID;
use windows::Win32::Media::Audio::*;
use windows::Win32::System::Com::{CoCreateInstance, CoInitializeEx, CoTaskMemFree, CLSCTX_ALL, COINIT_MULTITHREADED};

const SUBTYPE_FLOAT: GUID = GUID::from_u128(0x00000003_0000_0010_8000_00aa00389b71);

/// Interleaved device frames → mono (the channels averaged). `float`: 32-bit float, else 16-bit integer.
pub fn downmix(bytes: &[u8], channels: usize, float: bool, out: &mut Vec<f32>) {
    let width = if float { 4 } else { 2 };
    for frame in bytes.chunks_exact(width * channels) {
        let sum: f32 = frame
            .chunks_exact(width)
            .map(|b| if float { f32::from_le_bytes([b[0], b[1], b[2], b[3]]) } else { i16::from_le_bytes([b[0], b[1]]) as f32 / 32768.0 })
            .sum();
        out.push(sum / channels as f32);
    }
}

fn db(peak: f32) -> f64 {
    (20.0 * (peak.max(1e-6) as f64).log10() * 10.0).round() / 10.0
}

/// A packet from the microphone: mono samples and when the first was captured (QPC seconds, the
/// clock of `wasapi::now()` and of the output's `heard` times), so a take lines up with what played.
pub struct Packet {
    pub at: f64,
    pub samples: Vec<f32>,
}

/// The microphone that opened.
#[derive(Clone, Debug)]
pub struct Mic {
    pub rate: u32,
    pub channels: usize,
    /// Windows' id for it (what calibrations are kept under) and its name as Windows shows it.
    pub device: String,
    pub name: String,
    /// Opened raw: Windows' own processing (automatic gain, noise suppression, a mic array's beam) is off,
    /// so the level and the delay stay put. False when the device refused raw.
    pub raw: bool,
}

/// Opens the default microphone (WASAPI shared mode, its own rate, folded to mono) on a thread of
/// its own and hands `sink` every packet until `stop`; returns once it runs (or failed to open).
pub fn open(stop: Arc<AtomicBool>, sink: impl FnMut(Packet) + Send + 'static) -> Result<(Mic, std::thread::JoinHandle<Result<(), String>>), String> {
    let (tx, rx) = std::sync::mpsc::channel();
    let handle = std::thread::spawn(move || {
        let r = unsafe { capture(&stop, sink, &tx) };
        if let Err(e) = &r {
            let _ = tx.send(Err(e.clone()));
        }
        r
    });
    match rx.recv() {
        Ok(Ok(mic)) => Ok((mic, handle)),
        Ok(Err(e)) => Err(e),
        Err(_) => Err(handle.join().map_err(|_| "the microphone thread panicked".to_string())?.err().unwrap_or_else(|| "the microphone thread ended".into())),
    }
}

pub fn run(out: &str, seconds: Option<f64>) -> Result<(), String> {
    let stop = Arc::new(AtomicBool::new(false));
    let stdin_stop = stop.clone();
    std::thread::spawn(move || {
        for line in std::io::stdin().lock().lines() {
            let Ok(line) = line else { break };
            let l = line.trim();
            if l == "stop" || serde_json::from_str::<serde_json::Value>(l).map(|v| v["stop"].as_bool() == Some(true)).unwrap_or(false) {
                stdin_stop.store(true, Ordering::Relaxed);
                return;
            }
        }
        // A closed stdin ends the take too, unless --seconds decides its length.
        if seconds.is_none() {
            stdin_stop.store(true, Ordering::Relaxed);
        }
    });
    let (ptx, prx) = std::sync::mpsc::channel();
    let (mic, thread) = open(stop.clone(), move |p| {
        let _ = ptx.send(p);
    })?;
    println!("{}", serde_json::json!({ "ready": { "rate": mic.rate, "channels": mic.channels, "device": mic.device, "name": mic.name } }));
    let rate = mic.rate as usize;
    let started = Instant::now();
    let mut take: Vec<f32> = Vec::with_capacity(rate * 60);
    let (mut meter_at, mut meter_peak) = (0usize, 0f32);
    let mut result: Result<(), String> = Ok(());
    while !stop.load(Ordering::Relaxed) && seconds.is_none_or(|s| (take.len() as f64) < s * rate as f64) {
        match prx.recv_timeout(Duration::from_millis(100)) {
            Ok(p) => {
                meter_peak = p.samples.iter().fold(meter_peak, |m, v| m.max(v.abs()));
                take.extend_from_slice(&p.samples);
            }
            Err(std::sync::mpsc::RecvTimeoutError::Disconnected) => break,
            Err(_) => {}
        }
        if take.len() - meter_at >= rate / 10 {
            println!("{}", serde_json::json!({ "level": { "t": take.len() as f64 / rate as f64, "peakDb": db(meter_peak) } }));
            (meter_at, meter_peak) = (take.len(), 0.0);
        }
        if started.elapsed() > Duration::from_secs(3) && take.is_empty() {
            result = Err("the microphone delivered nothing in 3 s (muted, or blocked by Windows privacy settings?)".into());
            break;
        }
    }
    stop.store(true, Ordering::Relaxed);
    thread.join().map_err(|_| "the microphone thread panicked".to_string())??;
    result?;
    if let Some(s) = seconds {
        take.truncate((s * rate as f64) as usize);
    }
    std::fs::write(out, crate::mix::wavio::write_mono(&take, mic.rate)).map_err(|e| format!("{out}: {e}"))?;
    let peak = take.iter().fold(0f32, |m, v| m.max(v.abs()));
    println!("{}", serde_json::json!({ "done": { "file": out, "seconds": take.len() as f64 / rate as f64, "peakDb": db(peak) } }));
    Ok(())
}

/// `rostrum-sound record <out.wav> [--seconds <s>]`.
pub fn main(args: &[String]) -> Result<(), String> {
    let seconds = args.iter().position(|a| a == "--seconds").and_then(|i| args.get(i + 1)).map(|v| v.parse::<f64>().map_err(|_| format!("--seconds takes a number; got {v}"))).transpose()?;
    run(&args[1], seconds)
}

/// Asks for the raw stream (before Initialize): a laptop microphone otherwise turns itself up and down
/// (automatic gain) and its processing adds a delay of its own, which break calibration and level.
unsafe fn open_raw(client: &IAudioClient) -> bool {
    let props = AudioClientProperties { cbSize: std::mem::size_of::<AudioClientProperties>() as u32, bIsOffload: false.into(), eCategory: AudioCategory_Other, Options: AUDCLNT_STREAMOPTIONS_RAW };
    windows::core::Interface::cast::<IAudioClient2>(client).and_then(|c| c.SetClientProperties(&props)).is_ok()
}

unsafe fn capture(stop: &AtomicBool, mut sink: impl FnMut(Packet), ready: &std::sync::mpsc::Sender<Result<Mic, String>>) -> Result<(), String> {
    let _ = CoInitializeEx(None, COINIT_MULTITHREADED);
    let devices: IMMDeviceEnumerator = CoCreateInstance(&MMDeviceEnumerator, None, CLSCTX_ALL).map_err(|e| e.message())?;
    let device = devices.GetDefaultAudioEndpoint(eCapture, eConsole).map_err(|e| format!("no microphone: {}", e.message()))?;
    let id = device.GetId().ok().map(|p| { let s = p.to_string().unwrap_or_default(); CoTaskMemFree(Some(p.0 as *const _)); s }).unwrap_or_default();
    let client: IAudioClient = device.Activate(CLSCTX_ALL, None).map_err(|e| e.message())?;
    let mix = client.GetMixFormat().map_err(|e| e.message())?;
    let (rate, channels, bits, tag) = ((*mix).nSamplesPerSec, (*mix).nChannels as usize, (*mix).wBitsPerSample, (*mix).wFormatTag);
    let float = tag == 3 || (tag == 0xFFFE && std::ptr::addr_of!((*(mix as *const WAVEFORMATEXTENSIBLE)).SubFormat).read_unaligned() == SUBTYPE_FLOAT);
    let raw = open_raw(&client);
    let r = client.Initialize(AUDCLNT_SHAREMODE_SHARED, 0, 2_000_000, 0, mix, None);
    CoTaskMemFree(Some(mix as *const _ as *const _));
    r.map_err(|e| format!("the microphone would not open: {}", e.message()))?;
    if !(float && bits == 32) && bits != 16 {
        return Err(format!("the microphone's format is {bits}-bit {} (expected 32-bit float or 16-bit)", if float { "float" } else { "integer" }));
    }
    let cap: IAudioCaptureClient = client.GetService().map_err(|e| e.message())?;
    client.Start().map_err(|e| e.message())?;
    let name = crate::live::wasapi::device::name(&device);
    let _ = ready.send(Ok(Mic { rate, channels, device: id, name, raw }));
    let width = if float { 4 } else { 2 };
    let mut result = Ok(());
    'run: while !stop.load(Ordering::Relaxed) {
        std::thread::sleep(Duration::from_millis(5));
        loop {
            let n = match cap.GetNextPacketSize() {
                Ok(n) => n,
                Err(e) => {
                    result = Err(format!("the microphone stopped: {}", e.message()));
                    break 'run;
                }
            };
            if n == 0 {
                break;
            }
            let (mut data, mut frames, mut flags, mut qpc) = (std::ptr::null_mut::<u8>(), 0u32, 0u32, 0u64);
            if let Err(e) = cap.GetBuffer(&mut data, &mut frames, &mut flags, None, Some(&mut qpc)) {
                result = Err(format!("GetBuffer: {}", e.message()));
                break 'run;
            }
            let mut samples = Vec::with_capacity(frames as usize);
            if flags & (AUDCLNT_BUFFERFLAGS_SILENT.0 as u32) != 0 {
                samples.resize(frames as usize, 0.0);
            } else {
                downmix(std::slice::from_raw_parts(data, frames as usize * channels * width), channels, float, &mut samples);
            }
            let _ = cap.ReleaseBuffer(frames);
            sink(Packet { at: qpc as f64 * 1e-7, samples });
        }
    }
    let _ = client.Stop();
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn downmix_averages_channels() {
        let mut out = vec![];
        let bytes: Vec<u8> = [0.5f32, -0.5, 1.0, 0.0].iter().flat_map(|v| v.to_le_bytes()).collect();
        downmix(&bytes, 2, true, &mut out);
        assert_eq!(out, vec![0.0, 0.5]);
        let mut out16 = vec![];
        let ints: Vec<u8> = [16384i16, 16384].iter().flat_map(|v| v.to_le_bytes()).collect();
        downmix(&ints, 1, false, &mut out16);
        assert_eq!(out16, vec![0.5, 0.5]);
    }
}

//! `rostrum-sound live <instrument.json> [--shared] [--midi <device>] [--measure <notes>]` (S3).
//! Plays an instrument live on the default output (wasapi/: exclusive mode, else low-latency
//! shared). Notes come from a MIDI keyboard and from JSON lines on stdin ({"on": 60, "velocity": 0.8},
//! {"off": 60}, {"quit": true}; end of input stops), or from a test pattern (--measure). Out on
//! stdout, one JSON object per line: {"ready": …} once, {"note": …} per finished note (seconds
//! since the stream started, as heard), {"heard": …} per note-on (event → speaker), and a
//! {"latency": …} summary at the end.

use std::io::BufRead;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{channel, RecvTimeoutError, Sender};
use std::sync::Arc;
use std::time::Duration;

use crate::live::instrument::{Event, Instrument, LiveSpec, Report};
use crate::live::midi;
use crate::live::wasapi;

pub struct Options {
    pub shared: bool,
    pub midi: Option<u32>,
    pub measure: Option<usize>,
}

/// Note-ons at uneven times (so they land anywhere in a block), each held 80 ms.
pub(crate) fn test_pattern(n: usize, events: Sender<Event>) {
    for k in 0..n {
        std::thread::sleep(Duration::from_millis(90 + (k as u64 * 7919) % 37));
        let key = 60 + (k % 12) as u8;
        let _ = events.send(Event::On { key, velocity: 0.8, at: wasapi::now() });
        std::thread::sleep(Duration::from_millis(80));
        let _ = events.send(Event::Off { key });
    }
}

/// JSON lines from stdin until {"quit": true} or the end; keys still down are released.
fn stdin_notes(events: Sender<Event>) {
    let mut down: Vec<u8> = vec![];
    for line in std::io::stdin().lock().lines() {
        let Ok(line) = line else { break };
        let Ok(v) = serde_json::from_str::<serde_json::Value>(&line) else {
            println!("{}", serde_json::json!({ "error": format!("not JSON: {line}") }));
            continue;
        };
        if v["quit"].as_bool() == Some(true) {
            break;
        }
        let key = |k: &serde_json::Value| k.as_u64().filter(|k| *k < 128).map(|k| k as u8);
        if let Some(k) = key(&v["on"]) {
            down.push(k);
            let _ = events.send(Event::On { key: k, velocity: v["velocity"].as_f64().unwrap_or(0.8).clamp(0.0, 1.0), at: wasapi::now() });
        } else if let Some(k) = key(&v["off"]) {
            down.retain(|d| *d != k);
            let _ = events.send(Event::Off { key: k });
        } else {
            println!("{}", serde_json::json!({ "error": format!("expected {{\"on\": key}}, {{\"off\": key}} or {{\"quit\": true}}; got {line}") }));
        }
    }
    for k in down {
        let _ = events.send(Event::Off { key: k });
    }
}

pub fn run(mut spec: LiveSpec, opts: Options) -> Result<(), String> {
    let (etx, erx) = channel();
    let (rtx, rrx) = channel();
    let stop = Arc::new(AtomicBool::new(false));
    // MIDI first: winmm can take seconds to load the first time, and the stream's clock (note times) starts with the stream.
    let devices = midi::devices();
    let _midi = match opts.midi {
        Some(i) => Some(midi::open(i, etx.clone())?),
        None => None,
    };
    // A plugin instrument: its session here on the main thread, activated at the stream's rate.
    let mut plugin = spec.plugin.as_ref().map(crate::plugins::live::LivePlugin::open).transpose()?;
    spec.slot = plugin.as_ref().map(|p| p.slot());
    let (opened, audio) = wasapi::start(move |rate| Instrument::new(&spec, rate, erx, rtx), stop.clone(), !opts.shared, None)?;
    if let Some(p) = plugin.as_mut() {
        p.activate(opened.rate)?;
    }
    let rate = opened.rate as f64;
    println!(
        "{}",
        serde_json::json!({ "ready": { "mode": opened.mode, "rate": opened.rate, "periodMs": opened.period_frames as f64 * 1000.0 / rate, "format": opened.format, "device": opened.device, "exclusiveRefused": opened.fallback, "midiDevices": devices, "midi": opts.midi } })
    );
    let done = Arc::new(AtomicBool::new(false));
    let input = {
        let (done, etx) = (done.clone(), etx.clone());
        let measure = opts.measure;
        std::thread::spawn(move || {
            match measure {
                Some(n) => test_pattern(n, etx),
                None => stdin_notes(etx),
            }
            done.store(true, Ordering::Relaxed);
        })
    };
    drop(etx);
    let mut latencies: Vec<f64> = vec![];
    let mut quiet_since: Option<std::time::Instant> = None;
    loop {
        if let Some(p) = plugin.as_mut() {
            p.idle();
        }
        match rrx.recv_timeout(Duration::from_millis(if plugin.is_some() { 5 } else { 50 })) {
            Ok(Report::Note { key, velocity, start, end }) => println!("{}", serde_json::json!({ "note": { "key": key, "velocity": velocity, "start": start as f64 / rate, "end": end as f64 / rate } })),
            Ok(Report::Heard { key, latency, queue }) => {
                latencies.push(latency);
                println!("{}", serde_json::json!({ "heard": { "key": key, "latencyMs": (latency * 1e5).round() / 100.0, "queueMs": (queue * 1e5).round() / 100.0 } }));
            }
            Ok(Report::Ignored { key }) => println!("{}", serde_json::json!({ "ignored": { "key": key, "why": "the drum kit has no voice on this key" } })),
            Ok(Report::Failed { what }) => println!("{}", serde_json::json!({ "error": what })),
            Err(RecvTimeoutError::Disconnected) => break,
            Err(RecvTimeoutError::Timeout) => {}
        }
        // After the input ends, a moment for the last note-offs to be played and reported.
        if done.load(Ordering::Relaxed) {
            let since = *quiet_since.get_or_insert_with(std::time::Instant::now);
            if since.elapsed() > Duration::from_millis(300) {
                break;
            }
        }
        if audio.is_finished() {
            break;
        }
    }
    stop.store(true, Ordering::Relaxed);
    let _ = input.join();
    let stats = audio.join().map_err(|_| "the audio thread panicked".to_string())??;
    if let Some(p) = plugin {
        p.close();
    }
    if !latencies.is_empty() {
        let ms = |s: f64| (s * 1e5).round() / 100.0;
        let avg = latencies.iter().sum::<f64>() / latencies.len() as f64;
        let mut sorted = latencies.clone();
        sorted.sort_by(f64::total_cmp);
        let max = latencies.iter().cloned().fold(f64::MIN, f64::max);
        let min = latencies.iter().cloned().fold(f64::MAX, f64::min);
        println!(
            "{}",
            serde_json::json!({ "latency": { "notes": latencies.len(), "minMs": ms(min), "avgMs": ms(avg), "medianMs": ms(sorted[sorted.len() / 2]), "maxMs": ms(max), "mode": stats.mode, "periodMs": stats.period_frames as f64 * 1000.0 / rate, "underTenMs": max < 0.010, "droppedMs": (stats.dropped_ms * 100.0).round() / 100.0, "steppedUp": stats.steps, "blocks": stats.blocks } })
        );
    }
    Ok(())
}

/// `rostrum-sound live <instrument.json> [--shared] [--midi <n>] [--measure <notes>]`.
pub fn main(args: &[String]) -> Result<(), String> {
    let spec = serde_json::from_str(&std::fs::read_to_string(&args[1]).map_err(|e| format!("{}: {e}", args[1]))?).map_err(|e| format!("{}: {e}", args[1]))?;
    let flag = |name: &str| args.iter().position(|a| a == name).and_then(|i| args.get(i + 1)).map(|v| v.parse::<usize>().map_err(|_| format!("{name} takes a number; got {v}"))).transpose();
    run(spec, Options { shared: args.iter().any(|a| a == "--shared"), midi: flag("--midi")?.map(|v| v as u32), measure: flag("--measure")? })
}

/// `rostrum-sound latency`: a plain sine synth, 40 notes at uneven times, through each mode.
pub fn latency_cmd() -> Result<(), String> {
    let sine = r#"{"synth":{"wave":"sine","voices":1,"detune":0,"cutoff":8000,"resonance":0,"envAmount":0,"attack":0.002,"decay":0.05,"sustain":0.8,"release":0.05,"octave":0},"volume":0.1}"#;
    for shared in [false, true] {
        run(serde_json::from_str(sine).map_err(|e| e.to_string())?, Options { shared, midi: None, measure: Some(40) })?;
    }
    println!("{}", serde_json::json!({ "sharedModeProbe": serde_json::from_str::<serde_json::Value>(&wasapi::probe::probe()?).unwrap_or_default() }));
    Ok(())
}

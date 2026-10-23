//! `rostrum-sound play <mix.wav | schedule.json> [options]`: the transport (transport.rs) on the live
//! output, driven by JSON lines on stdin — the protocol the CLI (`rostrum play`) and the app use:
//!   {"play": true} {"play": {"from": 12.5}} {"stop": true} {"seek": 30} {"loop": [8, 16]} {"loop": null}
//!   {"metronome": true} {"countIn": 1} {"record": true} {"record": {"punch": [8, 12]}} {"record": false}
//!   {"on": 60, "velocity": 0.8} {"off": 60} {"load": "<new mix.wav>"} {"quit": true}
//! Out on stdout, one JSON object per line: {"ready": …}, {"pos": {t, playing}} every 50 ms while it
//! changes (the mix time at the speaker), {"rolling": t}, {"wrapped": t}, {"end": t}, {"note": {key,
//! velocity, start, end}} (recorded, in mix seconds), {"levels": {t, strips: {<track | bus id | "master">: [peakDb,
//! rmsDb]}}} ~30 times a second while rolling (each strip's loudest 1/30 s window since the last line, at the speaker's
//! mix time, read from the render's `<mix>.levels.json`: mix/render/levels.rs) and {"levels": null} once when it stops,
//! (no levels file beside the mix, or one for another render: one {"error": "meters: …"} line, and no levels), {"input": {peakDb}} every 100 ms with --mic (the input level), {"take": {file, start, seconds, rate, peakDb}}
//! (a microphone take, one per pass), {"heard": …} per played note, {"error": …}, and {"done": …}.
//! Options: --shared, --midi <n>, --instrument <live.json>, --mic <takes dir>, --bpm <b>, --beats <n>,
//! --beat-times <file.json> (the beats in seconds, when the tempo changes: the metronome follows them),
//! --bar-times <file.json> (each bar's start in seconds, when the time signature changes: accented clicks),
//! --from <s>, --loop <a> <b>, --metronome, --count-in <bars>, --record, --punch <a> <b>, --autoplay,
//! --until-end (quit when playback ends), --measure <notes> (a test pattern on the instrument),
//! --monitor auto|surround|binaural|stereo (a surround mix on this output: monitor.rs; `ready.monitor` says
//! which and why), --master <json> (the mastering spec a fold-down or binaural render is held to).
//! The commands are play/protocol.rs; the microphone takes play/takes.rs.

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::channel;
use std::sync::Arc;
use std::time::{Duration, Instant};

pub mod mix;
mod meters;
mod protocol;
mod takes;

use crate::live::instrument::{Instrument, LiveSpec, Report};
use crate::live::play::mix::Monitoring;
use crate::live::transport::{Clock, Cmd, Out, Transport};
use crate::live::midi;
use crate::live::record;
use crate::live::wasapi;
use meters::Meters;
use protocol::{arg, Msg};
use takes::{Calibrating, Takes};

/// A JSON file an option names (`--instrument`, `--beat-times`), or None without the option.
fn json_file<T: serde::de::DeserializeOwned>(args: &[String], name: &str) -> Result<Option<T>, String> {
    let Some(i) = args.iter().position(|a| a == name) else { return Ok(None) };
    let f = args.get(i + 1).ok_or(format!("{name} takes a file"))?;
    serde_json::from_str(&std::fs::read_to_string(f).map_err(|e| format!("{f}: {e}"))?).map(Some).map_err(|e| format!("{f}: {e}"))
}

pub fn run(args: &[String]) -> Result<(), String> {
    let (mix, mix_rate, levels) = crate::live::play::mix::read(&args[1])?;
    let mut meters = Meters::new(levels);
    let monitoring = Monitoring::from_args(args)?;
    let flag = |n: &str| args.iter().any(|a| a == n);
    let mut spec: Option<LiveSpec> = json_file(args, "--instrument")?;
    let (bpm, beats) = (arg::<f64>(args, "--bpm", 0)?.unwrap_or(120.0), arg::<u32>(args, "--beats", 0)?.unwrap_or(4));
    let beat_times: Vec<f64> = json_file(args, "--beat-times")?.unwrap_or_default();
    let bar_times: Vec<f64> = json_file(args, "--bar-times")?.unwrap_or_default();
    let takes_dir = args.iter().position(|a| a == "--mic").map(|i| args.get(i + 1).cloned().ok_or("--mic takes a folder for the takes")).transpose()?;
    let (ctx, crx) = channel();
    let (ntx, nrx) = channel();
    let (otx, orx) = channel();
    let (rtx, rrx) = channel::<Report>();
    let (mtx, mrx) = channel::<Msg>();
    let stop = Arc::new(AtomicBool::new(false));
    // The microphone heard through the output (hear.rs): its packets go to the audio thread as well.
    let (htx, hrx) = std::sync::mpsc::sync_channel::<Vec<f32>>(64);
    let hear = takes_dir.as_ref().map(|_| crate::live::hear::Hear::new(hrx));
    let devices = midi::devices();
    let _midi = match arg::<u32>(args, "--midi", 0)? {
        Some(i) => Some(midi::open(i, ntx.clone())?),
        None => None,
    };
    // Calibrating: the metronome recorded back through the microphone (calib.rs), from the start to the end.
    let calibrate = flag("--calibrate");
    if calibrate && takes_dir.is_none() {
        return Err("--calibrate records the metronome through the microphone: give --mic <folder>".into());
    }
    // Set-up commands, applied before the first block.
    let mut armed = protocol::setup(args, &ctx, calibrate)?;
    let seconds = mix.seconds(mix_rate);
    // A plugin instrument: its session here on the main thread (plugins/live.rs), activated once the stream is open.
    let mut plugin = spec.as_ref().and_then(|s| s.plugin.as_ref()).map(crate::plugins::live::LivePlugin::open).transpose()?;
    if let (Some(s), Some(p)) = (spec.as_mut(), plugin.as_ref()) {
        s.slot = Some(p.slot());
    }
    let chosen = monitoring.clone();
    let make = move |dev: &crate::live::monitor::Device| -> Result<Transport, String> {
        let rate = dev.rate;
        let inst = match &spec {
            Some(s) => {
                let (itx, irx) = channel();
                Some((Instrument::new(s, rate, irx, rtx)?, itx))
            }
            None => None,
        };
        Ok(Transport::new(Arc::new(chosen.first(&mix, mix_rate, dev)?), rate, bpm, beats, inst, crx, nrx, otx).with_beats(&beat_times).with_bars(&bar_times).with_hear(hear).with_chirp(calibrate))
    };
    let (opened, audio) = wasapi::start_on(make, stop.clone(), !flag("--shared"), Some(mix_rate as u32))?;
    if let Some(p) = plugin.as_mut() {
        p.activate(opened.rate)?;
    }
    let rate = opened.rate as f64;
    let mic_stop = Arc::new(AtomicBool::new(false));
    let mic = match &takes_dir {
        Some(dir) => {
            std::fs::create_dir_all(dir).map_err(|e| format!("{dir}: {e}"))?;
            let tx = mtx.clone();
            Some(record::open(mic_stop.clone(), move |p| {
                crate::live::hear::send(&htx, &p.samples);
                let _ = tx.send(Msg::Packet(p));
            })?)
        }
        None => None,
    };
    let input_offset = mic.as_ref().and_then(|(m, _)| if calibrate { None } else { crate::live::calib::offset(&opened.device, &m.device, m.raw) });
    println!(
        "{}",
        serde_json::json!({ "ready": { "mode": opened.mode, "rate": opened.rate, "periodMs": opened.period_frames as f64 * 1000.0 / rate, "format": opened.format, "device": opened.device, "exclusiveRefused": opened.fallback, "seconds": seconds, "mixRate": mix_rate, "resampled": opened.rate as f64 != mix_rate,
            "monitor": monitoring.report(Some(opened.channels as usize)), "midiDevices": devices, "mic": mic.as_ref().map(|(m, _)| serde_json::json!({ "rate": m.rate, "device": m.device, "name": m.name, "raw": m.raw, "inputOffsetMs": input_offset.map(|o| (o * 1e5).round() / 100.0) })) } })
    );
    let until_end = flag("--until-end") || calibrate;
    let input = protocol::read_input(mtx.clone(), ntx.clone(), rate, monitoring.clone(), arg::<usize>(args, "--measure", 0)?, until_end);
    let mic_rate = mic.as_ref().map_or(48000.0, |(m, _)| m.rate as f64);
    let calibrating = calibrate.then(|| Calibrating { beat: 60.0 / bpm, device: opened.device.clone(), mic_device: mic.as_ref().map(|(m, _)| m.device.clone()).unwrap_or_default(), raw: mic.as_ref().is_some_and(|(m, _)| m.raw) });
    let mut takes = Takes::new(takes_dir.clone().unwrap_or_else(|| ".".into()), mic_rate, input_offset, calibrating);
    let mut clock = Clock::default();
    let mic_open = mic.is_some();
    let (mut input_peak, mut input_shown) = (0f32, Instant::now());
    let (mut latencies, mut notes, mut last_pos, mut shown) = (vec![], 0usize, None::<f64>, Instant::now());
    'main: loop {
        if let Some(p) = plugin.as_mut() {
            p.idle();
        }
        match mrx.recv_timeout(Duration::from_millis(5)) {
            Ok(Msg::Quit) => break 'main,
            Ok(Msg::Cmd(Cmd::Hear(gain, _))) => {
                if mic_open {
                    let _ = ctx.send(Cmd::Hear(gain, mic_rate));
                } else {
                    println!("{}", serde_json::json!({ "error": "hear: no microphone is open (start play with --mic <takes folder>)" }));
                }
            }
            Ok(Msg::Load(c, levels)) => {
                meters = Meters::new(levels);
                let _ = ctx.send(c);
            }
            Ok(Msg::Cmd(c)) => {
                if let Cmd::Record(r) = &c {
                    armed = *r;
                    if r.is_none() {
                        takes.finish();
                    }
                }
                if matches!(c, Cmd::Stop | Cmd::Seek(_)) {
                    takes.finish();
                }
                let _ = ctx.send(c);
            }
            Ok(Msg::Packet(p)) => {
                input_peak = p.samples.iter().fold(input_peak, |m, v| m.max(v.abs()));
                takes.packet(&p, armed, &clock);
            }
            Err(_) => {}
        }
        while let Ok(o) = orx.try_recv() {
            match o {
                Out::Clock { at, t } => clock.push(at, t),
                Out::Note { key, velocity, start, end } => {
                    notes += 1;
                    println!("{}", serde_json::json!({ "note": { "key": key, "velocity": velocity, "start": start, "end": end } }));
                }
                Out::Rolling(t) => println!("{}", serde_json::json!({ "rolling": t })),
                Out::Wrapped => println!("{}", serde_json::json!({ "wrapped": true })),
                Out::End => {
                    takes.finish();
                    println!("{}", serde_json::json!({ "end": seconds }));
                    if until_end {
                        break 'main;
                    }
                }
            }
        }
        while let Ok(r) = rrx.try_recv() {
            match r {
                Report::Heard { key, latency, queue } => {
                    latencies.push(latency);
                    println!("{}", serde_json::json!({ "heard": { "key": key, "latencyMs": (latency * 1e5).round() / 100.0, "queueMs": (queue * 1e5).round() / 100.0 } }));
                }
                Report::Ignored { key } => println!("{}", serde_json::json!({ "ignored": { "key": key } })),
                Report::Failed { what } => println!("{}", serde_json::json!({ "error": what })),
                _ => {} // its own notes: the transport records them, in mix time
            }
        }
        if mic_open && input_shown.elapsed() >= Duration::from_millis(100) {
            input_shown = Instant::now();
            println!("{}", serde_json::json!({ "input": { "peakDb": (200.0 * (input_peak.max(1e-6) as f64).log10()).round() / 10.0 } }));
            input_peak = 0.0;
        }
        if shown.elapsed() >= Duration::from_millis(50) {
            shown = Instant::now();
            let t = clock.mix_at(wasapi::now());
            if t.map(|t| (t * 100.0).round()) != last_pos.map(|t| (t * 100.0).round()) {
                println!("{}", serde_json::json!({ "pos": { "t": t.map(|t| (t * 1000.0).round() / 1000.0), "playing": t.is_some() } }));
                last_pos = t;
            }
        }
        meters.show(clock.mix_at(wasapi::now()));
        if audio.is_finished() {
            break;
        }
    }
    takes.finish();
    mic_stop.store(true, Ordering::Relaxed);
    if let Some((_, h)) = mic {
        h.join().map_err(|_| "the microphone thread panicked".to_string())??;
    }
    std::thread::sleep(Duration::from_millis(100)); // the last notes' reports
    stop.store(true, Ordering::Relaxed);
    let stats = audio.join().map_err(|_| "the audio thread panicked".to_string())??;
    if let Some(p) = plugin {
        p.close();
    }
    drop(input);
    let ms = |s: f64| (s * 1e5).round() / 100.0;
    let lat = (!latencies.is_empty()).then(|| {
        let mut l = latencies.clone();
        l.sort_by(f64::total_cmp);
        serde_json::json!({ "notes": l.len(), "minMs": ms(l[0]), "medianMs": ms(l[l.len() / 2]), "maxMs": ms(l[l.len() - 1]), "jitterMs": ms(l[l.len() - 1] - l[0]) })
    });
    println!("{}", serde_json::json!({ "done": { "notes": notes, "takes": takes.taken, "latency": lat, "mode": stats.mode, "periodMs": stats.period_frames as f64 * 1000.0 / rate, "droppedMs": (stats.dropped_ms * 100.0).round() / 100.0, "latencyKeptMs": (stats.settled_ms * 100.0).round() / 100.0, "steppedUp": stats.steps, "blocks": stats.blocks } }));
    Ok(())
}

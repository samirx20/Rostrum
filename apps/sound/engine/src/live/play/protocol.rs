//! The transport's protocol (play.rs): one JSON line on stdin → a command for the audio thread (notes go
//! straight to the instrument), and the set-up the command line asks for.

use std::io::BufRead;
use std::sync::mpsc::Sender;
use std::sync::Arc;

use crate::live::instrument::Event;
use crate::live::play::mix::Monitoring;
use crate::live::transport::Cmd;
use crate::live::record;
use crate::live::wasapi;

pub enum Msg {
    Cmd(Cmd),
    /// A new render to play, and its strips' meters (levels.rs) or why there are none.
    Load(Cmd, Result<crate::mix::render::levels::Levels, String>),
    Packet(record::Packet),
    Quit,
}

pub fn arg<T: std::str::FromStr>(args: &[String], name: &str, k: usize) -> Result<Option<T>, String> {
    match args.iter().position(|a| a == name) {
        None => Ok(None),
        Some(i) => args.get(i + 1 + k).ok_or(format!("{name} takes a value"))?.parse().map(Some).map_err(|_| format!("{name}: not a number")),
    }
}

/// One JSON line → what it asks for (notes go straight to the audio thread).
pub fn parse(v: &serde_json::Value, rate: f64, notes: &Sender<Event>, monitoring: &Monitoring) -> Result<Option<Msg>, String> {
    let pair = |x: &serde_json::Value| x.as_array().filter(|a| a.len() == 2).and_then(|a| Some((a[0].as_f64()?, a[1].as_f64()?)));
    let key = |k: &serde_json::Value| k.as_u64().filter(|k| *k < 128).map(|k| k as u8);
    Ok(Some(Msg::Cmd(if v["quit"].as_bool() == Some(true) {
        return Ok(Some(Msg::Quit));
    } else if let Some(k) = key(&v["on"]) {
        let _ = notes.send(Event::On { key: k, velocity: v["velocity"].as_f64().unwrap_or(0.8).clamp(0.0, 1.0), at: wasapi::now() });
        return Ok(None);
    } else if let Some(k) = key(&v["off"]) {
        let _ = notes.send(Event::Off { key: k });
        return Ok(None);
    } else if v["play"].as_bool() == Some(false) {
        Cmd::Stop
    } else if !v["play"].is_null() {
        Cmd::Play(v["play"]["from"].as_f64().or(v["play"].as_f64()))
    } else if v["stop"].as_bool() == Some(true) {
        Cmd::Stop
    } else if let Some(t) = v["seek"].as_f64() {
        Cmd::Seek(t)
    } else if v.get("loop").is_some() {
        Cmd::Loop(pair(&v["loop"]))
    } else if let Some(on) = v["metronome"].as_bool() {
        Cmd::Metronome(on)
    } else if let Some(n) = v["countIn"].as_u64() {
        Cmd::CountIn(n as u32)
    } else if v.get("record").is_some() {
        Cmd::Record(match &v["record"] {
            serde_json::Value::Bool(false) | serde_json::Value::Null => None,
            r => Some(pair(&r["punch"])),
        })
    } else if v.get("hear").is_some() {
        // Hearing the microphone: true (gain 1), false, or {"gain": g}; play.rs fills in the microphone's rate.
        let gain = match &v["hear"] {
            serde_json::Value::Bool(on) => if *on { 1.0 } else { 0.0 },
            h => h["gain"].as_f64().ok_or(format!("hear takes true, false or {{\"gain\": g}}; got {h}"))?.clamp(0.0, 4.0),
        };
        Cmd::Hear(gain as f32, 0.0)
    } else if let Some(f) = v["load"].as_str() {
        let (mix, from, levels) = crate::live::play::mix::read(f)?;
        return Ok(Some(Msg::Load(Cmd::Load(Arc::new(monitoring.again(&mix, from, rate as u32)?)), levels)));
    } else {
        return Err(format!("unknown command {v}"));
    })))
}

/// The set-up the arguments ask for, sent before the first block: the loop, the metronome, the count-in,
/// recording armed (with its punch, or for calibrating), and playing or a place to start. Returns what is armed.
pub fn setup(args: &[String], ctx: &Sender<Cmd>, calibrate: bool) -> Result<Option<Option<(f64, f64)>>, String> {
    let flag = |n: &str| args.iter().any(|a| a == n);
    let mut armed = None;
    if let Some(a) = arg::<f64>(args, "--loop", 0)? {
        ctx.send(Cmd::Loop(Some((a, arg::<f64>(args, "--loop", 1)?.ok_or("--loop takes <from> <to>")?)))).unwrap();
    }
    ctx.send(Cmd::Metronome(flag("--metronome") || calibrate)).unwrap();
    ctx.send(Cmd::CountIn(arg::<u32>(args, "--count-in", 0)?.unwrap_or(0))).unwrap();
    if calibrate {
        armed = Some(None);
        ctx.send(Cmd::Record(armed)).unwrap();
    } else if flag("--record") {
        let punch = match arg::<f64>(args, "--punch", 0)? {
            Some(a) => Some((a, arg::<f64>(args, "--punch", 1)?.ok_or("--punch takes <from> <to>")?)),
            None => None,
        };
        armed = Some(punch);
        ctx.send(Cmd::Record(armed)).unwrap();
    }
    let from = arg::<f64>(args, "--from", 0)?;
    if flag("--autoplay") || calibrate {
        ctx.send(Cmd::Play(from)).unwrap();
    } else if let Some(t) = from {
        ctx.send(Cmd::Seek(t)).unwrap();
    }
    Ok(armed)
}

/// Commands from stdin, on a thread of their own (or the --measure test pattern on the instrument).
/// The end of input quits, unless playback is to run to its end.
pub fn read_input(mtx: Sender<Msg>, ntx: Sender<Event>, rate: f64, monitoring: Arc<Monitoring>, measure: Option<usize>, until_end: bool) -> std::thread::JoinHandle<()> {
    std::thread::spawn(move || {
        if let Some(n) = measure {
            crate::live::perform::test_pattern(n, ntx);
            let _ = mtx.send(Msg::Quit);
            return;
        }
        for line in std::io::stdin().lock().lines() {
            let Ok(line) = line else { break };
            if line.trim().is_empty() {
                continue;
            }
            match serde_json::from_str::<serde_json::Value>(&line).map_err(|_| format!("not JSON: {line}")).and_then(|v| parse(&v, rate, &ntx, &monitoring)) {
                Ok(Some(m)) => {
                    let quit = matches!(m, Msg::Quit);
                    let _ = mtx.send(m);
                    if quit {
                        return;
                    }
                }
                Ok(None) => {}
                Err(e) => println!("{}", serde_json::json!({ "error": e })),
            }
        }
        if !until_end {
            let _ = mtx.send(Msg::Quit);
        }
    })
}

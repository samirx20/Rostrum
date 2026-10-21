//! `rostrum-sound plugin <session.json> [--gui] [--audio] [--shared] [--midi <n>]`: one plugin
//! opened for a person — its own editor window, heard live while they tweak it (an instrument from
//! a MIDI keyboard or JSON note lines; an effect over the track's audio, looped), a preset loaded —
//! and its state handed back as data for the document (`{"state": {state, values}}`), so the edit
//! goes through the document's history and every render after it is the same. Both plugin formats
//! open through the `Session` trait (clap/session.rs, vst3/session.rs); this is the part they share.
//! stdin (JSON lines): {"on": 60, "velocity": 0.8} {"off": 60} {"save": true} {"quit": true}.
//! stdout: {"ready": …}, {"state": …} on every save and once at the end, {"error": …}.

mod feed;

use std::io::BufRead;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::channel;
use std::sync::{Arc, Mutex};
use std::time::Duration;

use serde::Deserialize;

use crate::live::instrument::Event;
use crate::plugins::window::Window;
use feed::Feed;

/// What the session file holds: the plugin as the schedule names it, what kind it is, a preset to load.
#[derive(Deserialize)]
pub struct SessionSpec {
    pub plugin: crate::plugins::clap::PluginSpec,
    #[serde(default)]
    pub effect: bool,
    #[serde(default)]
    pub preset: Option<Preset>,
    #[serde(default)]
    pub title: Option<String>,
    /// An effect's input: audio to loop through it while it is heard (the track as it reaches it).
    #[serde(default)]
    pub input: Option<String>,
}

/// A preset: a file (a CLAP preset location; a .vstpreset), and the key inside it when it holds several.
#[derive(Deserialize, Clone, Debug)]
pub struct Preset {
    #[serde(default)]
    pub file: Option<String>,
    #[serde(default)]
    pub key: Option<String>,
}

/// A note for the plugin in this block: (frame offset, key, velocity; 0 = off).
pub type Note = (u32, u8, f64);

/// The audio-thread half of an activated plugin.
pub trait Proc: Send {
    fn process(&mut self, input: (&[f32], &[f32]), out: (&mut [f32], &mut [f32]), notes: &[Note]) -> Result<(), String>;
    fn into_any(self: Box<Self>) -> Box<dyn std::any::Any>;
}

/// The main-thread half: what each plugin format does for a session.
pub trait Session {
    fn activate(&mut self, rate: f64, max_frames: u32) -> Result<Box<dyn Proc>, String>;
    /// Opens the editor embedded in a window of ours (None: the plugin has no editor we can embed).
    fn open_editor(&mut self, title: &str) -> Result<Option<Window>, String>;
    /// Main-thread work the plugin asked for, resizes; false once its editor has been closed.
    fn idle(&mut self, window: Option<&Window>) -> bool;
    fn state(&mut self) -> Result<String, String>;
    /// The current values of the parameters the document names.
    fn values(&mut self) -> Vec<(u32, f64)>;
    /// Closes the editor and deactivates (with the processor back from the audio thread).
    fn close(&mut self, proc: Option<Box<dyn Proc>>);
}


pub struct Options {
    pub gui: bool,
    pub audio: bool,
    pub shared: bool,
    pub midi: Option<u32>,
    pub title: String,
    /// An effect's input, stereo frames at their rate.
    pub input: Option<(Vec<[f32; 2]>, f64)>,
}

fn state_line(s: &mut dyn Session) -> serde_json::Value {
    match s.state() {
        Ok(st) => serde_json::json!({ "state": { "state": st, "values": s.values() } }),
        Err(e) => serde_json::json!({ "error": format!("saving the plugin's state: {e}") }),
    }
}

pub fn run(s: &mut dyn Session, o: Options) -> Result<(), String> {
    let (ntx, nrx) = channel::<Event>();
    let quit = Arc::new(AtomicBool::new(false));
    let save = Arc::new(AtomicBool::new(false));
    {
        let (ntx, quit, save) = (ntx.clone(), quit.clone(), save.clone());
        std::thread::spawn(move || {
            for line in std::io::stdin().lock().lines() {
                let Ok(line) = line else { break };
                let Ok(v) = serde_json::from_str::<serde_json::Value>(&line) else { continue };
                let key = |k: &serde_json::Value| k.as_u64().filter(|k| *k < 128).map(|k| k as u8);
                if let Some(k) = key(&v["on"]) {
                    let _ = ntx.send(Event::On { key: k, velocity: v["velocity"].as_f64().unwrap_or(0.8).clamp(0.0, 1.0), at: crate::live::wasapi::now() });
                } else if let Some(k) = key(&v["off"]) {
                    let _ = ntx.send(Event::Off { key: k });
                } else if v["save"].as_bool() == Some(true) {
                    save.store(true, Ordering::Relaxed);
                } else if v["quit"].as_bool() == Some(true) {
                    break;
                }
            }
            quit.store(true, Ordering::Relaxed);
        });
    }
    let _midi = match o.midi {
        Some(i) => Some(crate::live::midi::open(i, ntx.clone())?),
        None => None,
    };
    let slot: Arc<Mutex<Option<Box<dyn Proc>>>> = Default::default();
    let stop = Arc::new(AtomicBool::new(false));
    let (htx, hrx) = channel();
    let (etx, erx) = channel();
    let mut audio = None;
    if o.audio {
        let (feed_slot, input) = (slot.clone(), o.input.clone());
        let make = move |rate: u32| -> Result<Feed, String> {
            let input = input.map(|(x, r)| crate::live::transport::resample(&x, r, rate as f64)).unwrap_or_default();
            Ok(Feed { slot: feed_slot, notes: nrx, input: Arc::new(input), pos: 0, bufs: Default::default(), pending: vec![], heard: htx, errors: etx })
        };
        let (opened, handle) = crate::live::wasapi::start(make, stop.clone(), !o.shared, None)?;
        *slot.lock().unwrap() = Some(s.activate(opened.rate as f64, 8192)?);
        audio = Some((opened, handle));
    }
    let window = if o.gui { s.open_editor(&o.title)? } else { None };
    println!(
        "{}",
        serde_json::json!({ "ready": { "audio": audio.as_ref().map(|(a, _)| serde_json::json!({ "mode": a.mode, "rate": a.rate, "periodMs": a.period_frames as f64 * 1000.0 / a.rate as f64, "device": a.device, "exclusiveRefused": a.fallback })),
            "editor": o.gui, "embedded": window.is_some(), "midiDevices": crate::live::midi::devices() } })
    );
    let mut latencies = vec![];
    while o.gui || o.audio {
        if let Some(w) = &window {
            if !w.pump() {
                break;
            }
        } else {
            crate::plugins::window::pump_messages();
        }
        if !s.idle(window.as_ref()) || quit.load(Ordering::Relaxed) {
            break;
        }
        if save.swap(false, Ordering::Relaxed) {
            println!("{}", state_line(s));
        }
        latencies.extend(hrx.try_iter());
        for e in erx.try_iter() {
            println!("{}", serde_json::json!({ "error": e }));
        }
        if audio.as_ref().is_some_and(|(_, h)| h.is_finished()) {
            break;
        }
        std::thread::sleep(Duration::from_millis(5));
    }
    let last = state_line(s);
    stop.store(true, Ordering::Relaxed);
    let stats = match audio {
        Some((_, h)) => Some(h.join().map_err(|_| "the audio thread panicked".to_string())??),
        None => None,
    };
    let proc = slot.lock().unwrap().take();
    s.close(proc);
    drop(window);
    println!("{last}");
    latencies.extend(hrx.try_iter());
    if !latencies.is_empty() || stats.is_some() {
        latencies.sort_by(f64::total_cmp);
        let ms = |x: f64| (x * 1e5).round() / 100.0;
        let n = latencies.len();
        println!("{}", serde_json::json!({ "latency": { "notes": n, "minMs": latencies.first().map(|x| ms(*x)), "medianMs": latencies.get(n / 2).map(|x| ms(*x)), "maxMs": latencies.last().map(|x| ms(*x)), "droppedMs": stats.map(|s| (s.dropped_ms * 100.0).round() / 100.0), "steppedUp": stats.map(|s| s.steps) } }));
    }
    Ok(())
}

/// `rostrum-sound plugin <session.json> …`: the session for the plugin's format.
pub fn main(args: &[String]) -> Result<(), String> {
    let spec: SessionSpec = serde_json::from_str(&std::fs::read_to_string(&args[1]).map_err(|e| format!("{}: {e}", args[1]))?).map_err(|e| format!("{}: {e}", args[1]))?;
    let flag = |n: &str| args.iter().any(|a| a == n);
    let midi = args.iter().position(|a| a == "--midi").and_then(|i| args.get(i + 1)).map(|v| v.parse::<u32>().map_err(|_| format!("--midi takes a number; got {v}"))).transpose()?;
    let input = match &spec.input {
        Some(f) => {
            let w = crate::instruments::sfz::read_wav(std::path::Path::new(f))?;
            Some((w.frames, w.rate))
        }
        None => None,
    };
    let o = Options { gui: flag("--gui"), audio: flag("--audio"), shared: flag("--shared"), midi, title: spec.title.clone().unwrap_or_else(|| "Rostrum: plugin".into()), input };
    run(open(&spec)?.as_mut(), o)
}

/// The session for the plugin's format (its window here; played live in live.rs).
pub fn open(spec: &SessionSpec) -> Result<Box<dyn Session>, String> {
    match spec.plugin.format.as_str() {
        "clap" => Ok(Box::new(crate::plugins::clap::session::ClapSession::new(spec)?)),
        "vst3" => Ok(Box::new(crate::plugins::vst3::session::Vst3Session::new(spec)?)),
        f => Err(format!("plugin format \"{f}\": this engine hosts clap and vst3")),
    }
}

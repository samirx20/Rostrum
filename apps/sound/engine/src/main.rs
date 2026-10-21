//! rostrum-sound: Rostrum's native sound engine (docs/NATIVE_ENGINE.md § Sound engine).
//!   rostrum-sound render <schedule.json> <out.wav>   the mix, offline: 32-bit float WAV of its bed (stereo, 5.1,
//!                                                    7.1: bed/) + stats (JSON)
//!   rostrum-sound layouts                           the channel layouts (names, azimuths) as JSON
//!   rostrum-sound fold <bed.wav> <stereo|5.1|binaural> <out.wav> [--master <json>]
//!                                                    a bed folded to a delivery layout (bed/fold.rs)
//!   rostrum-sound play <mix.wav | schedule.json> [..] the transport: the mix live (play / stop / seek / loop,
//!                                                    metronome, count-in, overdub notes and microphone takes;
//!                                                    JSON lines on stdin: live/play.rs)
//!   rostrum-sound live <instrument.json> [--shared] [--midi <n>] [--measure <notes>]
//!                                                    an instrument played live (MIDI / stdin), recorded as heard
//!   rostrum-sound model-samples <model.name> <dir>  a procedural instrument rendered ahead as samples + an
//!                                                    SFZ, so it plays live (instruments/model/samples.rs)
//!   rostrum-sound record <out.wav> [--seconds <s>]   a voiceover take from the default microphone (mono float WAV)
//!   rostrum-sound analyze <mono.f32> <rate> [--notes]  tempo, key, chords, notes, timbre of a recording (JSON)
//!   rostrum-sound inspect <clip.wav> [--png <out.png>]  what is wrong with a recording: clipping, clicks, hum,
//!                                                    room, sibilance, spectrum, noises; a spectrogram (analysis/inspect.rs)
//!   rostrum-sound plugins                            the installed CLAP / VST3 plugins and their parameters (JSON)
//!   rostrum-sound plugin <session.json> [--gui] [--audio] [--midi <n>]
//!                                                    one plugin opened for a person: its editor, heard live,
//!                                                    a preset loaded; its state handed back (plugins/session.rs)
//!   rostrum-sound plugin-presets <clap|vst3> <path> <id> [<name> <vendor>]   a plugin's presets (JSON)
//!   rostrum-sound midi                               the MIDI input devices and the audio outputs
//!                                                    (ROSTRUM_AUDIO_OUTPUT=<name> picks one for play / live / latency)
//!   rostrum-sound latency                            played note → speaker, measured (exclusive and shared mode)
//!
//! Each command lives with the module that owns it; this file only dispatches.

mod analysis;
mod bed;
mod dialogue;
mod fx;
mod instruments;
mod live;
mod mix;
mod plugins;
mod sfx;
mod stretch;


fn run() -> Result<(), String> {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match (args.first().map(String::as_str), args.len()) {
        (Some("render"), 3) => mix::render_cmd(&args),
        (Some("fold"), n) if n >= 4 => bed::fold::run(&args),
        (Some("layouts"), 1) => bed::layouts_cmd(),
        #[cfg(windows)]
        (Some("play"), n) if n >= 2 => live::play::run(&args),
        #[cfg(not(windows))]
        (Some("play"), 2) => live::graph::play_schedule(&args[1]),
        #[cfg(windows)]
        (Some("live"), n) if n >= 2 => live::perform::main(&args),
        #[cfg(windows)]
        (Some("record"), n) if n >= 2 => live::record::main(&args),
        #[cfg(windows)]
        (Some("plugin"), n) if n >= 2 => plugins::session::main(&args),
        (Some("plugin-presets"), n) if n >= 4 => plugins::presets::main(&args),
        (Some("plugins"), 1) => plugins::list_cmd(),
        (Some("analyze"), n) if n >= 3 => analysis::analyze_cmd(&args),
        (Some("model-samples"), 3) => instruments::model::samples::cmd(&args),
        (Some("inspect"), n) if n >= 2 => analysis::inspect_cmd(&args),
        #[cfg(windows)]
        (Some("midi"), 1) => live::midi::list_cmd(),
        #[cfg(windows)]
        (Some("latency"), 1) => live::perform::latency_cmd(),
        _ => Err("usage: rostrum-sound render <schedule.json> <out.wav> | fold <bed.wav> <stereo|5.1|binaural> <out.wav> [--master <json>] | play <schedule.json> | model-samples <model.name> <dir> | live <instrument.json> [--shared] [--midi <n>] [--measure <notes>] | record <out.wav> [--seconds <s>] | midi | latency".into()),
    }
}

fn main() {
    if let Err(e) = run() {
        eprintln!("rostrum-sound: {e}");
        std::process::exit(1);
    }
}

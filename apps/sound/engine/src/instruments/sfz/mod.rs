//! SFZ instruments (src/core/soundDsl/instruments/sampled.ts names them; the library is VSCO 2 CE, CC0): a
//! focused reader for the opcodes the shipped instruments use — regions with key / velocity
//! ranges, round robin (`seq_length` / `seq_position`, `lorand` / `hirand`, seeded so every render
//! is the same), `volume`, `tune`, `transpose`, `pan`, `offset`, `amp_veltrack`, the amp envelope
//! (`ampeg_delay` … `ampeg_release`), loops (`loop_mode`, `loop_start` / `loop_end`, or the WAV's
//! own `smpl` loop) — and a renderer. Each note plays on its own: its region's sample resampled to
//! the note's exact pitch, under its envelope and expression. TypeScript picks the articulation's
//! file; two of them are playing styles of the sustain samples: `legato` (a note that starts while
//! the previous one sounds enters past its attack and crossfades) and `swell` (a crescendo).
//! Also (2026-10-15, for the pianos and drum kits of the sfzinstruments / FreePats libraries):
//! release samples (`trigger=release`, quieter the longer the note was held: `rt_decay`, dB/s),
//! unpitched regions (`pitch_keytrack=0`: a hammer's noise), one-shots (`loop_mode=one_shot`: a
//! drum plays to its sample's end whatever the note's length), choke groups (`group` / `off_by`: a
//! closed hi-hat stops the open one) and FLAC samples (flac.rs). Regions a controller triggers
//! (`on_locc64` …: pedal noises) never play — the score has no pedal controller.
//! Also (2026-10-15, the instrument wave): the preprocessor (`#define`, `#include`: sfzpre.rs), and
//! controllers at their defaults with what is built on them — CC gates, CC modulations and curves,
//! crossfades by velocity, key and CC, velocity curves, `amp_random`, `width`, `note_polyphony` /
//! `off_time` (sfzctl.rs); `bend_*` is read and has no effect (a score bends no pitch wheel); WAVs in
//! the extensible format (16/24/32-bit integer, 32-bit float).
//! Anything else in the file is an error naming it, never a silent difference.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex, OnceLock};

use serde::Deserialize;

mod controls;
mod flac;
pub mod onset;
mod preprocess;
pub mod tame;

use crate::instruments::expression::Expression;

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct SfzSpec {
    pub file: String,
    #[serde(default)]
    pub legato: bool,
    #[serde(default)]
    pub swell: bool,
    /// An even kit (tame.rs): transients held in reach of each hit's loudness, and each key's starting level (dB).
    #[serde(default)]
    pub even: bool,
    #[serde(default)]
    pub gains: Vec<(u8, f64)>,
}

#[derive(Clone, Debug, PartialEq)]
pub struct Region {
    pub sample: PathBuf,
    pub lokey: u8, pub hikey: u8, pub keycenter: f64, pub lovel: u8, pub hivel: u8,
    pub lorand: f64, pub hirand: f64, pub seq_length: u32, pub seq_position: u32,
    pub volume: f64, pub tune: f64, pub pan: f64, pub offset: usize, pub veltrack: f64,
    pub looped: Option<(usize, usize)>, pub loop_mode: Option<bool>,
    pub delay: f64, pub attack: f64, pub hold: f64, pub decay: f64, pub sustain: f64, pub release: f64,
    /// Played when the note ends (`trigger=release`), its level falling `rt_decay` dB per second the note was held.
    pub on_release: bool, pub rt_decay: f64,
    /// How far the sample follows the key (pitch_keytrack / 100: 0 = the same pitch on every key).
    pub keytrack: f64,
    /// `loop_mode=one_shot`: plays to its end whatever the note's length (unless choked).
    pub one_shot: bool,
    /// A note in `group` stops the sounding notes whose `off_by` is that group (0: none).
    pub group: u32, pub off_by: u32,
    /// Triggered by a controller (`on_locc*`), not a key: never played.
    pub cc_only: bool,
    /// Controller-derived and per-note shaping (sfzctl.rs).
    pub ext: controls::Ext,
}

/// Opcodes read as they are; those that only label or that the engine decides itself are accepted and ignored.
const IGNORED: &[&str] = &["group_label", "region_label", "ampeg_dynamic", "sw_label", "master_label", "global_label", "bend_up", "bend_down", "bend_step"];

/// "c4", "c#4", "db4" or a number → a MIDI key (c4 = 60).
fn note(v: &str) -> Result<f64, String> {
    if let Ok(n) = v.parse::<f64>() { return Ok(n); }
    let b = v.to_ascii_lowercase();
    let mut c = b.chars();
    let base = match c.next() { Some('c') => 0, Some('d') => 2, Some('e') => 4, Some('f') => 5, Some('g') => 7, Some('a') => 9, Some('b') => 11, _ => return Err(format!("\"{v}\" is not a key")) };
    let rest: String = c.collect();
    let (acc, oct) = if let Some(r) = rest.strip_prefix('#') { (1, r) } else if let Some(r) = rest.strip_prefix('b') { (-1, r) } else { (0, rest.as_str()) };
    let oct: i32 = oct.parse().map_err(|_| format!("\"{v}\" is not a key"))?;
    Ok(((oct + 1) * 12 + base + acc) as f64)
}

/// Parses an SFZ text; samples resolve against `dir` (and `default_path`).
pub fn parse(text: &str, dir: &Path) -> Result<Vec<Region>, String> {
    let clean = preprocess::preprocess(text, dir)?;
    // Levels: global < master < group < region; a header resets its own level and the ones below.
    let mut scopes: [HashMap<String, String>; 4] = Default::default();
    let mut control: HashMap<String, String> = HashMap::new();
    let mut curves: Vec<HashMap<String, String>> = vec![];
    // Regions are read once every header is known (the controllers' defaults and curves may come after them).
    let (mut cur, mut pending) = (usize::MAX, vec![]);
    for t in tokenize(&clean) {
        if let Some(h) = t.strip_prefix('<').and_then(|h| h.strip_suffix('>')) {
            if cur == 3 { pending.push(scopes.clone()); }
            cur = match h { "control" => 4, "global" => 0, "master" => 1, "group" => 2, "region" => 3, "curve" => 6, "effect" | "midi" => 5, _ => return Err(format!("SFZ header <{h}> is not supported")) };
            if cur < 4 { for s in scopes.iter_mut().skip(cur) { s.clear(); } }
            if cur == 6 { curves.push(HashMap::new()); }
        } else if let Some((k, v)) = t.split_once('=') {
            match cur { 4 => { control.insert(k.into(), v.into()); } 0..=3 => { scopes[cur].insert(k.into(), v.into()); } 6 => { curves.last_mut().unwrap().insert(k.into(), v.into()); } 5 => {} _ => return Err(format!("SFZ opcode {k} before any header")) }
        }
    }
    if cur == 3 { pending.push(scopes.clone()); }
    let controls = controls::Controls::new(&control, &curves)?;
    let mut regions = vec![];
    for s in &pending { if let Some(r) = region(s, &control, &controls, dir)? { regions.push(r); } }
    Ok(regions)
}

/// Splits into headers and opcode=value pairs; a `sample=` value runs to the next opcode (file names have spaces).
fn tokenize(s: &str) -> Vec<String> {
    let mut out: Vec<String> = vec![];
    for word in s.split(|c: char| c.is_whitespace() || c == '<').filter(|w| !w.is_empty()) {
        let w = if word.ends_with('>') && !word.contains('=') { format!("<{word}") } else { word.to_string() };
        let joins = !w.starts_with('<') && !w.contains('=') && out.last().is_some_and(|l| l.starts_with("sample=") || l.starts_with("default_path="));
        if joins { let l = out.last_mut().unwrap(); l.push(' '); l.push_str(&w); } else { out.push(w); }
    }
    out
}

/// A region from its merged scopes, or None when a controller gate keeps it silent.
fn region(scopes: &[HashMap<String, String>; 4], control: &HashMap<String, String>, controls: &controls::Controls, dir: &Path) -> Result<Option<Region>, String> {
    let mut o: HashMap<&str, &str> = HashMap::new();
    for s in scopes { for (k, v) in s { o.insert(k, v); } }
    let mut used = vec![];
    let Some((add, ext)) = controls::region(&o, controls, &mut used)? else { return Ok(None) };
    // A plain opcode's value, plus what its controllers add.
    let num = |k: &str, d: f64| -> Result<f64, String> { Ok(o.get(k).map_or(Ok(d), |v| v.parse().map_err(|_| format!("SFZ {k}={v} is not a number")))? + add.get(k).copied().unwrap_or(0.0)) };
    let key = |k: &str, d: f64| -> Result<f64, String> { o.get(k).map_or(Ok(d), |v| note(v)) };
    let mut r = Region {
        sample: PathBuf::new(), lokey: 0, hikey: 127, keycenter: 60.0, lovel: 0, hivel: 127, lorand: 0.0, hirand: 1.0, seq_length: 1, seq_position: 1,
        volume: num("volume", 0.0)?, tune: num("tune", 0.0)? + 100.0 * num("transpose", 0.0)?, pan: num("pan", 0.0)? / 100.0, offset: num("offset", 0.0)? as usize,
        veltrack: num("amp_veltrack", 100.0)? / 100.0, looped: None, loop_mode: None,
        delay: num("ampeg_delay", 0.0)?, attack: num("ampeg_attack", 0.0)?, hold: num("ampeg_hold", 0.0)?, decay: num("ampeg_decay", 0.0)?, sustain: num("ampeg_sustain", 100.0)? / 100.0, release: num("ampeg_release", 0.001)?,
        on_release: o.get("trigger").is_some_and(|t| *t == "release"), rt_decay: num("rt_decay", 0.0)?, keytrack: num("pitch_keytrack", 100.0)? / 100.0,
        one_shot: o.get("loop_mode").is_some_and(|m| *m == "one_shot"), group: num("group", 0.0)? as u32, off_by: num("off_by", 0.0)? as u32,
        cc_only: o.keys().any(|k| k.starts_with("on_locc") || k.starts_with("on_hicc")), ext,
    };
    if let Some(k) = o.get("key") { let k = note(k)?; (r.lokey, r.hikey, r.keycenter) = (k as u8, k as u8, k); }
    r.lokey = key("lokey", r.lokey as f64)? as u8;
    r.hikey = key("hikey", r.hikey as f64)? as u8;
    r.keycenter = key("pitch_keycenter", r.keycenter)?;
    (r.lovel, r.hivel) = (num("lovel", 0.0)? as u8, num("hivel", 127.0)? as u8);
    (r.lorand, r.hirand) = (num("lorand", 0.0)?, num("hirand", 1.0)?);
    (r.seq_length, r.seq_position) = (num("seq_length", 1.0)? as u32, num("seq_position", 1.0)? as u32);
    if let (Some(a), Some(b)) = (o.get("loop_start"), o.get("loop_end")) { r.looped = Some((a.parse().unwrap_or(0), b.parse().unwrap_or(0))); }
    r.loop_mode = match o.get("loop_mode").copied() { None => None, Some("no_loop") | Some("one_shot") => Some(false), Some("loop_continuous") | Some("loop_sustain") => Some(true), Some(m) => return Err(format!("SFZ loop_mode={m} is not supported")) };
    if o.get("trigger").is_some_and(|t| *t != "attack" && *t != "release") { return Err("SFZ trigger= other than attack and release (first, legato) is not supported".into()); }
    let known = ["sample", "key", "lokey", "hikey", "pitch_keycenter", "lovel", "hivel", "lorand", "hirand", "seq_length", "seq_position", "volume", "tune", "transpose", "pan", "offset", "amp_veltrack", "loop_mode", "loop_start", "loop_end", "trigger", "ampeg_delay", "ampeg_attack", "ampeg_hold", "ampeg_decay", "ampeg_sustain", "ampeg_release", "rt_decay", "pitch_keytrack", "group", "off_by"];
    let by_controller = |k: &str| k.starts_with("on_locc") || k.starts_with("on_hicc");
    if let Some(k) = o.keys().find(|k| !known.contains(k) && !IGNORED.contains(k) && !k.starts_with("sw_") && !by_controller(k) && !used.iter().any(|u| u == *k)) { return Err(format!("SFZ opcode {k} is not supported")); }
    if o.keys().any(|k| k.starts_with("sw_")) { return Err("keyswitch SFZ files (sw_*) are not played: pick the articulation's own file".into()); }
    let sample = o.get("sample").ok_or("SFZ region without a sample")?.replace('\\', "/");
    let base = control.get("default_path").map(|p| p.replace('\\', "/")).unwrap_or_default();
    r.sample = dir.join(format!("{base}{sample}"));
    Ok(Some(r))
}

/// Regions for a key and velocity (1 … 127), the `nth` time this key is struck, `rand` 0 … 1.
pub fn select(regions: &[Region], key: u8, vel: u8, nth: u32, rand: f64) -> Vec<&Region> {
    select_on(regions, false, key, vel, nth, rand)
}

/// The same for the regions a note's end plays (`on_release`) or its start (else).
pub fn select_on(regions: &[Region], on_release: bool, key: u8, vel: u8, nth: u32, rand: f64) -> Vec<&Region> {
    regions.iter().filter(|r| !r.cc_only && r.on_release == on_release && key >= r.lokey && key <= r.hikey && vel >= r.lovel && vel <= r.hivel && rand >= r.lorand && (rand < r.hirand || r.hirand >= 1.0) && nth % r.seq_length.max(1) + 1 == r.seq_position).collect()
}

/// A decoded sample: interleaved stereo frames, its rate, the file's own loop, and where it is heard (frames from its
/// start: onset.rs).
pub struct Sample { pub frames: Vec<[f32; 2]>, pub rate: f64, pub looped: Option<(usize, usize)>, pub onset: usize }

impl Sample {
    pub fn new(frames: Vec<[f32; 2]>, rate: f64, looped: Option<(usize, usize)>) -> Sample {
        let onset = onset::find(&frames, rate, 0);
        Sample { frames, rate, looped, onset }
    }

    /// Frames from `from` (a region's `offset`) to where the sample is heard.
    pub fn onset_from(&self, from: usize) -> usize {
        if from <= self.onset { self.onset - from } else { onset::find(&self.frames, self.rate, from) }
    }
}

pub fn read_wav(path: &Path) -> Result<Sample, String> {
    if path.extension().is_some_and(|e| e.eq_ignore_ascii_case("flac")) { return flac::read_flac(path); }
    let b = std::fs::read(path).map_err(|e| format!("{}: {e}", path.display()))?;
    if b.len() < 12 || &b[0..4] != b"RIFF" || &b[8..12] != b"WAVE" { return Err(format!("{}: not a WAV file", path.display())); }
    let (mut fmt, mut data, mut looped, mut p) = (None, None, None, 12);
    // WAVE_FORMAT_EXTENSIBLE: its subformat GUID starts with the plain format code (1 PCM, 3 float).
    let mut sub: Option<u16> = None;
    while p + 8 <= b.len() {
        let n = u32::from_le_bytes(b[p + 4..p + 8].try_into().unwrap()) as usize;
        let body = &b[p + 8..(p + 8 + n).min(b.len())];
        match &b[p..p + 4] {
            b"fmt " if body.len() >= 26 && u16::from_le_bytes([body[0], body[1]]) == 0xFFFE => { sub = Some(u16::from_le_bytes([body[24], body[25]])); fmt = Some((0xFFFE, u16::from_le_bytes([body[2], body[3]]) as usize, u32::from_le_bytes(body[4..8].try_into().unwrap()), u16::from_le_bytes([body[14], body[15]]))); }
            b"fmt " if body.len() >= 16 => fmt = Some((u16::from_le_bytes([body[0], body[1]]), u16::from_le_bytes([body[2], body[3]]) as usize, u32::from_le_bytes(body[4..8].try_into().unwrap()), u16::from_le_bytes([body[14], body[15]]))),
            b"data" => data = Some(body),
            b"smpl" if body.len() >= 60 && u32::from_le_bytes(body[28..32].try_into().unwrap()) > 0 => looped = Some((u32::from_le_bytes(body[44..48].try_into().unwrap()) as usize, u32::from_le_bytes(body[48..52].try_into().unwrap()) as usize)),
            _ => {}
        }
        p += 8 + n + (n & 1);
    }
    let ((format, ch, rate, bits), data) = (fmt.ok_or(format!("{}: no fmt chunk", path.display()))?, data.ok_or(format!("{}: no data chunk", path.display()))?);
    let format = if format == 0xFFFE { sub.unwrap_or(0) } else { format };
    let width = bits as usize / 8;
    let read = |s: &[u8]| -> f32 { match (format, bits) {
        (1, 16) => i16::from_le_bytes([s[0], s[1]]) as f32 / 32768.0,
        (1, 24) => (i32::from_le_bytes([0, s[0], s[1], s[2]]) >> 8) as f32 / 8388608.0,
        (1, 32) => i32::from_le_bytes(s.try_into().unwrap()) as f32 / 2147483648.0,
        _ => f32::from_le_bytes(s.try_into().unwrap()),
    } };
    if !matches!((format, bits), (1, 16) | (1, 24) | (1, 32) | (3, 32)) || ch == 0 { return Err(format!("{}: WAV format {format} at {bits} bits is not supported", path.display())); }
    let frame = width * ch;
    let frames = data.chunks_exact(frame).map(|f| { let l = read(&f[..width]); [l, if ch > 1 { read(&f[width..2 * width]) } else { l }] }).collect();
    Ok(Sample::new(frames, rate as f64, looped))
}

/// Files load once per process and are shared between clips.
fn cached<T: Send + Sync + 'static>(path: &Path, load: impl FnOnce(&Path) -> Result<T, String>) -> Result<Arc<T>, String> {
    static CACHE: OnceLock<Mutex<HashMap<(PathBuf, std::any::TypeId), Arc<dyn std::any::Any + Send + Sync>>>> = OnceLock::new();
    let k = (path.to_path_buf(), std::any::TypeId::of::<T>());
    if let Some(v) = CACHE.get_or_init(Default::default).lock().unwrap().get(&k) { return Ok(v.clone().downcast().unwrap()); }
    let v: Arc<T> = Arc::new(load(path)?);
    CACHE.get().unwrap().lock().unwrap().insert(k, v.clone());
    Ok(v)
}

pub fn instrument(file: &str) -> Result<Arc<Vec<Region>>, String> {
    cached(Path::new(file), |p| {
        let text = std::fs::read_to_string(p).map_err(|e| format!("{file}: {e}"))?;
        parse(&text, p.parent().unwrap_or(Path::new("."))).map_err(|e| format!("{file}: {e}"))
    })
}

/// A note to play: start and length in samples, its pitches, velocity 0 … 1, pan −1 … 1, its expression.
pub struct Note<'a> { pub start: usize, pub len: usize, pub freqs: &'a [f64], pub velocity: f64, pub pan: f64, pub expression: Option<&'a Expression> }

const LEGATO_SKIP: f64 = 0.09; // seconds of the sample's attack a legato note enters past
pub const LEGATO_FADE: f64 = 0.07;

/// Adds the notes (one instrument) into the buffers.
pub fn render(spec: &SfzSpec, notes: &[Note], left: &mut [f32], right: &mut [f32], sr: f64) -> Result<(), String> {
    let regions = instrument(&spec.file)?;
    let mut order: Vec<usize> = (0..notes.len()).collect();
    order.sort_by_key(|&i| notes[i].start);
    let mut struck: HashMap<u8, u32> = HashMap::new();
    let choked = chokes(&regions, notes, &order);
    let mut ends: Vec<(usize, Option<f64>, bool)> = notes.iter().map(|n| (n.start + n.len, None, false)).collect();
    if spec.legato {
        // Each note that starts while the previous one still sounds: the previous one hands over in a crossfade.
        for w in order.windows(2) {
            let (a, b) = (w[0], w[1]);
            if notes[b].start <= ends[a].0 + (0.02 * sr) as usize && notes[b].start > notes[a].start { ends[a] = (notes[b].start + (LEGATO_FADE * sr) as usize, Some(LEGATO_FADE), ends[a].2); ends[b].2 = true; }
        }
    }
    for (k, &i) in order.iter().enumerate() {
        let n = &notes[i];
        let vel = (n.velocity.clamp(0.0, 1.0) * 127.0).round().clamp(1.0, 127.0) as u8;
        for (j, &f) in n.freqs.iter().enumerate() {
            let midi = 69.0 + 12.0 * (f / 440.0).log2();
            let key = midi.round().clamp(0.0, 127.0) as u8;
            let nth = { let c = struck.entry(key).or_insert(0); *c += 1; *c - 1 };
            let rand = ((k as u64 * 0x9E37_79B9 + j as u64 * 0x85EB_CA6B + key as u64) % 10007) as f64 / 10007.0;
            let hits = select(&regions, key, vel, nth, rand);
            if hits.is_empty() {
                let name = |k: u8| format!("{}{}", ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"][k as usize % 12], k as i32 / 12 - 1);
                let (lo, hi) = (regions.iter().map(|r| r.lokey).min().unwrap_or(0), regions.iter().map(|r| r.hikey).max().unwrap_or(0));
                return Err(format!("{}: no sample for {} (key {key}) at velocity {vel}; the instrument plays {}–{}", spec.file, name(key), name(lo), name(hi)));
            }
            let (off, release, legato) = ends[i];
            let level = spec.gains.iter().find(|(k, _)| *k == key).map_or(0.0, |g| g.1);
            for r in hits {
                let sample = if spec.even { cached(&r.sample, tame::read)?.0.clone() } else { cached(&r.sample, read_wav)? };
                let mut v = SfzVoice::new(r, sample, midi, n.velocity, n.pan, legato, spec.swell, n.len as f64 / sr, n.expression.cloned(), sr);
                v.gain *= 10f64.powf(level / 20.0);
                // It starts its attack early so it is heard on its time (onset.rs; a legato note enters past its attack;
                // a note in the song's first moments starts at 0, as late as its attack); it is still let go at its end.
                let at = if legato { n.start } else { n.start.saturating_sub(v.lead()) };
                // A one-shot rings to its sample's end unless a note of its choke group stops it.
                match (r.one_shot, choked[i]) {
                    (false, c) => v.release(off.min(c.unwrap_or(usize::MAX)).saturating_sub(at), if c.is_some_and(|c| c < off) { Some(choke(r)) } else { release }),
                    (true, Some(c)) => v.release(c.saturating_sub(at), Some(choke(r))),
                    (true, None) => {}
                }
                mix(&mut v, at, left, right);
            }
            // The note's release samples (string resonance, hammer noise), from its end, softer the longer it was held.
            for r in select_on(&regions, true, key, vel, nth, rand) {
                let held = off.saturating_sub(n.start) as f64 / sr;
                let mut v = SfzVoice::new(r, cached(&r.sample, read_wav)?, midi, n.velocity * 10f64.powf(-r.rt_decay * held / 20.0), n.pan, false, false, 0.0, None, sr);
                // It plays to its sample's end (no note-off of its own).
                mix(&mut v, off, left, right);
            }
        }
    }
    Ok(())
}

/// Seconds a choked note fades out over: its `off_time` when it sets one, else 30 ms.
const CHOKE: f64 = 0.03;
fn choke(r: &Region) -> f64 { r.ext.off_time.unwrap_or(if r.ext.note_polyphony.is_some() { 0.006 } else { CHOKE }) }

/// Adds a voice from sample `at` into the buffers until it finishes.
fn mix(v: &mut SfzVoice, at: usize, left: &mut [f32], right: &mut [f32]) {
    for k in at..left.len().min(right.len()) {
        let Some((a, b)) = v.next() else { break };
        left[k] += a;
        right[k] += b;
    }
}

/// Where each note is choked: the start of the first later note whose key is in the group its key's `off_by` names.
fn chokes(regions: &[Region], notes: &[Note], order: &[usize]) -> Vec<Option<usize>> {
    let key = |n: &Note| n.freqs.first().map(|&f| (69.0 + 12.0 * (f / 440.0).log2()).round().clamp(0.0, 127.0) as u8);
    let of = |n: &Note| key(n).and_then(|k| regions.iter().find(|r| !r.cc_only && !r.on_release && k >= r.lokey && k <= r.hikey)).map_or((0, 0, None), |r| (r.group, r.off_by, r.ext.note_polyphony));
    let mut out = vec![None; notes.len()];
    for (x, &a) in order.iter().enumerate() {
        let (_, off, poly) = of(&notes[a]);
        let later = || order[x + 1..].iter().filter(|&&b| notes[b].start > notes[a].start);
        let by_group = if off == 0 { None } else { later().find(|&&b| of(&notes[b]).0 == off).map(|&b| notes[b].start) };
        // note_polyphony = n: the n-th later strike of the same key stops it.
        let by_key = poly.filter(|&n| n > 0).and_then(|n| later().filter(|&&b| key(&notes[b]) == key(&notes[a])).nth(n as usize - 1).map(|&b| notes[b].start));
        out[a] = match (by_group, by_key) { (Some(g), Some(k)) => Some(g.min(k)), (g, k) => g.or(k) };
    }
    out
}

/// One sounding region of a note: its sample read at the note's pitch under the region's envelope.
/// Gate-based — it sustains until `release` — so a score (which knows each note's end) and a live
/// key (which does not) play the same voice.
pub struct SfzVoice {
    s: Arc<Sample>,
    r: Region,
    gain: f64,
    pl: f32,
    pr: f32,
    step: f64,
    looped: Option<(usize, usize)>,
    /// A sustained note longer than its sample (which has no loop of its own: VSCO's are ~10 s):
    /// (loop end, loop length, crossfade) in frames — the last stretch is crossfaded back so it holds.
    auto: Option<(f64, f64, f64)>,
    release: f64,
    attack: f64,
    /// Samples into the voice where its release starts (usize::MAX while held).
    note_end: usize,
    /// The note's length in seconds for `swell` and the expression's shape (a score's; live: none).
    dur: f64,
    swell: bool,
    expression: Option<Expression>,
    pos: f64,
    i: usize,
    sr: f64,
}

impl SfzVoice {
    #[allow(clippy::too_many_arguments)]
    pub fn new(r: &Region, s: Arc<Sample>, midi: f64, velocity: f64, pan: f64, legato: bool, swell: bool, dur: f64, expression: Option<Expression>, sr: f64) -> SfzVoice {
        let r = &noted(r, midi, velocity);
        // amp_random's draw: seeded by the note (key, velocity), so a re-render is identical.
        let seed = ((midi * 7919.0 + velocity * 104_729.0).sin() * 43_758.545).fract().abs();
        let gain = 10f64.powf(r.volume / 20.0) * r.ext.note_gain(r.veltrack, midi, velocity, seed);
        let pan = (r.pan + pan).clamp(-1.0, 1.0);
        let (pl, pr) = (((1.0 - pan) * 0.5).sqrt() * std::f64::consts::SQRT_2, ((1.0 + pan) * 0.5).sqrt() * std::f64::consts::SQRT_2);
        let step = 2f64.powf(((midi - r.keycenter) * r.keytrack + r.tune / 100.0) / 12.0) * s.rate / sr;
        let looped = if r.loop_mode == Some(false) { None } else { r.looped.or(s.looped).filter(|&(a, b)| b > a + 1 && b < s.frames.len()) };
        let pos = r.offset as f64 + if legato { LEGATO_SKIP * s.rate } else { 0.0 };
        let len = s.frames.len() as f64;
        let auto = (looped.is_none() && r.loop_mode != Some(false) && dur * sr * step > (len - pos) * 0.9 && len > s.rate * 2.0).then(|| {
            // Loop the sample's later body (past the attack), ending 0.25 s before its end, crossfading 0.3 s.
            let end = len - 0.25 * s.rate;
            let span = (end * 0.45).min(4.0 * s.rate).max(0.8 * s.rate);
            (end, span, (0.3 * s.rate).min(span * 0.5))
        });
        SfzVoice { gain, pl: pl as f32, pr: pr as f32, step, looped, auto, release: r.release.max(0.002), attack: if legato { LEGATO_FADE } else { r.attack }, note_end: usize::MAX, dur, swell, expression, pos, i: 0, sr, r: r.clone(), s }
    }

    /// Output samples from the voice's start to where it is heard (onset.rs): the sample's attack at the note's pitch,
    /// after the region's delay, at most `onset::MAX_LEAD`.
    pub fn lead(&self) -> usize {
        let frames = self.s.onset_from(self.pos as usize) as f64 / self.step.max(1e-9);
        ((frames + self.r.delay * self.sr).min(onset::MAX_LEAD * self.sr)).round() as usize
    }

    /// Releases `after` samples from now, over `over` seconds (else the region's own release).
    pub fn release(&mut self, after: usize, over: Option<f64>) {
        if self.note_end == usize::MAX {
            self.note_end = self.i + after;
            if let Some(o) = over {
                self.release = o.max(0.002);
            }
        }
    }

    pub fn held(&self) -> bool {
        self.note_end == usize::MAX
    }

    /// The next frame, or None once it has finished (released out, or the sample ran out).
    pub fn next(&mut self) -> Option<(f32, f32)> {
        let (r, i, sr) = (&self.r, self.i, self.sr);
        let t = i as f64 / sr;
        let attack = self.attack;
        let mut env = if t < r.delay { 0.0 } else {
            let u = t - r.delay;
            if u < attack { u / attack.max(1e-6) } else if u < attack + r.hold { 1.0 } else if u < attack + r.hold + r.decay { 1.0 - (1.0 - r.sustain) * (u - attack - r.hold) / r.decay } else { r.sustain }
        };
        if i >= self.note_end { let x = (i - self.note_end) as f64 / sr / self.release; if x >= 1.0 { return None; } env *= (1.0 - x).powi(2); }
        if self.swell { let x = (t / (self.dur * 0.65).max(0.05)).min(1.0); env *= 0.12 + 0.88 * x * x * (3.0 - 2.0 * x); }
        if let Some(e) = &self.expression { env *= e.gain(t, self.dur); }
        let p = self.pos as usize;
        if p + 1 >= self.s.frames.len() { return None; }
        let at = |q: f64| { let p = q as usize; let f = (q - p as f64) as f32; let (a, b) = (self.s.frames[p], self.s.frames[(p + 1).min(self.s.frames.len() - 1)]); [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f] };
        let mut x = at(self.pos);
        // The automatic loop's crossfade: the end of the stretch fades (equal power) into its start.
        if let Some((end, span, fade)) = self.auto {
            if self.pos > end - fade {
                let w = ((self.pos - (end - fade)) / fade).clamp(0.0, 1.0);
                let y = at(self.pos - span);
                let (ga, gb) = (((1.0 - w) * std::f64::consts::FRAC_PI_2).sin() as f32, (w * std::f64::consts::FRAC_PI_2).sin() as f32);
                x = [x[0] * ga + y[0] * gb, x[1] * ga + y[1] * gb];
            }
        }
        let g = (self.gain * env) as f32;
        // `width`: the side signal scaled (1 = as recorded, 0 = mono).
        if self.r.ext.width != 1.0 { let (m, d) = ((x[0] + x[1]) * 0.5, (x[0] - x[1]) * 0.5 * self.r.ext.width as f32); x = [m + d, m - d]; }
        let out = (x[0] * g * self.pl, x[1] * g * self.pr);
        self.pos += self.step * self.expression.as_ref().map_or(1.0, |e| e.ratio(t));
        if let Some((a, b)) = self.looped { if self.pos >= b as f64 { self.pos -= (b - a) as f64; } }
        if let Some((end, span, _)) = self.auto { if self.pos >= end { self.pos -= span; } }
        self.i += 1;
        Some(out)
    }
}

/// The region as this note plays it: its velocity/key modulations (extended controllers 131 / 133) added.
fn noted(r: &Region, midi: f64, velocity: f64) -> Region {
    let mut r = r.clone();
    let deltas: Vec<(String, f64)> = r.ext.per_note_deltas(midi, velocity).into_iter().map(|(t, d)| (t.to_string(), d)).collect();
    for (t, d) in deltas {
        match t.as_str() {
            "volume" => r.volume += d, "pan" => r.pan += d / 100.0, "tune" => r.tune += d, "offset" => r.offset = (r.offset as f64 + d).max(0.0) as usize,
            "amp_veltrack" => r.veltrack += d / 100.0, "ampeg_delay" => r.delay += d, "ampeg_attack" => r.attack += d, "ampeg_hold" => r.hold += d,
            "ampeg_decay" => r.decay += d, "ampeg_sustain" => r.sustain += d / 100.0, "ampeg_release" => r.release += d, _ => r.ext.width += d / 100.0,
        }
    }
    (r.delay, r.attack, r.hold, r.decay, r.release, r.sustain) = (r.delay.max(0.0), r.attack.max(0.0), r.hold.max(0.0), r.decay.max(0.0), r.release.max(0.0), r.sustain.clamp(0.0, 1.0));
    r
}

/// A live SFZ instrument's samples, all decoded up front (no file is read while a key is played).
pub fn preload(file: &str) -> Result<(Arc<Vec<Region>>, HashMap<PathBuf, Arc<Sample>>), String> {
    let regions = instrument(file)?;
    let mut samples = HashMap::new();
    for r in regions.iter() {
        if !samples.contains_key(&r.sample) {
            samples.insert(r.sample.clone(), cached(&r.sample, read_wav)?);
        }
    }
    Ok((regions, samples))
}

/// A key struck live: its regions (round robin by strike count, `rand` from the strike).
pub fn strike(regions: &[Region], samples: &HashMap<PathBuf, Arc<Sample>>, key: u8, velocity: f64, nth: u32, legato: bool, sr: f64) -> Vec<SfzVoice> {
    let vel = (velocity.clamp(0.0, 1.0) * 127.0).round().clamp(1.0, 127.0) as u8;
    let rand = ((nth as u64 * 0x9E37_79B9 + key as u64) % 10007) as f64 / 10007.0;
    select(regions, key, vel, nth, rand).into_iter().filter_map(|r| samples.get(&r.sample).map(|s| SfzVoice::new(r, s.clone(), key as f64, velocity, 0.0, legato, false, 0.0, None, sr))).collect()
}

#[cfg(test)]
mod tests;

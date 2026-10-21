//! A procedural instrument rendered ahead as a multisample, so it plays live (`rostrum-sound
//! model-samples <name> <dir>`). Live, a note's length and the next note are not known when its key goes
//! down, so the model cannot render the part as it does in a mix; instead each key region (every few
//! semitones over the instrument's range, every piece of the kit) is rendered once at three velocities
//! by the same model, held for a long note, and written with an SFZ file that plays them (sfz.rs: the
//! sample repitched across its region, released when the key is let go). The host caches the folder
//! by the engine build (AGENTS.md rule 9), so it is rendered once. What live play loses against the
//! mix: a string cut by the next note on it, a bowed line slurring into the next, an open hat choked.

use super::Note;

/// The rendering: keys `lo ..= hi` every `step` semitones, each held `hold` s and given `tail` s to ring,
/// released over `release` s when its key is let go.
struct Plan {
    lo: u8,
    hi: u8,
    step: u8,
    hold: f64,
    tail: f64,
    release: f64,
}

fn plan(name: &str) -> Option<Plan> {
    let p = |lo, hi, step, hold, tail, release| Some(Plan { lo, hi, step, hold, tail, release });
    match name {
        "model.guitar" => p(40, 88, 3, 4.0, 0.6, 0.15),
        "model.nylonGuitar" => p(40, 83, 3, 4.0, 0.6, 0.15),
        // Bars with no damper ring on after the key is let go.
        "model.marimba" => p(45, 96, 3, 2.0, 0.4, 2.0),
        "model.vibraphone" => p(53, 89, 3, 5.0, 0.6, 0.25),
        "model.glockenspiel" => p(79, 108, 3, 3.0, 0.6, 3.0),
        "model.tubularBell" => p(60, 77, 2, 6.0, 1.5, 1.5),
        "ddsp.violin" => p(55, 100, 3, 4.0, 0.3, 0.12),
        // The kit: one region per General MIDI piece, each a one-shot (the key's release does not cut it).
        "model.kit" => p(35, 59, 1, 0.2, 3.0, 4.0),
        _ => None,
    }
}

/// The velocity layers: (rendered velocity, lowest and highest MIDI velocity it plays).
const LAYERS: [(f64, u8, u8); 3] = [(0.35, 1, 60), (0.65, 61, 100), (0.95, 101, 127)];

/// One sample: the model's note at `key` and `velocity`, its silent end trimmed, as a stereo float WAV.
fn sample(name: &str, p: &Plan, key: u8, velocity: f64, sr: f64) -> Result<Vec<u8>, String> {
    let n = ((p.hold + p.tail) * sr) as usize;
    let (mut l, mut r) = (vec![0f32; n], vec![0f32; n]);
    let freq = 440.0 * 2f64.powf((key as f64 - 69.0) / 12.0);
    let note = Note { start: 0, len: (p.hold * sr) as usize, freq, velocity, pan: 0.0, expression: None, hardness: None, position: None, damping: None };
    super::render(name, &[note], &mut l, &mut r, sr)?;
    // −90 dBFS and below at the end is silence.
    let end = l.iter().zip(&r).rposition(|(a, b)| a.abs().max(b.abs()) > 3e-5).map_or(1, |i| i + 1);
    Ok(crate::mix::wavio::write(&[l[..end].to_vec(), r[..end].to_vec()], crate::bed::Layout::Stereo, sr as u32))
}

/// Renders the instrument's samples into `dir` (made when missing) with their `instrument.sfz`; returns its path.
pub fn write(name: &str, dir: &std::path::Path, sr: f64) -> Result<std::path::PathBuf, String> {
    let p = plan(name).ok_or(format!("no procedural instrument \"{name}\" (have {})", super::NAMES.join(", ")))?;
    std::fs::create_dir_all(dir).map_err(|e| format!("{}: {e}", dir.display()))?;
    // The kit also has its shaker, past the drums and cymbals (kit.rs).
    let centers: Vec<u8> = (p.lo..=p.hi).step_by(p.step as usize).chain((name == "model.kit").then_some(70)).collect();
    let jobs: Vec<(usize, u8, usize)> = centers.iter().enumerate().flat_map(|(i, &k)| (0..LAYERS.len()).map(move |v| (i, k, v))).collect();
    let rendered = crate::mix::par::map(jobs.clone(), |(_, key, v)| sample(name, &p, key, LAYERS[v].0, sr));
    let mut sfz = format!("// {name}, rendered ahead by rostrum-sound (model/samples.rs) to play live.\n<global> amp_veltrack=0 ampeg_release={}\n", p.release);
    for ((i, key, v), wav) in jobs.into_iter().zip(rendered) {
        let file = format!("{key}-v{v}.wav");
        std::fs::write(dir.join(&file), wav?).map_err(|e| format!("{}: {e}", dir.join(&file).display()))?;
        // A region reaches halfway to its neighbours; the ends take every key past them.
        let lokey = if i == 0 { 0 } else { key - p.step / 2 };
        let hikey = if i + 1 == centers.len() { 127 } else { key + (p.step - 1) / 2 };
        let (lokey, hikey) = if name == "model.kit" { (key, key) } else { (lokey, hikey) };
        let (_, lovel, hivel) = LAYERS[v];
        sfz.push_str(&format!("<region> sample={file} lokey={lokey} hikey={hikey} pitch_keycenter={key} lovel={lovel} hivel={hivel}\n"));
    }
    let out = dir.join("instrument.sfz");
    std::fs::write(&out, sfz).map_err(|e| format!("{}: {e}", out.display()))?;
    Ok(out)
}

/// `rostrum-sound model-samples <model.name> <dir>`.
pub fn cmd(args: &[String]) -> Result<(), String> {
    let t0 = std::time::Instant::now();
    let sfz = write(&args[1], std::path::Path::new(&args[2]), 48000.0)?;
    println!("{}", serde_json::json!({ "sfz": sfz.to_string_lossy(), "renderSeconds": t0.elapsed().as_secs_f64() }));
    Ok(())
}

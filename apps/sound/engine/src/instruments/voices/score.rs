//! A score clip: every voice of it rendered and summed in the schedule's order.

use super::Voice;

/// A score clip's voices into its buffers, in the schedule's order (as the TS mixdown summed them);
/// a sampler's notes play through one SoundFont synthesizer for the clip.
pub fn render_score(voices: &[crate::mix::schedule::Voice], left: &mut [f32], right: &mut [f32], sr: f64, span: Option<(usize, usize)>) -> Result<(), String> {
    use crate::mix::schedule::Voice as V;
    // A heard stretch (mix/window.rs, clip frames): only the notes that sound in it. SFZ notes all go in, so its
    // round robin counts every strike; it leaves out the ones not heard itself.
    let heard = |v: &V| match v {
        V::Note { start_idx, duration, .. } => crate::mix::window::heard(span, *start_idx, (duration * sr).round() as usize, sr),
        V::Drum { start_idx, .. } => crate::mix::window::heard(span, *start_idx, 0, sr),
    };
    let all = voices;
    let kept: Vec<V> = if span.is_some() { voices.iter().filter(|v| heard(v)).cloned().collect() } else { vec![] };
    let voices: &[V] = if span.is_some() { &kept } else { voices };
    let sampled: Vec<_> = voices
        .iter()
        .filter_map(|v| match v {
            V::Note { sampler: Some(s), freqs, start_idx, duration, velocity, expression, variation, .. } => {
                Some((s, crate::instruments::sampler::Note { start: *start_idx, len: (duration * sr).round() as usize, freqs: freqs.as_slice(), velocity: *velocity, expression: expression.as_ref(), variation: variation.as_ref() }))
            }
            _ => None,
        })
        .collect();
    if let Some(&(spec, _)) = sampled.first() {
        let notes: Vec<_> = sampled.into_iter().map(|(_, n)| n).collect();
        crate::instruments::sampler::render(spec, &notes, left, right, sr)?;
    }
    // SFZ instruments (sfz.rs): each articulation's notes together, so legato hands over between them.
    let mut files: Vec<&crate::instruments::sfz::SfzSpec> = vec![];
    for v in all { if let V::Note { sfz: Some(s), .. } = v { if !files.iter().any(|f| f.plays_as(s)) { files.push(s); } } }
    for spec in files {
        let notes: Vec<_> = all.iter().filter_map(|v| match v {
            V::Note { sfz: Some(s), freqs, start_idx, duration, velocity, pan, expression, cut, .. } if s.plays_as(spec) => Some(crate::instruments::sfz::Note { start: *start_idx, len: (duration * sr).round() as usize, freqs: freqs.as_slice(), velocity: *velocity, pan: *pan, expression: expression.as_ref(), cut: cut.map(|c| (c.max(0.0) * sr).round() as usize) }),
            _ => None,
        }).collect();
        crate::instruments::sfz::render(spec, &notes, left, right, sr, span)?;
    }
    // A plugin instrument: one instance for the clip's notes (its own polyphony and releases), rendered once and kept.
    let plugged: Vec<_> = voices.iter().filter_map(|v| match v { V::Note { plugin: Some(p), freqs, start_idx, duration, velocity, .. } => Some((p, freqs, *start_idx, *duration, *velocity)), _ => None }).collect();
    if let Some((spec, ..)) = plugged.first() {
        let notes: Vec<crate::plugins::clap::Note> = plugged
            .iter()
            .flat_map(|(_, freqs, start, dur, vel)| freqs.iter().map(move |f| crate::plugins::clap::Note { start: *start, end: start + (dur * sr).round() as usize, key: (69.0 + 12.0 * (f / 440.0).log2()).round().clamp(0.0, 127.0) as u16, velocity: *vel }))
            .collect();
        crate::plugins::clap::render::rendered(spec, &notes, left, right, sr, false)?;
    }
    // Procedural instruments (model/): each one's notes as one part (a string is cut by the next note on it, a bowed line slurs).
    let modelled = |v: &V| matches!(v, V::Note { instrument, synth: None, sampler: None, sfz: None, plugin: None, .. } if crate::instruments::model::is_model(instrument));
    let mut names: Vec<&str> = vec![];
    for v in voices.iter().filter(|v| modelled(v)) { if let V::Note { instrument, .. } = v { if !names.contains(&instrument.as_str()) { names.push(instrument); } } }
    for name in names {
        let notes: Vec<crate::instruments::model::Note> = voices.iter().filter(|v| modelled(v)).filter_map(|v| match v {
            V::Note { instrument, freqs, start_idx, duration, velocity, pan, expression, touch, .. } if instrument == name => Some(freqs.iter().map(move |&freq| crate::instruments::model::Note { start: *start_idx, len: (duration * sr).round() as usize, freq, velocity: *velocity, pan: *pan, expression: expression.as_ref(), hardness: touch.and_then(|t| t.hardness), position: touch.and_then(|t| t.position), damping: touch.and_then(|t| t.damping) })),
            _ => None,
        }).flatten().collect();
        crate::instruments::model::render(name, &notes, left, right, sr)?;
    }
    // Synth and drum voices: each part computed on its own core (a part depends on nothing but itself),
    // then added into the clip one after another in schedule order, so the sum is the same every run.
    let mut parts = Vec::new();
    for v in voices.iter().filter(|v| !matches!(v, V::Note { sampler: Some(_), .. } | V::Note { plugin: Some(_), .. } | V::Note { sfz: Some(_), .. }) && !modelled(v)) {
        Voice::from_schedule(v, left.len(), sr, &mut parts)?;
    }
    // In batches, so a long score never holds every part's samples at once.
    let cores = std::thread::available_parallelism().map(|n| n.get()).unwrap_or(4);
    let mut parts = parts.into_iter().peekable();
    while parts.peek().is_some() {
        let batch: Vec<Voice> = parts.by_ref().take(cores * 4).collect();
        let sounds = crate::mix::par::map(batch, |mut p| (p.start, (0..p.len).map(|i| p.next(i)).collect::<Vec<(f64, f64)>>()));
        for (start, s) in sounds {
            for (i, (l, r)) in s.into_iter().enumerate() {
                let k = start + i;
                left[k] = (left[k] as f64 + l) as f32;
                right[k] = (right[k] as f64 + r) as f32;
            }
        }
    }
    Ok(())
}

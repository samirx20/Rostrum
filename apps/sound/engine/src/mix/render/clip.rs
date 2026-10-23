//! Each clip into its own buffer, on all cores: content, speed, repairs, effects, reverse, glitch, filter
//! sweep, tone, fades and gain, reverb (a bed track's clip: as it is, at its speed, with its fades).

use crate::bed::Layout;
use crate::fx;
use crate::fx::dsp;
use crate::fx::reverb;
use crate::instruments::voices;
use crate::mix::effects;
use crate::mix::schedule::{Clip, Content, Schedule};
use crate::sfx;
use crate::sfx::speech;

use super::prof;

/// A clip of a Freeverb soundtrack (its reverb space is a Freeverb one): its reversed swell is Freeverb too.
fn freeverb_clip(c: &Clip) -> bool {
    c.reverb_space.as_deref().is_some_and(|s| s.starts_with("freeverb."))
}

/// Effect presets Rostrum used to make and no longer does (PURPOSE.md: no cheap effects); an old song that has one is refused naming it.
const RETIRED_PRESETS: &[&str] = &["whoosh", "swoosh", "swish", "swipe", "sweep", "transition", "zap", "laser", "portal", "warp", "glitch"];

fn render_clip(c: &Clip, sr: f64) -> Result<(Vec<f32>, Vec<f32>), String> {
    let (mut l, mut r) = (vec![0.0f32; c.samples], vec![0.0f32; c.samples]);
    let mut stretched = false;
    match &c.content {
        Content::Score { voices } => voices::score::render_score(voices, &mut l, &mut r, sr)?,
        Content::Sfx { preset, .. } if RETIRED_PRESETS.contains(&preset.as_str()) => return Err(format!("this song has a {preset}, which Rostrum no longer makes; remove it or replace it")),
        Content::Sfx { preset, material, duration, volume, pitch, pan_from, pan_to } => {
            sfx::render_sfx(&sfx::Sfx { preset, material: material.as_ref(), duration: *duration, volume: *volume, pitch: *pitch, pan_from: *pan_from, pan_to: *pan_to }, &mut l, &mut r, sr)
        }
        Content::Sample { pcm, duration, volume, pitch, pan_from, pan_to } => sfx::render_sample(pcm, *duration, *volume, *pitch, *pan_from, *pan_to, &mut l, &mut r, sr)?,
        Content::Media { pcm } => {
            if pcm.channels > 2 {
                return Err(format!("{}: {} channels in a stereo clip (a surround file plays on a bed track)", pcm.file, pcm.channels));
            }
            let src = pcm.read()?;
            let (sl, sr_): (Vec<f32>, Vec<f32>) = if pcm.channels == 2 { (src.iter().step_by(2).copied().collect(), src.iter().skip(1).step_by(2).copied().collect()) } else { (src.clone(), src) };
            match &c.rate {
                Some(rate) => crate::stretch::speed::time_stretch(&mut l, &mut r, sr, rate, Some((&sl, &sr_))),
                None => {
                    let n = l.len().min(sl.len());
                    l[..n].copy_from_slice(&sl[..n]);
                    r[..n].copy_from_slice(&sr_[..n]);
                }
            }
            stretched = true;
        }
        Content::Speech { pcm, pitch_ratio } => speech::render_speech(pcm, *pitch_ratio, &mut l, &mut r, sr)?,
        Content::VoiceSketch { tokens, base_f0 } => speech::render_voice_sketch(tokens, *base_f0, &mut l, &mut r, sr),
        Content::Waveform { peaks } => speech::render_waveform(peaks, c.duration, &mut l, &mut r, sr),
        Content::Silence => {}
    }
    if let (false, Some(rate)) = (stretched, &c.rate) {
        crate::stretch::speed::time_stretch(&mut l, &mut r, sr, rate, None);
    }
    // The recording's repairs (clip time): spectral regions, its own effects, the tone match.
    crate::dialogue::dereverb::repair(&mut l, &mut r, sr, &c.repair);
    fx::chain::stereo(&c.effects, &mut l, &mut r, sr)?;
    if let Some(m) = &c.match_eq {
        crate::fx::matcheq::apply(&mut l, &mut r, &m.curve, &m.phase, sr);
    }
    if let Some(wet) = c.reverse {
        // Reverb before reversing, so the tail swells up into the hit.
        let swell = if freeverb_clip(c) { "freeverb.cathedral" } else { "cathedral" };
        reverb::reverb(&mut l, &mut r, swell, wet, sr);
        l.reverse();
        r.reverse();
    }
    if let Some(g) = &c.glitch {
        effects::glitch(&mut l, &mut r, sr, g);
    }
    if let Some(s) = &c.filter_sweep {
        effects::filter_sweep(&mut l, &mut r, sr, s);
    }
    dsp::tone(&mut l, &mut r, &c.tone, sr);
    // Fades (their shapes), gain and pan, the clip's own lanes (clipshape.rs; none: dsp::fade_gain).
    crate::mix::clipshape::fade_gain(c, &mut l, &mut r, sr);
    if c.reverse.is_none() {
        reverb::reverb(&mut l, &mut r, c.reverb_space.as_deref().unwrap_or("hall"), c.reverb, sr);
    }
    crate::mix::clipshape::invert(c, &mut [&mut l, &mut r]);
    Ok((l, r))
}

/// A bed track's clip: a file already in the layout, channel for channel, at its speed (one time map
/// over every channel: the image holds), turned round when reversed, with its fades and gain.
fn render_bed_clip(c: &Clip, layout: Layout, sr: f64) -> Result<Vec<Vec<f32>>, String> {
    let Content::Media { pcm } = &c.content else { return Err(format!("a bed clip plays a {} file", layout.name())) };
    if pcm.channels != layout.channels() || !c.effects.is_empty() || c.reverse.is_some_and(|wet| wet > 0.0) {
        return Err(format!("{}: a bed clip is a {}-channel file played as it is (speed and reverse only: no clip effects, no reverse swell); this one has {} channels", pcm.file, layout.channels(), pcm.channels));
    }
    let src = pcm.read()?;
    let n = pcm.channels;
    let mut chs: Vec<Vec<f32>> = (0..n).map(|ch| (0..c.samples).map(|i| src.get(i * n + ch).copied().unwrap_or(0.0)).collect()).collect();
    if let Some(rate) = &c.rate {
        // A bed is music: the stretcher (PSOLA is for one voice).
        let whole: Vec<Vec<f32>> = (0..n).map(|ch| src.iter().skip(ch).step_by(n).copied().collect()).collect();
        let refs: Vec<&[f32]> = whole.iter().map(|v| v.as_slice()).collect();
        let music = crate::mix::schedule::Rate { content: Some("music".into()), ..rate.clone() };
        crate::stretch::speed::time_stretch_n(&mut chs.iter_mut().map(|v| v.as_mut_slice()).collect::<Vec<_>>(), sr, &music, Some(&refs));
    }
    if c.reverse.is_some() {
        chs.iter_mut().for_each(|v| v.reverse());
    }
    let g = dsp::FadeGain::new(c.samples, sr, c.fade_in, c.fade_out, c.volume, 0.0);
    let shape = crate::mix::clipshape::Shape::of(c, c.samples, sr);
    for v in chs.iter_mut() {
        v.iter_mut().enumerate().for_each(|(i, s)| *s = (*s as f64 * crate::mix::clipshape::bed_env(c, &g, &shape, i, sr) * c.volume) as f32);
    }
    crate::mix::clipshape::invert(c, &mut crate::bed::slices(&mut chs));
    Ok(chs)
}

/// Every clip of track `t`, rendered on all cores; results in the track's order.
pub(super) fn render_track_clips(s: &Schedule, t: usize) -> Result<Vec<Vec<Vec<f32>>>, String> {
    let sr = s.sample_rate as f64;
    let track = &s.tracks[t];
    crate::mix::par::map((0..track.clips.len()).collect(), |c| {
        let clip = &track.clips[c];
        let t0 = std::time::Instant::now();
        let r = if track.bed { render_bed_clip(clip, s.layout, sr) } else { render_clip(clip, sr).map(|(l, r)| vec![l, r]) };
        prof(&format!("clip {} #{c}", track.name), t0);
        r
    })
    .into_iter()
    .collect()
}

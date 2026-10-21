//! A CLAP plugin rendered offline in fixed 256-sample blocks, notes and parameters as sample-timed
//! events; and each render stored once (plugins may be random) so every later render reads it back.

use std::ffi::CString;

use clack_host::events::event_types::{MidiEvent, NoteOffEvent, NoteOnEvent, ParamValueEvent};
use clack_host::events::Match;
use clack_host::prelude::*;

use super::{cc_events, host_info, load_state, Host, Note, PluginSpec, Shared};

const BLOCK: u32 = 256;
/// A plugin's render, stored once (rule 9): plugins may be random (Surge starts its oscillators at
/// random phases), so a clip renders once and every later render reads it back — preview, export
/// and the next render alike. Keyed by everything that decides it: the plugin file (size, time), its
/// id, state, parameters and their envelopes, where it starts in the song, the notes, the input (an
/// effect), the length and the rate.
pub fn rendered(spec: &PluginSpec, notes: &[Note], left: &mut [f32], right: &mut [f32], sr: f64, effect: bool) -> Result<(), String> {
    use std::hash::{Hash, Hasher};
    let mut h = std::collections::hash_map::DefaultHasher::new();
    let meta = std::fs::metadata(&spec.path).map_err(|e| format!("plugin {}: {e}", spec.path))?;
    (&spec.format, &spec.path, meta.len(), meta.modified().ok(), &spec.id, effect, left.len(), sr.to_bits()).hash(&mut h);
    (&spec.state, spec.at.to_bits()).hash(&mut h);
    for (id, v) in &spec.params {
        id.hash(&mut h);
        match v {
            crate::mix::schedule::Param::Value(x) => x.to_bits().hash(&mut h),
            crate::mix::schedule::Param::Envelope(pts) => pts.iter().for_each(|[t, x]| (t.to_bits(), x.to_bits()).hash(&mut h)),
        }
    }
    for n in notes {
        (n.start, n.end, n.key, n.velocity.to_bits()).hash(&mut h);
    }
    for lane in &spec.cc {
        lane.cc.hash(&mut h);
        lane.points.iter().for_each(|[t, x]| (t.to_bits(), x.to_bits()).hash(&mut h));
    }
    if effect {
        for s in left.iter().chain(right.iter()) {
            s.to_bits().hash(&mut h);
        }
    }
    let cache = crate::mix::cache::dir("plugin");
    let name = format!("{:016x}.f32", h.finish());
    let n = left.len().min(right.len());
    let (mut ol, mut or) = (vec![0f32; n], vec![0f32; n]);
    match cache.as_deref().and_then(|d| crate::mix::cache::read(d, &name)) {
        Some(bytes) if bytes.len() == n * 8 => {
            for i in 0..n {
                ol[i] = f32::from_le_bytes(bytes[8 * i..8 * i + 4].try_into().unwrap());
                or[i] = f32::from_le_bytes(bytes[8 * i + 4..8 * i + 8].try_into().unwrap());
            }
        }
        _ => {
            if effect {
                ol.copy_from_slice(&left[..n]);
                or.copy_from_slice(&right[..n]);
            }
            match spec.format.as_str() {
                "clap" => render(spec, notes, &mut ol, &mut or, sr, effect)?,
                #[cfg(windows)]
                "vst3" => crate::plugins::vst3::render::render(spec, notes, &mut ol, &mut or, sr, effect)?,
                other => return Err(format!("plugin {}: this engine hosts CLAP and VST3 plugins; got format \"{other}\"", spec.path)),
            }
            if let Some(dir) = &cache {
                let bytes: Vec<u8> = (0..n).flat_map(|i| [ol[i].to_le_bytes(), or[i].to_le_bytes()].concat()).collect();
                crate::mix::cache::write(dir, &name, &bytes);
            }
        }
    }
    for i in 0..n {
        if effect {
            left[i] = ol[i];
            right[i] = or[i];
        } else {
            left[i] += ol[i];
            right[i] += or[i];
        }
    }
    Ok(())
}

/// Runs the plugin over `left` / `right` in place (an effect reads them as its input; an instrument adds its output).
pub fn render(spec: &PluginSpec, notes: &[Note], left: &mut [f32], right: &mut [f32], sr: f64, effect: bool) -> Result<(), String> {
    let who = || format!("plugin {} ({})", spec.id, spec.path);
    let entry = unsafe { PluginEntry::load(&spec.path) }.map_err(|e| format!("{}: cannot load: {e:?}", who()))?;
    let id = CString::new(spec.id.clone()).map_err(|_| format!("{}: bad id", who()))?;
    let mut instance = PluginInstance::<Host>::new(|_| Shared, |_| (), &entry, &id, &host_info()?).map_err(|e| format!("{}: {e:?}", who()))?;
    if let Some(state) = &spec.state {
        load_state(&mut instance.plugin_handle(), state).map_err(|e| format!("{}: {e}", who()))?;
    }
    let config = PluginAudioConfiguration { sample_rate: sr, min_frames_count: 1, max_frames_count: BLOCK };
    let processor = instance.activate(|_, _| (), config).map_err(|e| format!("{}: cannot activate: {e:?}", who()))?;
    let mut processor = processor.start_processing().map_err(|e| format!("{}: cannot start: {e:?}", who()))?;

    let total = left.len().min(right.len());
    // Every event of the render in time order: parameters at 0, then notes (offs before ons at the same sample).
    let mut timed: Vec<(usize, u8, u16, f64)> = notes.iter().flat_map(|n| [(n.end, 0u8, n.key, 0.0), (n.start, 1u8, n.key, n.velocity)]).collect();
    timed.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
    let mut next = 0;
    let (mut in_l, mut in_r, mut out_l, mut out_r) = (vec![0f32; BLOCK as usize], vec![0f32; BLOCK as usize], vec![0f32; BLOCK as usize], vec![0f32; BLOCK as usize]);
    let mut input_ports = AudioPorts::with_capacity(2, 1);
    let mut output_ports = AudioPorts::with_capacity(2, 1);
    let mut events = EventBuffer::new();
    let mut out_events = EventBuffer::new();
    let mut automation = crate::plugins::params::Automation::new(&spec.params, spec.at, sr);
    let mut cc_last = vec![];
    let mut pos = 0;
    while pos < total {
        let n = (total - pos).min(BLOCK as usize);
        events.clear();
        // Parameter changes and notes in time order within the block.
        let mut changes = automation.block(pos, n).into_iter().peekable();
        // Controller lanes as MIDI (a sustain pedal or bend at a note's sample goes before the note).
        let mut midi = cc_events(&spec.cc, &mut cc_last, spec.at, sr, pos, n).into_iter().peekable();
        let mut push_changes = |events: &mut EventBuffer, until: u32| {
            while let Some(&(o, pid, v)) = changes.peek().filter(|c| c.0 <= until) {
                if let Some(cid) = ClapId::from_raw(pid) {
                    events.push(&ParamValueEvent::new(o, cid, Pckn::match_all(), v));
                }
                changes.next();
            }
            while let Some(&(o, bytes)) = midi.peek().filter(|m| m.0 <= until) {
                events.push(&MidiEvent::new(o, 0, bytes));
                midi.next();
            }
        };
        while next < timed.len() && timed[next].0 < pos + n {
            let (at, on, key, vel) = timed[next];
            let t = (at.saturating_sub(pos)) as u32;
            let pckn = Pckn::new(0u16, 0u16, key, Match::All);
            push_changes(&mut events, t);
            if on == 1 {
                events.push(&NoteOnEvent::new(t, pckn, vel));
            } else {
                events.push(&NoteOffEvent::new(t, pckn, 0.0));
            }
            next += 1;
        }
        push_changes(&mut events, u32::MAX);
        in_l[..n].copy_from_slice(&left[pos..pos + n]);
        in_r[..n].copy_from_slice(&right[pos..pos + n]);
        out_l[..n].fill(0.0);
        out_r[..n].fill(0.0);
        out_events.clear();
        let input = input_ports.with_input_buffers([AudioPortBuffer { latency: 0, channels: AudioPortBufferType::f32_input_only([InputChannel::variable(&mut in_l[..n]), InputChannel::variable(&mut in_r[..n])].into_iter()) }]);
        let mut output = output_ports.with_output_buffers([AudioPortBuffer { latency: 0, channels: AudioPortBufferType::f32_output_only([&mut out_l[..n], &mut out_r[..n]].into_iter()) }]);
        processor
            .process(&input, &mut output, &InputEvents::from_buffer(&events), &mut OutputEvents::from_buffer(&mut out_events), Some(pos as u64), None)
            .map_err(|e| format!("{}: process failed: {e:?}", who()))?;
        for i in 0..n {
            if effect {
                left[pos + i] = out_l[i];
                right[pos + i] = out_r[i];
            } else {
                left[pos + i] += out_l[i];
                right[pos + i] += out_r[i];
            }
        }
        pos += n;
    }
    let stopped = processor.stop_processing();
    instance.deactivate(stopped);
    Ok(())
}

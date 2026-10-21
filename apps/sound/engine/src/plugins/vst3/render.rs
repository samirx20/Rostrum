//! A VST3 plugin rendered offline in fixed 256-sample blocks, notes and parameter changes timed to the sample.

use std::cell::RefCell;
use std::path::Path;

use vst3::Steinberg::Vst::*;
use vst3::Steinberg::*;
use vst3::ComWrapper;

use super::com::{Changes, Events};
use super::plugin::Plugin;
use super::{cid_of, factory};

const BLOCK: i32 = 256;

/// Runs the plugin over `left` / `right` in place (an effect reads them as its input; an instrument writes its output there).
pub fn render(spec: &crate::plugins::clap::PluginSpec, notes: &[crate::plugins::clap::Note], left: &mut [f32], right: &mut [f32], sr: f64, effect: bool) -> Result<(), String> {
    let who = format!("plugin {} ({})", spec.id, spec.path);
    let f = factory(Path::new(&spec.path))?;
    let plugin = Plugin::new(&f, &cid_of(&spec.id), &who)?;
    if let Some(state) = &spec.state {
        plugin.set_state(&crate::plugins::params::unbase64(state)?).map_err(|e| format!("{who}: {e}"))?;
    }
    let c = &plugin.component;
    let processor = c.cast::<IAudioProcessor>().ok_or(format!("{who}: no audio processor"))?;
    unsafe {
        let mut stereo: SpeakerArrangement = SpeakerArr::kStereo;
        let mut out_arr = [stereo];
        let ins = if effect { 1 } else { 0 };
        processor.setBusArrangements(&mut stereo, ins, out_arr.as_mut_ptr(), 1);
        if effect {
            c.activateBus(MediaTypes_::kAudio as MediaType, BusDirections_::kInput as BusDirection, 0, 1);
        }
        c.activateBus(MediaTypes_::kAudio as MediaType, BusDirections_::kOutput as BusDirection, 0, 1);
        if !effect && c.getBusCount(MediaTypes_::kEvent as MediaType, BusDirections_::kInput as BusDirection) > 0 {
            c.activateBus(MediaTypes_::kEvent as MediaType, BusDirections_::kInput as BusDirection, 0, 1);
        }
        let mut setup = ProcessSetup { processMode: ProcessModes_::kOffline as int32, symbolicSampleSize: SymbolicSampleSizes_::kSample32 as int32, maxSamplesPerBlock: BLOCK, sampleRate: sr };
        if processor.setupProcessing(&mut setup) != kResultOk {
            return Err(format!("{who}: refused 32-bit offline processing at {sr} Hz"));
        }
        if c.setActive(1) != kResultOk {
            return Err(format!("{who}: would not activate"));
        }
        processor.setProcessing(1);

        let total = left.len().min(right.len());
        let mut timed: Vec<(usize, u8, u16, f64)> = notes.iter().flat_map(|n| [(n.end, 0u8, n.key, 0.0), (n.start, 1u8, n.key, n.velocity)]).collect();
        timed.sort_by(|a, b| a.0.cmp(&b.0).then(a.1.cmp(&b.1)));
        let mut next = 0;
        let events = ComWrapper::new(Events(RefCell::new(vec![])));
        let changes = ComWrapper::new(Changes(RefCell::new(vec![])));
        let (mut il, mut ir, mut ol, mut or) = (vec![0f32; BLOCK as usize], vec![0f32; BLOCK as usize], vec![0f32; BLOCK as usize], vec![0f32; BLOCK as usize]);
        let mut pos = 0;
        let mut failed = None;
        let mut automation = crate::plugins::params::Automation::new(&spec.params, spec.at, sr);
        while pos < total {
            let n = (total - pos).min(BLOCK as usize);
            events.0.borrow_mut().clear();
            changes.0.borrow_mut().clear();
            for (o, id, v) in automation.block(pos, n) {
                let mut i = 0;
                let q = changes.addParameterData(&id, &mut i);
                if let Some(q) = vst3::ComRef::from_raw(q) {
                    q.addPoint(o as int32, v, std::ptr::null_mut());
                }
            }
            while next < timed.len() && timed[next].0 < pos + n {
                let (at, on, key, vel) = timed[next];
                let mut e: Event = std::mem::zeroed();
                e.sampleOffset = (at.saturating_sub(pos)) as int32;
                if on == 1 {
                    e.r#type = Event_::EventTypes_::kNoteOnEvent as u16;
                    e.__field0.noteOn = NoteOnEvent { channel: 0, pitch: key as int16, tuning: 0.0, velocity: vel as f32, length: 0, noteId: -1 };
                } else {
                    e.r#type = Event_::EventTypes_::kNoteOffEvent as u16;
                    e.__field0.noteOff = NoteOffEvent { channel: 0, pitch: key as int16, velocity: 0.0, noteId: -1, tuning: 0.0 };
                }
                events.0.borrow_mut().push(e);
                next += 1;
            }
            il[..n].copy_from_slice(&left[pos..pos + n]);
            ir[..n].copy_from_slice(&right[pos..pos + n]);
            ol[..n].fill(0.0);
            or[..n].fill(0.0);
            let mut in_ptrs = [il.as_mut_ptr(), ir.as_mut_ptr()];
            let mut out_ptrs = [ol.as_mut_ptr(), or.as_mut_ptr()];
            let mut input = AudioBusBuffers { numChannels: 2, silenceFlags: 0, __field0: AudioBusBuffers__type0 { channelBuffers32: in_ptrs.as_mut_ptr() } };
            let mut output = AudioBusBuffers { numChannels: 2, silenceFlags: 0, __field0: AudioBusBuffers__type0 { channelBuffers32: out_ptrs.as_mut_ptr() } };
            let mut data = ProcessData {
                processMode: ProcessModes_::kOffline as int32,
                symbolicSampleSize: SymbolicSampleSizes_::kSample32 as int32,
                numSamples: n as int32,
                numInputs: ins,
                numOutputs: 1,
                inputs: if effect { &mut input } else { std::ptr::null_mut() },
                outputs: &mut output,
                inputParameterChanges: changes.as_com_ref::<IParameterChanges>().unwrap().as_ptr(),
                outputParameterChanges: std::ptr::null_mut(),
                inputEvents: events.as_com_ref::<IEventList>().unwrap().as_ptr(),
                outputEvents: std::ptr::null_mut(),
                processContext: std::ptr::null_mut(),
            };
            if processor.process(&mut data) != kResultOk {
                failed = Some(format!("{who}: process failed at sample {pos}"));
                break;
            }
            left[pos..pos + n].copy_from_slice(&ol[..n]);
            right[pos..pos + n].copy_from_slice(&or[..n]);
            pos += n;
        }
        processor.setProcessing(0);
        c.setActive(0);
        if let Some(ctl) = &plugin.controller {
            if c.cast::<IEditController>().is_none() {
                ctl.terminate();
            }
        }
        c.terminate();
        failed.map_or(Ok(()), Err)
    }
}

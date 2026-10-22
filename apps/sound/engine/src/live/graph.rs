//! Live playback through Firewheel: the rendered mix plays from a node in the graph, so what is
//! heard is the exported file sample for sample (preview ≡ export). Live instruments and plugins
//! join this graph later (S3, S4).

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;

use firewheel::channel_config::{ChannelConfig, ChannelCount};
use firewheel::cpal::{CpalConfig, CpalStream};
use firewheel::node::{AudioNode, AudioNodeInfo, AudioNodeProcessor, ConstructProcessorContext, EmptyConfig, NodeError, ProcBuffers, ProcExtra, ProcInfo, ProcessStatus};
use firewheel::{FirewheelConfig, FirewheelContext};

/// A stereo buffer at its sample rate, and how far playback has got.
pub struct Take {
    pub left: Vec<f32>,
    pub right: Vec<f32>,
    pub rate: u32,
    pub pos: AtomicUsize,
}

#[derive(Clone)]
struct PlayerNode(Arc<Take>);
struct PlayerProc(Arc<Take>);

impl AudioNode for PlayerNode {
    type Configuration = EmptyConfig;
    fn info(&self, _: &EmptyConfig) -> Result<AudioNodeInfo, NodeError> {
        Ok(AudioNodeInfo::new().debug_name("rostrum_player").channel_config(ChannelConfig { num_inputs: ChannelCount::ZERO, num_outputs: ChannelCount::STEREO }))
    }
    fn construct_processor(&self, _: &EmptyConfig, cx: ConstructProcessorContext) -> Result<impl AudioNodeProcessor, NodeError> {
        let sr = cx.stream_info.sample_rate.get();
        if sr != self.0.rate {
            return Err(NodeError::from_boxed(format!("the device runs at {sr} Hz, the mix at {} Hz", self.0.rate).into()));
        }
        Ok(PlayerProc(self.0.clone()))
    }
}

impl AudioNodeProcessor for PlayerProc {
    fn process(&mut self, info: &ProcInfo, buffers: ProcBuffers, _: &mut ProcExtra) -> ProcessStatus {
        let take = &self.0;
        let pos = take.pos.load(Ordering::Relaxed);
        let (l, r) = buffers.outputs.split_at_mut(1);
        for i in 0..info.frames {
            l[0][i] = take.left.get(pos + i).copied().unwrap_or(0.0);
            r[0][i] = take.right.get(pos + i).copied().unwrap_or(0.0);
        }
        take.pos.store(pos + info.frames, Ordering::Relaxed);
        ProcessStatus::OutputsModified
    }
}

/// Plays the take on the default output device to its end.
pub fn play(take: Take) -> Result<(), String> {
    let take = Arc::new(take);
    let mut cx = FirewheelContext::new(FirewheelConfig::default());
    let id = cx.add_node(PlayerNode(take.clone()), None).map_err(|e| format!("{e:?}"))?;
    let out = cx.graph_out_node_id();
    cx.connect(id, out, &[(0, 0), (1, 1)], false).map_err(|e| format!("{e:?}"))?;
    let mut config = CpalConfig::default();
    config.output.desired_sample_rate = Some(take.rate);
    let stream = CpalStream::new(&mut cx, config).map_err(|e| format!("audio device: {e}"))?;
    while take.pos.load(Ordering::Relaxed) < take.left.len() {
        cx.update().map_err(|e| format!("{e:?}"))?;
        if !stream.output_stream_ok() {
            return Err("the audio device stopped".into());
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    std::thread::sleep(Duration::from_millis(100));
    Ok(())
}

/// `rostrum-sound play <schedule.json>`: the schedule rendered, then played to its end.
pub fn play_schedule(path: &str) -> Result<(), String> {
    let s = crate::mix::load(path)?;
    let mix = crate::mix::render::render(&s)?;
    let [l, r]: [Vec<f32>; 2] = crate::mix::render::stats::as_stereo(&mix.channels()?).try_into().map_err(|_| "a fold-down is two channels")?;
    play(Take { left: l, right: r, rate: s.sample_rate, pos: Default::default() })
}

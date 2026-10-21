//! How the live output plays a surround mix (play.rs, the transport): its bed on a device that has
//! the bed's speakers (each channel on its own speaker, by the WAVE channel masks), binaural on
//! headphones (WASAPI's endpoint form factor: headphones or a headset, Bluetooth included), else the
//! ITU fold-down — chosen, or asked for with `--monitor surround | binaural | stereo`, and always said.
//! The fold-down and binaural are the delivery's own (fold.rs fold_bed: held to the mastering spec),
//! so what is heard is what `export --layout` writes. A stereo mix plays as it is. A surround monitor
//! on a device that cannot place every channel is an error naming what the device offers, never a
//! silent fold-down (AGENTS.md rule 6).

use crate::bed::Layout;
use crate::live::frames::Frames;
use crate::fx::master::MasterSpec;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Monitor {
    Surround,
    Binaural,
    Stereo,
}

impl Monitor {
    /// "auto" (or nothing): None, chosen from the device.
    pub fn parse(s: &str) -> Result<Option<Monitor>, String> {
        match s {
            "auto" => Ok(None),
            "surround" => Ok(Some(Monitor::Surround)),
            "binaural" => Ok(Some(Monitor::Binaural)),
            "stereo" => Ok(Some(Monitor::Stereo)),
            _ => Err(format!("--monitor is auto, surround, binaural or stereo; got \"{s}\"")),
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Monitor::Surround => "surround",
            Monitor::Binaural => "binaural",
            Monitor::Stereo => "stereo",
        }
    }
}

/// The output as WASAPI describes it: its channels, their speakers (the mix format's channel mask;
/// 0 when it gives none) and the endpoint's form factor (EndpointFormFactor: 1 speakers, 3 headphones,
/// 5 headset …).
#[derive(Clone, Debug, Default)]
pub struct Device {
    pub rate: u32,
    pub channels: usize,
    pub mask: u32,
    pub form_factor: u32,
    pub name: String,
}

impl Device {
    pub fn headphones(&self) -> bool {
        matches!(self.form_factor, 3 | 5)
    }
}

const SPEAKERS: [(u32, &str); 11] = [(0x1, "FL"), (0x2, "FR"), (0x4, "FC"), (0x8, "LFE"), (0x10, "BL"), (0x20, "BR"), (0x40, "FLC"), (0x80, "FRC"), (0x100, "BC"), (0x200, "SL"), (0x400, "SR")];

/// A mask's speakers by name ("FL FR FC LFE BL BR").
pub fn speakers(mask: u32) -> String {
    let names: Vec<&str> = SPEAKERS.iter().filter(|(b, _)| mask & b != 0).map(|(_, n)| *n).collect();
    if names.is_empty() { "no speaker positions".into() } else { names.join(" ") }
}

/// For each device channel, the source channel it plays (None: silent). A stereo source plays on the
/// device's first two channels, as it always has. A wider source is placed speaker by speaker: each
/// source channel's mask bit on the device channel with that bit (the device's channels are its mask's
/// bits in order), back surrounds on side ones (or the reverse) when the device has only those and
/// nothing else wants them. A channel with nowhere to go is an error.
pub fn channel_map(src_channels: usize, src_mask: u32, dev_channels: usize, dev_mask: u32) -> Result<Vec<Option<usize>>, String> {
    let mut map = vec![None; dev_channels];
    if src_channels <= 2 {
        (0..src_channels.min(dev_channels)).for_each(|c| map[c] = Some(c));
        return Ok(map);
    }
    let bits = |m: u32| (0..32).map(|i| 1u32 << i).filter(move |b| m & b != 0).collect::<Vec<u32>>();
    let src_bits = bits(src_mask);
    if src_bits.len() != src_channels {
        return Err(format!("a {src_channels}-channel mix whose mask {src_mask:#x} names {} speakers", src_bits.len()));
    }
    let dev_bits = bits(dev_mask);
    if dev_bits.len() != dev_channels || dev_mask == 0 {
        return Err(format!("the device offers {dev_channels} channels with {} ({dev_mask:#x}): its speakers are not known, so a {src_channels}-channel bed cannot be placed", speakers(dev_mask)));
    }
    let alt = |b: u32| match b {
        0x10 => 0x200,
        0x200 => 0x10,
        0x20 => 0x400,
        0x400 => 0x20,
        _ => 0,
    };
    for (s, &b) in src_bits.iter().enumerate() {
        let want = if dev_mask & b != 0 { b } else if alt(b) != 0 && dev_mask & alt(b) != 0 && src_mask & alt(b) == 0 { alt(b) } else { 0 };
        let d = dev_bits.iter().position(|&x| x == want).ok_or_else(|| {
            format!("the device offers {dev_channels} channels ({}) and has no {} for this {src_channels}-channel bed ({})", speakers(dev_mask), speakers(b), speakers(src_mask))
        })?;
        map[d] = Some(s);
    }
    Ok(map)
}

/// Device channel `ch` of frame `i` from a block of `src_channels`-channel frames, by `map`: the one
/// placing rule the stream (wasapi/open.rs write) and the tests' offline device use.
pub fn placed(block: &[f32], i: usize, src_channels: usize, map: &[Option<usize>], ch: usize) -> f32 {
    map.get(ch).copied().flatten().map_or(0.0, |s| block[i * src_channels + s].clamp(-1.0, 1.0))
}

/// How to monitor a `layout` mix on `dev` (asked, or chosen), and why.
pub fn choose(asked: Option<Monitor>, layout: Layout, dev: &Device) -> Result<(Monitor, String), String> {
    if layout == Layout::Stereo {
        return Ok((Monitor::Stereo, "the mix is stereo".into()));
    }
    let placed = channel_map(layout.channels(), layout.mask(), dev.channels, dev.mask);
    match (asked, placed) {
        (Some(Monitor::Surround), Err(e)) => Err(format!("--monitor surround on \"{}\": {e} (--monitor binaural or stereo plays it there)", dev.name)),
        (Some(m), _) => Ok((m, "asked for (--monitor)".into())),
        (None, Ok(_)) => Ok((Monitor::Surround, format!("the device has the {} bed's speakers ({})", layout.name(), speakers(dev.mask)))),
        (None, Err(_)) if dev.headphones() => Ok((Monitor::Binaural, "the output is headphones".into())),
        (None, Err(_)) => Ok((Monitor::Stereo, format!("the ITU fold-down: the device offers {} channels ({})", dev.channels, speakers(dev.mask)))),
    }
}

/// The mix as the monitor plays it: the bed as it is, or the delivery's fold-down / binaural render.
pub fn prepare(chs: &[Vec<f32>], layout: Layout, monitor: Monitor, master: Option<MasterSpec>, sr: f64) -> Result<Frames, String> {
    match (layout, monitor) {
        (Layout::Stereo, _) => Ok(Frames::from_channels(chs, 0x3)),
        (_, Monitor::Surround) => Ok(Frames::from_channels(chs, layout.mask())),
        (_, m) => Ok(Frames::from_channels(&crate::bed::fold::fold_bed(chs, layout, if m == Monitor::Binaural { "binaural" } else { "stereo" }, master, sr, true)?.channels, 0x3)),
    }
}

#[cfg(test)]
#[path = "monitor_tests.rs"]
mod tests;

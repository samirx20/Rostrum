//! The job TypeScript hands the engine (src/engine/sound/schedule/index.ts): every clip's content
//! (voices, a synthesized effect, decoded audio as a PCM file), every gain and effect setting with
//! its defaults resolved. The engine decides nothing about the music.

mod content;
mod effect;

pub use content::*;
pub use effect::*;

use serde::Deserialize;

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Schedule {
    pub version: u32,
    pub sample_rate: u32,
    pub total_samples: usize,
    /// Rendered past the end and wrapped onto the start (a looping soundtrack), else 0.
    pub tail_samples: usize,
    pub fade_in_samples: usize,
    pub fade_out_samples: usize,
    pub master_volume: f64,
    /// The master bus' reverb space ("dry": none).
    pub master_reverb: String,
    /// The space tracks' reverb sends use.
    pub track_reverb_space: String,
    pub time_warps: Vec<TimeWarp>,
    /// Master-bus inserts, after the master reverb.
    #[serde(default)]
    pub effects: Vec<Effect>,
    /// The mastering stage (glue, loudness target, true-peak limiter), after the fader and fades.
    #[serde(default)]
    pub master: Option<crate::fx::master::MasterSpec>,
    /// The last stage, the soft safety clip above -1 dBFS (bus.rs safety_clip): on unless a soundtrack turns it off
    /// (`safetyClip: false`, schedule 8): the master then writes what the mix holds, samples past full scale included.
    #[serde(default = "safety_clip_on")]
    pub safety_clip: bool,
    /// The mix bus' channel layout (bed/; stereo when absent: every schedule before 7).
    #[serde(default)]
    pub layout: crate::bed::Layout,
    pub tracks: Vec<Track>,
    /// Buses (buses.rs; none before 8): tracks route into them and send to them.
    #[serde(default)]
    pub buses: Vec<crate::mix::buses::Bus>,
    /// A bus stem: what the master hears (buses.rs).
    #[serde(default)]
    pub tap: Option<crate::mix::buses::Tap>,
    /// The master fader over time (absent: masterVolume).
    #[serde(default)]
    pub master_automation: Option<Vec<[f64; 2]>>,
    /// Each track's render-cache key (trackcache.rs), made from the raw job when it is parsed.
    #[serde(skip)]
    pub track_keys: Vec<String>,
}

fn safety_clip_on() -> bool {
    true
}

/// The fader over time.
#[derive(Deserialize, Clone, Debug, Default)]
pub struct Automation {
    pub volume: Option<Vec<[f64; 2]>>,
    pub pan: Option<Vec<[f64; 2]>>,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Track {
    pub name: String,
    pub tone: String,
    pub volume: f64,
    pub pan: f64,
    pub reverb: f64,
    /// Heard in the mix (false: only a trigger for other tracks' ducks, a muted "ghost" kick).
    #[serde(default = "yes")]
    pub mix: bool,
    /// Dips under other tracks, applied in order (their gains multiply).
    #[serde(default)]
    pub ducks: Vec<Duck>,
    /// Inserts after the track's tone, before its fader.
    #[serde(default)]
    pub effects: Vec<Effect>,
    #[serde(default)]
    pub automation: Automation,
    /// A group bus this track feeds instead of the master (a layered instrument's layers feed their
    /// track, so its effects, fader, reverb send and ducks run once on the summed layers).
    #[serde(default)]
    pub into: Option<usize>,
    /// Where the track sits in a surround bed, or in stereo as an object (panner.rs); None: the stereo
    /// pan law into L / R.
    #[serde(default)]
    pub surround: Option<crate::bed::panner::Surround>,
    /// Its clips are already in the bed's layout (a surround soundtrack placed in a Video Editor mix):
    /// summed channel for channel, no panner.
    #[serde(default)]
    pub bed: bool,
    /// The bus it feeds (an index in `buses`); None: the master.
    #[serde(default)]
    pub output: Option<usize>,
    /// Copies of it into buses (buses.rs).
    #[serde(default)]
    pub sends: Vec<crate::mix::buses::Send>,
    /// Polarity flipped at the strip's input.
    #[serde(default)]
    pub invert: bool,
    pub clips: Vec<Clip>,
}

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Duck {
    /// The tracks (indices in the schedule) whose level triggers it.
    pub from: Vec<usize>,
    /// The gain lost under a full trigger (0.78 ≈ −13 dB).
    pub depth: f64,
    /// Seconds: how fast it dips and recovers, and how far ahead of the trigger it starts.
    pub attack: f64,
    pub release: f64,
    pub lookahead: f64,
    /// Seconds the dip holds after the trigger falls before it releases (so music does not swell
    /// back in every short pause between a voice's phrases).
    #[serde(default)]
    pub hold: f64,
    /// Under a voice: the bass is held and the music swells back (else the whole signal pumps).
    pub voice: bool,
    /// Report where it dipped (authored ducking; ambience ducks quietly).
    pub report: bool,
}

fn yes() -> bool {
    true
}

#[derive(Deserialize, Clone, Debug)]
#[serde(rename_all = "camelCase")]
pub struct Clip {
    pub start_sample: usize,
    /// The clip's buffer: its duration plus its release tail.
    pub samples: usize,
    pub duration: f64,
    pub content: Content,
    /// Speed: the self-stretch of a synthesized clip, or how media is read (rate, ramp, pitch kept).
    pub rate: Option<Rate>,
    pub reverse: Option<f64>,
    pub glitch: Option<Glitch>,
    pub filter_sweep: Option<FilterSweep>,
    pub tone: String,
    pub fade_in: f64,
    pub fade_out: f64,
    pub volume: f64,
    pub pan: f64,
    pub reverb: f64,
    /// The space of the clip's own reverb ("freeverb.hall" in a Freeverb soundtrack; absent: the comb "hall").
    #[serde(default)]
    pub reverb_space: Option<String>,
    /// Repairs of the recording, in order: spectral repair regions, the clip's own effects, the tone match.
    #[serde(default)]
    pub repair: Vec<Repair>,
    #[serde(default)]
    pub effects: Vec<Effect>,
    #[serde(default)]
    pub match_eq: Option<CurveEq>,
    /// The fades' shapes (clipshape.rs; absent: the equal-power quarter sine).
    #[serde(default)]
    pub fade_in_curve: Option<String>,
    #[serde(default)]
    pub fade_out_curve: Option<String>,
    /// Volume and pan over the clip's own time.
    #[serde(default)]
    pub automation: Automation,
    #[serde(default)]
    pub invert: bool,
}

impl Schedule {
    pub fn parse(json: &str) -> Result<Self, String> {
        let v: serde_json::Value = serde_json::from_str(json).map_err(|e| format!("schedule: {e}"))?;
        let raw_tracks = v.get("tracks").and_then(|t| t.as_array()).cloned().unwrap_or_default();
        let mut s: Schedule = serde_json::from_value(v).map_err(|e| format!("schedule: {e}"))?;
        // 7 added the layout and the panner (absent: stereo, as before); 6 the stretch fields (warp,
        // semitones, formant; absent in 5, read as none), so a front
        // still sending 5 renders as before and an engine older than 6 refuses a 6.
        // 8 added buses, sends, clip and master lanes, fade shapes and invert (absent: as before);
        // 9 the "attenuated" fade shape (an engine before 9 would play it as equalPower).
        if !(5..=9).contains(&s.version) {
            return Err(format!("schedule version {} (this engine reads 5 to 9)", s.version));
        }
        s.track_keys = crate::mix::trackcache::keys(&raw_tracks, s.sample_rate, s.layout.name(), s.total_samples + s.tail_samples, &s.track_reverb_space);
        Ok(s)
    }
}

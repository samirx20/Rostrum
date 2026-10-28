//! Inserts on a live instrument (a layered instrument's layers): the same EQ bands and saturator as
//! the mix (eq.rs, inserts.rs), run block by block with their state kept between blocks. Only what plays the
//! same live as in the mix is accepted — fixed EQ bands and saturation; an automated parameter or
//! any other effect is an error naming it (the layer then plays in the mix, not live).

use crate::fx::eq::{biquad, Coeffs};
use crate::fx::inserts::saturated;
use crate::mix::schedule::{Effect, Param};

enum Stage {
    Eq(Vec<(Coeffs, [[f64; 2]; 2])>),
    Saturate { drive: f64, mix: f64 },
}

pub struct LiveFx(Vec<Stage>);

fn fixed(p: &Param, what: &str) -> Result<f64, String> {
    match p {
        Param::Value(v) => Ok(*v),
        Param::Envelope(_) => Err(format!("an automated {what} plays in the mix, not live")),
    }
}

impl LiveFx {
    pub fn new(effects: &[Effect], sr: f64) -> Result<LiveFx, String> {
        let mut stages = vec![];
        for e in effects {
            stages.push(match e {
                Effect::Eq { bands } => Stage::Eq(
                    bands
                        .iter()
                        .map(|b| Ok((biquad(&b.shape, fixed(&b.freq, "EQ frequency")?, fixed(&b.gain, "EQ gain")?, fixed(&b.q, "EQ q")?, sr), [[0.0; 2]; 2])))
                        .collect::<Result<_, String>>()?,
                ),
                Effect::Saturate { drive, mix } => Stage::Saturate { drive: fixed(drive, "saturation drive")?, mix: fixed(mix, "saturation mix")? },
                other => return Err(format!("{} plays in the mix, not live (live layers take eq and saturate)", name(other))),
            });
        }
        Ok(LiveFx(stages))
    }

    /// Runs the chain over one block in place.
    pub fn process(&mut self, l: &mut [f32], r: &mut [f32]) {
        for stage in self.0.iter_mut() {
            match stage {
                Stage::Eq(bands) => {
                    for (c, z) in bands.iter_mut() {
                        for i in 0..l.len() {
                            l[i] = c.tick(&mut z[0], l[i] as f64) as f32;
                            r[i] = c.tick(&mut z[1], r[i] as f64) as f32;
                        }
                    }
                }
                Stage::Saturate { drive, mix } => {
                    for v in l.iter_mut().chain(r.iter_mut()) {
                        *v = saturated(*v as f64, *drive, *mix) as f32;
                    }
                }
            }
        }
    }
}

fn name(e: &Effect) -> &'static str {
    match e {
        Effect::Eq { .. } => "eq",
        Effect::Compressor { .. } => "a compressor",
        Effect::Delay { .. } => "a delay",
        Effect::Reverb { .. } => "a reverb",
        Effect::Saturate { .. } => "saturate",
        Effect::Tape { .. } => "tape",
        Effect::Limiter { .. } => "a limiter",
        Effect::Width { .. } => "a stereo width",
        Effect::Chorus { .. } => "a chorus",
        Effect::Tremolo { .. } => "a tremolo",
        Effect::Convolution { .. } => "a convolution",
        Effect::Plugin { .. } => "a plugin effect",
        Effect::Deess { .. } | Effect::Gate { .. } | Effect::Leveller { .. } => "a dialogue dynamics effect (deess, gate, leveller)",
        Effect::Dehum { .. } | Effect::Declip { .. } | Effect::Declick { .. } | Effect::Dereverb { .. } => "a dialogue repair (dehum, declip, declick, dereverb)",
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn block_by_block_matches_the_mix_and_refuses_what_differs() {
        let sr = 48000.0;
        let effects: Vec<Effect> = serde_json::from_str(r#"[{"type":"eq","bands":[{"shape":"lowpass","freq":1500,"gain":0,"q":0.707},{"shape":"peak","freq":340,"gain":3,"q":1.4}]},{"type":"saturate","drive":1.5,"mix":0.4}]"#).unwrap();
        let x: Vec<f32> = (0..4800).map(|i| ((i as f64 * 0.07).sin() * 0.6 + (i as f64 * 0.9).sin() * 0.3) as f32).collect();
        let (mut ml, mut mr) = (x.clone(), x.clone());
        crate::fx::chain::stereo(&effects, &mut ml, &mut mr, sr).unwrap();
        let mut live = LiveFx::new(&effects, sr).unwrap();
        let (mut ll, mut lr) = (x.clone(), x);
        for (a, b) in ll.chunks_mut(144).zip(lr.chunks_mut(144)) {
            live.process(a, b);
        }
        let diff = ml.iter().zip(&ll).map(|(a, b)| (a - b).abs()).fold(0f32, f32::max);
        assert!(diff < 1e-6, "{diff}");
        let auto: Vec<Effect> = serde_json::from_str(r#"[{"type":"saturate","drive":[[0,1],[1,4]],"mix":1}]"#).unwrap();
        assert!(LiveFx::new(&auto, sr).err().unwrap().contains("automated"));
        let rev: Vec<Effect> = serde_json::from_str(r#"[{"type":"reverb","space":"hall","mix":0.3}]"#).unwrap();
        assert!(LiveFx::new(&rev, sr).err().unwrap().contains("reverb"));
    }
}

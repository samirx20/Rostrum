//! The learned decoder of a DDSP instrument (ddsp.rs): pitch and loudness in, per frame, out come the
//! harmonics' levels and the noise's spectrum. A small network trained offline on CC0 recordings
//! (docs/AI_MODELS.md; the weights ship in data/ddsp/): two 3-layer MLPs (Linear → LayerNorm →
//! leaky ReLU) for pitch and loudness, a GRU that gives it a sense of time (a bow's attack, a
//! swell), an output MLP and a linear head. Plain f32 matrix-vector products in a fixed order, so a
//! render is the same on every machine.

use serde::Deserialize;
use std::collections::HashMap;

#[derive(Deserialize, Clone, Debug)]
pub struct Stats {
    pub ld_mean: f64,
    pub ld_std: f64,
    pub ld_p10: f64,
    pub ld_p95: f64,
    pub ld_min: f64,
}

#[derive(Deserialize)]
struct TensorInfo {
    name: String,
    shape: Vec<usize>,
    offset: usize,
}

#[derive(Deserialize)]
struct Header {
    sr: f64,
    harmonics: usize,
    bands: usize,
    stats: Stats,
    tensors: Vec<TensorInfo>,
}

struct Linear {
    w: Vec<f32>,
    b: Vec<f32>,
    i: usize,
}
impl Linear {
    fn apply(&self, x: &[f32], out: &mut Vec<f32>) {
        out.clear();
        out.extend(self.b.iter().enumerate().map(|(o, b)| b + self.w[o * self.i..(o + 1) * self.i].iter().zip(x).map(|(w, x)| w * x).sum::<f32>()));
    }
}

struct Mlp {
    layers: Vec<(Linear, Vec<f32>, Vec<f32>)>,
}
impl Mlp {
    fn apply(&self, x: &[f32]) -> Vec<f32> {
        let mut cur = x.to_vec();
        let mut next = Vec::new();
        for (l, g, b) in &self.layers {
            l.apply(&cur, &mut next);
            let n = next.len() as f32;
            let mean = next.iter().sum::<f32>() / n;
            let var = next.iter().map(|v| (v - mean) * (v - mean)).sum::<f32>() / n;
            let inv = 1.0 / (var + 1e-5).sqrt();
            cur = next.iter().zip(g).zip(b).map(|((v, g), b)| {
                let y = (v - mean) * inv * g + b;
                if y > 0.0 { y } else { 0.01 * y }
            }).collect();
        }
        cur
    }
}

pub struct Decoder {
    f: Mlp,
    ld: Mlp,
    w_ih: Linear,
    w_hh: Linear,
    hidden: usize,
    out: Mlp,
    head: Linear,
    /// The room it learned (at `sr`; the first tap is the dry signal's, left out).
    pub ir: Vec<f32>,
    pub sr: f64,
    pub harmonics: usize,
    pub bands: usize,
    pub stats: Stats,
}

impl Decoder {
    pub fn load(bytes: &[u8]) -> Result<Decoder, String> {
        let hl = u32::from_le_bytes(bytes.get(..4).ok_or("ddsp weights: empty")?.try_into().unwrap()) as usize;
        let h: Header = serde_json::from_slice(&bytes[4..4 + hl]).map_err(|e| format!("ddsp weights: {e}"))?;
        let data: Vec<f32> = crate::mix::wavio::f32_le(&bytes[4 + hl..]);
        let t: HashMap<&str, &TensorInfo> = h.tensors.iter().map(|t| (t.name.as_str(), t)).collect();
        let get = |name: &str| -> Result<(Vec<f32>, Vec<usize>), String> {
            let ti = t.get(name).ok_or(format!("ddsp weights: no {name}"))?;
            let n: usize = ti.shape.iter().product();
            Ok((data.get(ti.offset..ti.offset + n).ok_or(format!("ddsp weights: {name} cut short"))?.to_vec(), ti.shape.clone()))
        };
        let linear = |p: &str| -> Result<Linear, String> {
            let (w, s) = get(&format!("{p}.weight"))?;
            Ok(Linear { w, b: get(&format!("{p}.bias"))?.0, i: s[1] })
        };
        let mlp = |p: &str| -> Result<Mlp, String> {
            Ok(Mlp { layers: (0..3).map(|k| Ok((linear(&format!("{p}.l.{k}"))?, get(&format!("{p}.n.{k}.weight"))?.0, get(&format!("{p}.n.{k}.bias"))?.0))).collect::<Result<_, String>>()? })
        };
        let (wih, s) = get("gru.weight_ih_l0")?;
        let (whh, sh) = get("gru.weight_hh_l0")?;
        Ok(Decoder {
            f: mlp("f")?,
            ld: mlp("ld")?,
            w_ih: Linear { w: wih, b: get("gru.bias_ih_l0")?.0, i: s[1] },
            w_hh: Linear { w: whh, b: get("gru.bias_hh_l0")?.0, i: sh[1] },
            hidden: sh[1],
            out: mlp("out")?,
            head: linear("head")?,
            ir: get("ir")?.0,
            sr: h.sr,
            harmonics: h.harmonics,
            bands: h.bands,
            stats: h.stats,
        })
    }

    /// The head's raw outputs for each frame of pitch (Hz) and loudness (dB).
    pub fn run(&self, f0: &[f64], ld: &[f64]) -> Vec<Vec<f32>> {
        let g = self.hidden;
        let mut hstate = vec![0f32; g];
        let (mut gi, mut gh, mut o) = (Vec::new(), Vec::new(), Vec::new());
        f0.iter().zip(ld).map(|(&f, &l)| {
            let a = self.f.apply(&[(12.0 * (f / 440.0).log2() / 24.0) as f32]);
            let b = self.ld.apply(&[((l - self.stats.ld_mean) / self.stats.ld_std) as f32]);
            let x: Vec<f32> = a.iter().chain(&b).copied().collect();
            self.w_ih.apply(&x, &mut gi);
            self.w_hh.apply(&hstate, &mut gh);
            let sig = |v: f32| 1.0 / (1.0 + (-v).exp());
            for k in 0..g {
                let r = sig(gi[k] + gh[k]);
                let z = sig(gi[g + k] + gh[g + k]);
                let n = (gi[2 * g + k] + r * gh[2 * g + k]).tanh();
                hstate[k] = (1.0 - z) * n + z * hstate[k];
            }
            let cat: Vec<f32> = hstate.iter().chain(&a).chain(&b).copied().collect();
            let y = self.out.apply(&cat);
            self.head.apply(&y, &mut o);
            o.clone()
        }).collect()
    }
}

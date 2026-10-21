//! Listening, for agents and the mix readout: `analyze` (tempo, key, chords, notes, timbre: analyze.rs,
//! tempo.rs, meter.rs, keyfind.rs), `inspect` (what is wrong with a recording: inspect.rs, rt60.rs,
//! spectrogram.rs), a mix's balance and loudness figures (balance.rs, loudstats.rs), and the shared
//! STFT (stft.rs).

pub mod analyze;
pub mod balance;
pub mod inspect;
pub mod keyfind;
pub mod loudness;
pub mod loudstats;
#[cfg(test)]
mod loudness_parity;
pub mod meter;
pub mod notes;
pub mod rt60;
pub mod spectrogram;
pub mod stft;
pub mod tempo;

/// `rostrum-sound analyze <mono.f32> <rate> [--notes]`.
pub fn analyze_cmd(args: &[String]) -> Result<(), String> {
    let bytes = std::fs::read(&args[1]).map_err(|e| format!("{}: {e}", args[1]))?;
    let x = crate::mix::wavio::f32_le(&bytes);
    let rate: f64 = args[2].parse().map_err(|_| format!("analyze: the rate is a number; got {}", args[2]))?;
    println!("{}", analyze::analyze_asked(&x, rate, &analyze::Ask::from_args(args)?));
    Ok(())
}

/// `rostrum-sound inspect <clip.wav> [--png <out.png>]`.
pub fn inspect_cmd(args: &[String]) -> Result<(), String> {
    let (l, r, sr) = crate::mix::wavio::read_stereo(&args[1])?;
    let png = args.iter().position(|a| a == "--png").and_then(|i| args.get(i + 1)).map(String::as_str);
    println!("{}", inspect::inspect(&l, &r, sr, png)?);
    Ok(())
}

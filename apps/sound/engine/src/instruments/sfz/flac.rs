//! FLAC samples for SFZ instruments (the sfzinstruments libraries — Karoryfer, Versilian — ship
//! FLAC): decoded once into the same stereo frames a WAV gives (sfz.rs `Sample`), so a region
//! plays the same whatever the file format. Decoding is claxon (Apache-2.0, pure Rust).

use std::path::Path;

use super::Sample;

pub fn read_flac(path: &Path) -> Result<Sample, String> {
    let err = |e: claxon::Error| format!("{}: {e}", path.display());
    let mut r = claxon::FlacReader::open(path).map_err(err)?;
    let info = r.streaminfo();
    let (ch, bits) = (info.channels as usize, info.bits_per_sample);
    if ch == 0 || bits == 0 || bits > 32 { return Err(format!("{}: FLAC with {ch} channels at {bits} bits is not supported", path.display())); }
    let scale = 1.0 / (1u64 << (bits - 1)) as f32;
    let mut frames = Vec::with_capacity(info.samples.unwrap_or(0) as usize);
    let mut buf = Vec::new();
    let mut blocks = r.blocks();
    while let Some(block) = blocks.read_next_or_eof(std::mem::take(&mut buf)).map_err(err)? {
        let l = block.channel(0);
        let rr = if ch > 1 { block.channel(1) } else { l };
        frames.extend(l.iter().zip(rr).map(|(&a, &b)| [a as f32 * scale, b as f32 * scale]));
        buf = block.into_buffer();
    }
    Ok(Sample { frames, rate: info.sample_rate as f64, looped: None })
}

#[cfg(test)]
mod tests {
    #[test]
    fn a_missing_flac_is_an_error_naming_the_file() {
        let e = super::read_flac(std::path::Path::new("no/such/file.flac")).err().unwrap();
        assert!(e.contains("file.flac"), "{e}");
    }
}

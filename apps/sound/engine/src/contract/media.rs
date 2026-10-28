//! The engine decodes media itself (contract rule 5): a file (WAV, FLAC, OGG Vorbis, MP3, the audio of MP4 /
//! MOV) is decoded once, made stereo, resampled to the mix's rate and kept in the cache (`sound/media/`),
//! keyed by its path, size, modified time, the rate and this decoder's version. A clip's in-point and
//! length cut a slice of that, also kept. The job then reads raw f32 files (schedule/content.rs Pcm).

use super::error::Error;
use serde_json::{json, Value};
use std::path::{Path, PathBuf};

/// Bump when decoding or resampling changes what comes out (the cache key includes it).
const DECODER: &str = "media-v1";

/// A decoded slice: the job's Pcm (`{file, channels, frames}`) and its length in seconds.
pub struct Slice {
    pub pcm: Value,
    pub seconds: f64,
}

fn cache_dir() -> PathBuf {
    // ROSTRUM_CACHE_MB=0 and tests keep no cache; the slices still need a file for the job to read.
    crate::mix::cache::dir("media").unwrap_or_else(|| std::env::temp_dir().join("rostrum-sound-media"))
}

/// `length` None: to the file's end.
pub fn slice(path: &str, rate: u32, start: f64, length: Option<f64>, at: &str) -> Result<Slice, Error> {
    let file = Path::new(path);
    let meta = std::fs::metadata(file).map_err(|e| Error::not_found(at, &format!("\"{path}\""), format!("cannot be read ({e})")))?;
    let mtime = meta.modified().ok().and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok()).map_or(0, |d| d.as_nanos());
    let key = blake3::hash(format!("{}|{}|{mtime}|{rate}|{DECODER}", file.display(), meta.len()).as_bytes()).to_hex()[..24].to_string();
    let dir = cache_dir();
    std::fs::create_dir_all(&dir).map_err(|e| Error::render(format!("media cache {}: {e}", dir.display())))?;
    let whole = dir.join(format!("{key}.f32"));
    if !whole.is_file() {
        let data = decode(file, rate).map_err(|e| Error::new("BAD_ARGUMENT", at, format!("\"{path}\""), e))?;
        write_atomic(&whole, &data)?;
    }
    let frames = (std::fs::metadata(&whole).map_err(|e| Error::render(e.to_string()))?.len() / 8) as usize;
    let a = (start * rate as f64).round() as usize;
    let b = length.map_or(frames, |l| (a + (l * rate as f64).round() as usize).min(frames));
    if a >= frames || b <= a {
        return Err(Error::new("BAD_ARGUMENT", at, format!("in {start} s"), format!("is past the end of \"{path}\" ({:.3} s long)", frames as f64 / rate as f64)));
    }
    let file = if a == 0 && b == frames {
        whole
    } else {
        let cut = dir.join(format!("{key}-{a}-{b}.f32"));
        if !cut.is_file() {
            let bytes = std::fs::read(&whole).map_err(|e| Error::render(format!("{}: {e}", whole.display())))?;
            write_bytes(&cut, &bytes[a * 8..b * 8])?;
        }
        cut
    };
    Ok(Slice { pcm: json!({ "file": file.to_string_lossy(), "channels": 2, "frames": b - a }), seconds: (b - a) as f64 / rate as f64 })
}

fn write_atomic(path: &Path, data: &[f32]) -> Result<(), Error> {
    let bytes: Vec<u8> = data.iter().flat_map(|x| x.to_le_bytes()).collect();
    write_bytes(path, &bytes)
}

fn write_bytes(path: &Path, bytes: &[u8]) -> Result<(), Error> {
    let tmp = path.with_extension(format!("tmp{}", std::process::id()));
    std::fs::write(&tmp, bytes).and_then(|_| std::fs::rename(&tmp, path)).map_err(|e| {
        let _ = std::fs::remove_file(&tmp);
        Error::render(format!("media cache {}: {e}", path.display()))
    })
}

/// The whole file as interleaved stereo f32 at `rate`.
fn decode(path: &Path, rate: u32) -> Result<Vec<f32>, String> {
    let (stereo, from) = decode_native(path)?;
    let frames = crate::live::frames::Frames { channels: 2, mask: 0x3, data: stereo };
    Ok(crate::live::frames::resample(&frames, from, rate as f64).data)
}

/// The whole file as interleaved stereo f32 at its own sample rate (an SFZ sample in OGG / MP3 plays from this).
pub(crate) fn decode_native(path: &Path) -> Result<(Vec<f32>, f64), String> {
    use symphonia::core::audio::SampleBuffer;
    use symphonia::core::codecs::{DecoderOptions, CODEC_TYPE_NULL};
    use symphonia::core::errors::Error as E;
    use symphonia::core::formats::FormatOptions;
    use symphonia::core::io::MediaSourceStream;
    use symphonia::core::meta::MetadataOptions;
    use symphonia::core::probe::Hint;

    let f = std::fs::File::open(path).map_err(|e| format!("cannot be opened ({e})"))?;
    let mss = MediaSourceStream::new(Box::new(f), Default::default());
    let mut hint = Hint::new();
    if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
        hint.with_extension(ext);
    }
    let formats = super::names::MEDIA_FORMATS.join(", ");
    let probed = symphonia::default::get_probe().format(&hint, mss, &FormatOptions::default(), &MetadataOptions::default())
        .map_err(|e| format!("is not a sound file this engine reads ({e}); it reads {formats}"))?;
    let mut format = probed.format;
    let track = format.tracks().iter().find(|t| t.codec_params.codec != CODEC_TYPE_NULL).ok_or("has no audio track")?;
    let (id, from) = (track.id, track.codec_params.sample_rate.ok_or("has no sample rate")?);
    let mut dec = symphonia::default::get_codecs().make(&track.codec_params, &DecoderOptions::default()).map_err(|e| format!("audio codec not supported ({e})"))?;
    let mut stereo: Vec<f32> = vec![];
    loop {
        let packet = match format.next_packet() {
            Ok(p) => p,
            Err(E::IoError(e)) if e.kind() == std::io::ErrorKind::UnexpectedEof => break,
            Err(E::ResetRequired) => break,
            Err(e) => return Err(format!("cannot be read to the end ({e})")),
        };
        if packet.track_id() != id {
            continue;
        }
        let buf = match dec.decode(&packet) {
            Ok(b) => b,
            Err(E::DecodeError(_)) => continue, // one damaged packet: skip it, as players do
            Err(e) => return Err(format!("cannot be decoded ({e})")),
        };
        let spec = *buf.spec();
        let ch = spec.channels.count().max(1);
        let mut sb = SampleBuffer::<f32>::new(buf.capacity() as u64, spec);
        sb.copy_interleaved_ref(buf);
        for f in sb.samples().chunks_exact(ch) {
            let (l, r) = if ch == 1 { (f[0], f[0]) } else { (f[0], f[1]) };
            stereo.extend([l, r]);
        }
    }
    if stereo.is_empty() {
        return Err("has no audio".into());
    }
    Ok((stereo, from as f64))
}

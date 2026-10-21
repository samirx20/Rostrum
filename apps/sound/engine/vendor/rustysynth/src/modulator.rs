//! Rostrum patch: SoundFont modulators (SF2 2.04 §8.2–8.4). Upstream rustysynth discards the
//! `pmod` / `imod` chunks, so a font that shapes its velocity layers with modulators (MuseScore
//! General's pianos: a 300 Hz filter a velocity modulator opens, layers cross-faded by velocity)
//! plays its soft layers dull and quiet and its loud layer ~20 dB louder. Modulators whose sources
//! are fixed at note-on (velocity, key, none) are summed into the voice's generators when it
//! starts; ones driven by controllers / pressure / pitch wheel are left to the channel (as before).

use std::io::Read;

use crate::binary_reader::BinaryReader;
use crate::error::SoundFontError;
use crate::generator_type::GeneratorType;

#[derive(Clone, Copy, Debug, PartialEq)]
pub(crate) struct Modulator {
    pub(crate) src: u16,
    pub(crate) dest: u16,
    pub(crate) amount: i16,
    pub(crate) amt_src: u16,
    pub(crate) transform: u16,
}

/// The default modulators that depend only on the note (SF2 2.04 §8.4.1, §8.4.2): velocity to
/// attenuation (negative concave, 960 cB) and velocity to filter cutoff (negative linear, −2400 cents).
pub(crate) const DEFAULTS: [Modulator; 2] = [
    Modulator { src: 0x0502, dest: GeneratorType::INITIAL_ATTENUATION as u16, amount: 960, amt_src: 0, transform: 0 },
    Modulator { src: 0x0102, dest: GeneratorType::INITIAL_FILTER_CUTOFF_FREQUENCY as u16, amount: -2400, amt_src: 0, transform: 0 },
];

impl Modulator {
    pub(crate) fn read_from_chunk<R: Read>(reader: &mut R, size: usize) -> Result<Vec<Modulator>, SoundFontError> {
        if !size.is_multiple_of(10) {
            return Err(SoundFontError::InvalidGeneratorList);
        }
        let mut list = Vec::with_capacity(size / 10);
        for _ in 0..size / 10 {
            list.push(Modulator {
                src: BinaryReader::read_u16(reader)?,
                dest: BinaryReader::read_u16(reader)?,
                amount: BinaryReader::read_i16(reader)?,
                amt_src: BinaryReader::read_u16(reader)?,
                transform: BinaryReader::read_u16(reader)?,
            });
        }
        Ok(list)
    }

    /// Same modulator (§9.5.1): same sources, destination and transform; a later one replaces it.
    pub(crate) fn same(&self, o: &Modulator) -> bool {
        self.src == o.src && self.dest == o.dest && self.amt_src == o.amt_src && self.transform == o.transform
    }

    /// Whether every source is fixed when the note starts.
    pub(crate) fn note_only(&self) -> bool {
        fixed(self.src) && fixed(self.amt_src) && (self.dest as usize) < GeneratorType::COUNT
    }

    /// This modulator's contribution to its destination generator for a note.
    pub(crate) fn value(&self, key: i32, velocity: i32) -> f32 {
        let v = self.amount as f32 * source(self.src, key, velocity) * source(self.amt_src, key, velocity);
        if self.transform == 2 { v.abs() } else { v }
    }
}

/// A general-controller source (no controller, velocity, key): the others move during a note.
fn fixed(src: u16) -> bool {
    src & 0x80 == 0 && matches!(src & 0x7F, 0 | 2 | 3)
}

/// A source's value (§8.2): its 7-bit input mapped by direction, polarity and curve.
fn source(src: u16, key: i32, velocity: i32) -> f32 {
    let raw = match src & 0x7F {
        0 => return 1.0, // no controller: the amount as is
        2 => velocity,
        3 => key,
        _ => return 0.0,
    };
    let mut x = raw.clamp(0, 127) as f32 / 127.0;
    if src & 0x100 != 0 {
        x = 1.0 - x;
    }
    let curve = |u: f32| match src >> 10 {
        1 => concave(u),
        2 => 1.0 - concave(1.0 - u),
        3 => if u >= 0.5 { 1.0 } else { 0.0 },
        _ => u,
    };
    if src & 0x200 == 0 {
        curve(x)
    } else if x >= 0.5 {
        curve(2.0 * x - 1.0)
    } else {
        -curve(1.0 - 2.0 * x)
    }
}

/// The spec's concave curve: −20/96 · log10((1 − u)²), clamped to [0, 1].
fn concave(u: f32) -> f32 {
    if u >= 1.0 { 1.0 } else { (-(40.0 / 96.0) * (1.0 - u).log10()).clamp(0.0, 1.0) }
}

/// The note-only modulators of a zone: its global zone's, replaced by its own identical ones.
pub(crate) fn merge(global: &[Modulator], local: &[Modulator]) -> Vec<Modulator> {
    let mut list: Vec<Modulator> = global.iter().filter(|m| !local.iter().any(|l| l.same(m))).copied().collect();
    list.extend(local.iter().copied());
    list.retain(|m| m.note_only());
    list
}

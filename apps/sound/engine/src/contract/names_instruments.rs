//! The plain instrument names (`{"builtIn": "piano"}`) and what each plays, in one table (Sam's choice by ear,
//! GAP.md § 1): a recorded instrument (a pack's SFZ file per articulation, the first the default; or a
//! section split by pitch into zones of other entries), an analog synth preset, or a classic synthesized
//! voice (instruments/voices/tones.rs, only by `classic.<name>` or where no recording exists). Kits too.
//! A document keeps the name as written; changing a row here changes every song that uses it.

/// A recorded instrument: its pack folder (under `<assets>/sounds/`), its articulations' files relative to
/// it (the first plays by default), or `zones` (highest MIDI key, entry id) that split a section by pitch.
pub struct Recorded {
    pub id: &'static str,
    pub pack: &'static str,
    pub about: &'static str,
    /// Playable MIDI keys, low and high.
    pub range: (u8, u8),
    pub arts: &'static [(&'static str, &'static str)],
    pub zones: &'static [(u8, &'static str)],
    /// What its licence asks every work using it to say (CC-BY packs).
    pub credit: Option<&'static str>,
    /// Half steps the pack's file maps each sample above the pitch it sounds (Growlybass names every sample an octave
    /// high): a note asks the file for its key plus this, so it plays at the pitch written.
    pub key_offset: i8,
}

const fn rec(id: &'static str, pack: &'static str, about: &'static str, range: (u8, u8), arts: &'static [(&'static str, &'static str)]) -> Recorded {
    Recorded { id, pack, about, range, arts, zones: &[], credit: None, key_offset: 0 }
}

const VS: &str = "vsco2-strings";
const VB: &str = "vsco2-brass";
const VW: &str = "vsco2-woodwinds";
const VM: &str = "vcsl-mallets";
const SALAMANDER: &str = "Salamander Grand Piano by Alexander Holm (CC-BY 3.0)";
const WURLITZER: &str = "Wurlitzer EP200 samples by Greg Sullivan (CC-BY 3.0)";
const RHODES: &str = "Rhodes Mark II samples by Tim Kahn (freesound.org, CC-BY 4.0)";
pub const MULDJORD: &str = "Drum samples provided by DrumGizmo.org (MuldjordKit by Lars Muldjord, CC-BY 4.0)";

pub const RECORDED: &[Recorded] = &[
    rec("violins", VS, "violin section (VSCO 2)", (55, 86), &[("sustain", "ViolinEnsSusVib.sfz"), ("soft", "ViolinEnsSusVib-Quiet.sfz"), ("spiccato", "ViolinEnsSpic.sfz"), ("tremolo", "ViolinEnsTrem.sfz"), ("pizzicato", "ViolinEnsPizz.sfz")]),
    rec("violas", VS, "viola section (VSCO 2)", (48, 86), &[("sustain", "ViolaEnsSusVib.sfz"), ("soft", "ViolaEnsSusVib-Quiet.sfz"), ("spiccato", "ViolaEnsSpic.sfz"), ("tremolo", "ViolaEnsTrem.sfz"), ("pizzicato", "ViolaEnsPizz.sfz")]),
    rec("cellos", VS, "cello section (VSCO 2)", (36, 77), &[("sustain", "CelloEnsSusVib.sfz"), ("soft", "CelloEnsSusVib-Quiet.sfz"), ("spiccato", "CelloEnsSpic.sfz"), ("tremolo", "CelloEnsTrem.sfz"), ("pizzicato", "CelloEnsPizz.sfz")]),
    rec("basses", VS, "contrabass (VSCO 2, solo: the library's only bass)", (24, 60), &[("sustain", "ContrabassSusVB.sfz"), ("soft", "ContrabassSusVB-Quiet.sfz"), ("spiccato", "ContrabassSpic.sfz"), ("tremolo", "ContrabassTrem.sfz"), ("pizzicato", "ContrabassPizz.sfz"), ("nonVibrato", "ContrabassSusNV.sfz")]),
    Recorded { id: "strings", pack: VS, about: "string section (VSCO 2): basses below C2, cellos to B2, violas to F#3, violins above", range: (24, 86), arts: &[], zones: &[(35, "basses"), (47, "cellos"), (54, "violas"), (127, "violins")], credit: None, key_offset: 0 },
    rec("violin", VS, "solo violin (VSCO 2)", (55, 96), &[("sustain", "SViolinVib.sfz"), ("soft", "SViolinVib-Quiet.sfz"), ("spiccato", "SViolinSpic.sfz"), ("tremolo", "SViolinTrem.sfz"), ("pizzicato", "SViolinPizz.sfz")]),
    rec("harp", VS, "concert harp (VSCO 2)", (28, 101), &[("pluck", "Harp.sfz")]),
    rec("horn", VB, "French horn (VSCO 2)", (33, 77), &[("sustain", "FHornSus.sfz"), ("staccato", "FHornStac.sfz"), ("muted", "FHornMute.sfz")]),
    rec("trumpet", VB, "trumpet (VSCO 2)", (52, 84), &[("sustain", "TrumpetSus.sfz"), ("vibrato", "TrumpetSusVib.sfz"), ("staccato", "TrumpetStac.sfz"), ("muted", "TrumpetStraightMuteSus.sfz")]),
    rec("trombone", VB, "tenor trombone (VSCO 2)", (34, 65), &[("sustain", "TromboneSus.sfz"), ("vibrato", "TromboneVib.sfz"), ("staccato", "TromboneStac.sfz")]),
    rec("tuba", VB, "tuba (VSCO 2)", (29, 62), &[("sustain", "TubaSus.sfz"), ("staccato", "TubaStac.sfz")]),
    Recorded { id: "brass", pack: VB, about: "brass section (VSCO 2): tuba to D2, trombone to A3, horn to A#4, trumpet above", range: (29, 84), arts: &[], zones: &[(38, "tuba"), (57, "trombone"), (70, "horn"), (127, "trumpet")], credit: None, key_offset: 0 },
    rec("flute", VW, "flute (VSCO 2)", (60, 96), &[("sustain", "FluteSusVib.sfz"), ("nonVibrato", "FluteSusNV.sfz"), ("staccato", "FluteStac.sfz")]),
    rec("piccolo", VW, "piccolo (VSCO 2)", (67, 91), &[("sustain", "PiccoloSus.sfz"), ("staccato", "PiccoloStac.sfz")]),
    rec("oboe", VW, "oboe (VSCO 2)", (58, 89), &[("sustain", "OboeSusVib.sfz"), ("nonVibrato", "OboeSusNV.sfz"), ("staccato", "OboeStac.sfz")]),
    rec("clarinet", VW, "clarinet (VSCO 2)", (50, 90), &[("sustain", "ClarinetSus.sfz"), ("staccato", "ClarinetStac.sfz")]),
    rec("bassoon", VW, "bassoon (VSCO 2)", (34, 75), &[("sustain", "BassoonSus.sfz"), ("vibrato", "BassoonVib.sfz"), ("staccato", "BassoonStac.sfz")]),
    rec("timpani", "vsco2-percussion", "timpani (VSCO 2)", (36, 60), &[("hit", "Timpani.sfz"), ("roll", "TimpaniRolls.sfz")]),
    Recorded { credit: Some(SALAMANDER), ..rec("concertGrand", "salamander-piano", "concert grand piano (Salamander Grand Piano V3, a Yamaha C5)", (21, 108), &[("keys", "SalamanderGrandPianoV3_44.1khz16bit/SalamanderGrandPianoV3.sfz")]) },
    Recorded { credit: Some(RHODES), ..rec("rhodes", "rhodes", "Fender Rhodes Mark II 73 electric piano, one velocity layer (Tim Kahn); F4 to C#6 are stretched from E4 and D6, crossfaded over B4 to G5", (28, 100), &[("keys", "rhodes.sfz")]) },
    Recorded { credit: Some(WURLITZER), ..rec("wurlitzer", "wurlitzer", "Wurlitzer EP200 electric piano", (33, 96), &[("keys", "Wurlitzer EP200/Wurlitzer EP200.sfz")]) },
    rec("drawbarOrgan", "drawbar-organ", "tonewheel drawbar organ (FreePats)", (33, 98), &[("keys", "DrawbarOrganEmulation-SFZ-20190712/DrawbarOrganEmulation-20190712.sfz")]),
    rec("pipeOrgan", "vcsl-organ", "pipe organ, loud registration (VCSL)", (36, 97), &[("keys", "Aerophones/Edge-blown Aerophones/Pipe Organ - Loud.sfz"), ("pedal", "Aerophones/Edge-blown Aerophones/Pipe Organ - Loud Pedal.sfz")]),
    rec("nylonGuitar", "freepats-guitar", "Spanish classical guitar, fingerstyle (FreePats)", (29, 83), &[("fingerstyle", "SpanishClassicalGuitar-SF2-20190618/SpanishClassicalGuitar-20190618.sf2")]),
    rec("archtopGuitar", "shinyguitar", "archtop steel-string guitar (Karoryfer Shinyguitar)", (33, 91), &[("fingerstyle", "Programs/rostrum-acoustic.sfz")]),
    rec("cleanGuitar", "fsbs-clean-guitar", "electric guitar, clean (FreePats FSBS)", (35, 86), &[("pluck", "EGuitarFSBS-clean SFZ+FLAC-20260807/EGuitarFSBS-clean bridge 20260807.sfz")]),
    Recorded { key_offset: 12, ..rec("jazzBass", "growlybass", "electric bass, fingered (Karoryfer Growlybass)", (21, 67), &[("fingerstyle", "growlybass_clean.sfz")]) },
    rec("uprightBass", "dsmolken-bass", "double bass, pizzicato (D. Smolken)", (24, 60), &[("pizzicato", "d_smolken_rubner_bass_pizz.sfz")]),
    rec("cello", "bigcat-cello", "solo cello (Karoryfer x bigcat)", (36, 77), &[("sustain", "Programs/vc_arco_sus_map.sfz"), ("pizzicato", "Programs/vc_pizz_basic.sfz")]),
    rec("tenorSax", "vcsl-sax", "tenor saxophone (VCSL)", (44, 89), &[("sustain", "Aerophones/Reed Aerophones/Tenor Saxophone - Non-Vibrato.sfz"), ("vibrato", "Aerophones/Reed Aerophones/Tenor Saxophone - Vibrato.sfz"), ("staccato", "Aerophones/Reed Aerophones/Tenor Saxophone - Staccato.sfz")]),
    rec("harmonica", "vcsl-harmonica", "chromatic harmonica, Hohner Super 64 (VCSL): a plain breath, an accented one, a vibrato one; the breath-out sound plays when a key lifts", (47, 98), &[("sustain", "harmonica.sfz"), ("accent", "harmonica-accent.sfz"), ("vibrato", "harmonica-vibrato.sfz")]),
    rec("marimba", VM, "marimba (VCSL)", (41, 97), &[("mallet", "Idiophones/Struck Idiophones/Marimba.sfz")]),
    rec("vibraphone", VM, "vibraphone, hard mallets (VCSL)", (53, 89), &[("mallet", "Idiophones/Struck Idiophones/Vibraphone - Hard Mallets.sfz")]),
    rec("xylophone", VM, "xylophone (VCSL)", (55, 97), &[("mallet", "Idiophones/Struck Idiophones/Xylophone - Medium Mallets.sfz")]),
    rec("glockenspiel", VM, "glockenspiel (VCSL)", (67, 97), &[("mallet", "Idiophones/Struck Idiophones/Glockenspiel.sfz")]),
    rec("tubularBells", VM, "tubular bells (VCSL)", (60, 79), &[("mallet", "Idiophones/Struck Idiophones/Tubular Bells 2.sfz")]),
];

/// What a plain name plays: a recorded entry (and the articulation it starts in, else the entry's first),
/// a synth preset, or a classic synthesized voice.
pub enum Plays {
    Rec(&'static str, Option<&'static str>),
    Synth(&'static str),
    Classic(&'static str),
}
use Plays::{Classic, Rec, Synth};

pub const PLAIN: &[(&str, Plays)] = &[
    ("piano", Rec("concertGrand", None)), ("grandPiano", Rec("concertGrand", None)), ("acousticPiano", Rec("concertGrand", None)), ("feltPiano", Rec("concertGrand", None)),
    ("electricPiano", Rec("wurlitzer", None)), ("wurlitzer", Rec("wurlitzer", None)), ("rhodes", Rec("rhodes", None)),
    ("organ", Rec("drawbarOrgan", None)), ("drawbarOrgan", Rec("drawbarOrgan", None)), ("pipeOrgan", Rec("pipeOrgan", None)),
    ("guitar", Rec("nylonGuitar", None)), ("nylonGuitar", Rec("nylonGuitar", None)),
    ("acousticGuitar", Rec("archtopGuitar", None)), ("steelGuitar", Rec("archtopGuitar", None)), ("archtopGuitar", Rec("archtopGuitar", None)),
    ("electricGuitar", Rec("cleanGuitar", None)), ("cleanGuitar", Rec("cleanGuitar", None)),
    ("bass", Rec("jazzBass", None)), ("electricBass", Rec("jazzBass", None)), ("bassGuitar", Rec("jazzBass", None)),
    ("uprightBass", Rec("uprightBass", None)), ("doubleBass", Rec("uprightBass", None)),
    ("strings", Rec("strings", None)), ("analogStrings", Rec("strings", None)), ("spiccatoStrings", Rec("strings", Some("spiccato"))),
    ("violins", Rec("violins", None)), ("violas", Rec("violas", None)), ("cellos", Rec("cellos", None)), ("basses", Rec("basses", None)),
    ("violin", Rec("violin", None)), ("harp", Rec("harp", None)), ("cello", Rec("cello", None)),
    ("horn", Rec("horn", None)), ("brass", Rec("brass", None)), ("cinematicBrass", Rec("brass", None)), ("trumpet", Rec("trumpet", None)), ("mutedTrumpet", Rec("trumpet", Some("muted"))), ("trombone", Rec("trombone", None)), ("tuba", Rec("tuba", None)),
    ("flute", Rec("flute", None)), ("piccolo", Rec("piccolo", None)), ("oboe", Rec("oboe", None)), ("clarinet", Rec("clarinet", None)), ("bassoon", Rec("bassoon", None)),
    ("saxophone", Rec("tenorSax", None)), ("tenorSax", Rec("tenorSax", None)),
    ("harmonica", Rec("harmonica", None)),
    ("marimba", Rec("marimba", None)), ("glassMarimba", Rec("marimba", None)), ("vibraphone", Rec("vibraphone", None)), ("xylophone", Rec("xylophone", None)),
    ("glockenspiel", Rec("glockenspiel", None)), ("tubularBells", Rec("tubularBells", None)), ("timpani", Rec("timpani", None)),
    ("warmPad", Synth("analogPad")), ("pad", Synth("analogPad")), ("subBass", Synth("analogBass")), ("pluck", Synth("analogPluck")),
    ("choirPad", Classic("choirPad")),
];

/// The synthesized voices (instruments/voices/tones.rs), played by `classic.<name>`.
pub const CLASSIC: &[&str] = &["feltPiano", "grandPiano", "warmPad", "analogStrings", "spiccatoStrings", "choirPad", "cinematicBrass", "subBass", "glassMarimba"];

/// The analog presets (the experiment's analogPad / analogBass / analogPluck, Sam 2026-10-15), as the engine's synth spec.
pub const PRESETS: &[(&str, &str, &str)] = &[
    ("analogPad", "a slow analog pad: seven drifting saws, a filter that opens over a second and breathes with a slow LFO, a little air and a sub",
     r#"{"wave":"saw","voices":7,"detune":16,"cutoff":900,"resonance":0.12,"envAmount":1.4,"filterEnv":{"attack":0.9,"decay":2.5,"sustain":0.5,"release":1.6},"attack":0.5,"decay":1.5,"sustain":0.85,"release":1.8,"octave":0,"glide":0,"filterVelocity":0,"drive":0,"lfo":{"wave":"triangle","rate":0.23,"pitch":0,"cutoff":0.3,"amp":0,"delay":0.6},"drift":6,"noise":0.03,"sub":0.2,"curve":"analog","level":2,"width":1}"#),
    ("analogBass", "a round analog bass: a drifting triangle with a sine sub an octave down, low-passed and lightly driven, mono",
     r#"{"wave":"triangle","voices":1,"detune":12,"cutoff":850,"resonance":0.1,"envAmount":0.8,"filterEnv":{"attack":0.002,"decay":0.3,"sustain":0.4,"release":0.1},"attack":0.004,"decay":0.5,"sustain":0.85,"release":0.12,"octave":0,"glide":0,"filterVelocity":0,"drive":1.6,"drift":2.5,"noise":0,"sub":0.7,"curve":"analog","level":2,"width":0}"#),
    ("analogPluck", "an analog pluck: three drifting saws, a snappy filter that velocity opens, a breath of noise on the attack",
     r#"{"wave":"saw","voices":3,"detune":9,"cutoff":520,"resonance":0.22,"envAmount":3.6,"filterEnv":{"attack":0.001,"decay":0.25,"sustain":0,"release":0.2},"filterVelocity":1.2,"attack":0.001,"decay":0.55,"sustain":0,"release":0.3,"octave":0,"glide":0,"drive":0,"pitchEnv":{"semitones":0.4,"time":0.008},"drift":4,"noise":0.015,"sub":0,"curve":"analog","level":6,"width":1}"#),
];

/// A drum kit (`{"kit": …}`): its SFZ on General MIDI keys, and a kit that fills the keys it lacks; `None` file:
/// the synthesized kit.
pub struct Kit {
    pub name: &'static str,
    pub about: &'static str,
    pub file: Option<(&'static str, &'static str)>,
    pub fill: Option<(&'static str, &'static str)>,
    pub credit: Option<&'static str>,
}

const STUDIO: (&str, &str) = ("studio-kit", "studio-kit.sfz");

pub const KITS: &[Kit] = &[
    Kit { name: "drums", about: "recorded rock kit (MuldjordKit); rim, clap and shaker from the studio kit", file: Some(("muldjord-kit", "MuldjordKit SFZ+FLAC-20201018/rostrum-gm.sfz")), fill: Some(STUDIO), credit: Some(MULDJORD) },
    Kit { name: "studio", about: "recorded studio kit (Karoryfer Big Rusty Drums, VCSL claps and shaker)", file: Some(STUDIO), fill: None, credit: None },
    Kit { name: "jazz", about: "recorded jazz kit played with brushes (Karoryfer Swirly Drums): brush snare and stir, ride, hats, toms; rim, clap, shaker and ride bell from the studio kit", file: Some(("swirly-kit", "swirly-kit.sfz")), fill: Some(STUDIO), credit: None },
    Kit { name: "classic", about: "the synthesized kit", file: None, fill: None, credit: None },
];

pub fn recorded(id: &str) -> Option<&'static Recorded> {
    RECORDED.iter().find(|r| r.id == id)
}

pub fn plain(name: &str) -> Option<&'static Plays> {
    PLAIN.iter().find(|(n, _)| *n == name).map(|(_, p)| p)
}

pub fn preset(name: &str) -> &'static (&'static str, &'static str, &'static str) {
    PRESETS.iter().find(|p| p.0 == name).expect("a preset the table names")
}

/// Every name `builtIn` accepts: the plain names, then `classic.<voice>`.
pub fn built_in_names() -> Vec<String> {
    PLAIN.iter().map(|(n, _)| n.to_string()).chain(CLASSIC.iter().map(|c| format!("classic.{c}"))).collect()
}

pub fn kit_names() -> Vec<&'static str> {
    KITS.iter().map(|k| k.name).collect()
}

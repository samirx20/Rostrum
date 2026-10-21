use std::ffi::c_void;

use vst3::Steinberg::*;

use super::com::Stream;
use super::plugin::{pack, unpack, vstpreset};
use super::render::render;
use super::*;
#[test]
fn states_pack_and_vstpresets_read() {
    let blob = pack(b"component", b"ctl");
    assert_eq!(unpack(&blob).unwrap(), (&b"component"[..], &b"ctl"[..]));
    assert!(unpack(b"RVS3\x09").is_err());
    // A .vstpreset: header, the two chunks, the chunk list.
    let mut f = b"VST3".to_vec();
    f.extend(1i32.to_le_bytes());
    f.extend([b'0'; 32]);
    let list_at = 48 + 4 + 2;
    f.extend((list_at as i64).to_le_bytes());
    f.extend(b"compct");
    f.extend(b"List");
    f.extend(2i32.to_le_bytes());
    for (id, off, size) in [(b"Comp", 48i64, 4i64), (b"Cont", 52, 2)] {
        f.extend(id);
        f.extend(off.to_le_bytes());
        f.extend(size.to_le_bytes());
    }
    assert_eq!(unpack(&vstpreset(&f).unwrap()).unwrap(), (&b"comp"[..], &b"ct"[..]));
    let s = Stream::new(vec![]);
    unsafe {
        let mut buf = *b"hello";
        s.write(buf.as_mut_ptr() as *mut c_void, 5, std::ptr::null_mut());
        s.seek(1, 0, std::ptr::null_mut());
        let mut out = [0u8; 3];
        let mut got = 0;
        s.read(out.as_mut_ptr() as *mut c_void, 3, &mut got);
        assert_eq!((&out, got), (b"ell", 3));
    }
}

#[test]
fn a_third_party_vst3_instrument_plays_notes_at_their_pitch() {
    let Some(bundle) = folders().into_iter().map(|d| d.join("Surge XT.vst3")).find(|p| p.exists()) else {
        eprintln!("Surge XT (VST3) not installed: skipped");
        return;
    };
    let f = factory(&bundle).unwrap();
    let class = classes(&f).into_iter().find(|c| c.instrument).expect("an instrument class");
    let id: String = class.cid.iter().map(|b| format!("{:02X}", *b as u8)).collect();
    let spec = crate::plugins::clap::PluginSpec { format: "vst3".into(), path: bundle.to_string_lossy().into_owned(), id, params: vec![], state: None, at: 0.0, cc: vec![] };
    let notes = [crate::plugins::clap::Note { start: 4800, end: 4800 + 24000, key: 57, velocity: 0.8 }];
    let (mut l, mut r) = (vec![0f32; 48000], vec![0f32; 48000]);
    render(&spec, &notes, &mut l, &mut r, 48000.0, false).unwrap();
    let peak = l.iter().fold(0f32, |m, v| m.max(v.abs()));
    assert!(peak > 0.01, "the note sounds (peak {peak})");
    let ups = l[9600..24000].windows(2).filter(|w| w[0] < 0.0 && w[1] >= 0.0).count() as f64 / 0.3;
    assert!((ups - 220.0).abs() < 25.0, "{ups} crossings a second");
}

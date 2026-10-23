//! The per-track render cache (trackcache.rs): a cached mix is the uncached mix, bit for bit; a change
//! to one track re-renders that track alone; what acts after the track (its name, ducks) keys nothing.

use crate::mix::render::{render_with, tests::SCHEDULE};
use crate::mix::schedule::Schedule;
use crate::mix::trackcache::TrackCache;

fn bits(chs: &[Vec<f32>]) -> Vec<Vec<u32>> {
    chs.iter().map(|c| c.iter().map(|v| v.to_bits()).collect()).collect()
}

fn folder(name: &str) -> std::path::PathBuf {
    let d = std::env::temp_dir().join(format!("rostrum-trackcache-{name}-{}", std::process::id()));
    let _ = std::fs::remove_dir_all(&d);
    d
}

fn files(d: &std::path::Path) -> usize {
    std::fs::read_dir(d).map(|r| r.count()).unwrap_or(0)
}

#[test]
fn a_cached_mix_is_the_uncached_mix_bit_for_bit() {
    let dir = folder("same");
    let cache = TrackCache::at(dir.clone());
    let s = Schedule::parse(SCHEDULE).unwrap();
    let plain = render_with(&s, None).unwrap();
    let cold = render_with(&s, Some(&cache)).unwrap();
    assert_eq!(files(&dir), 2, "each track stored");
    let warm = render_with(&s, Some(&cache)).unwrap();
    assert_eq!(bits(&plain.channels().unwrap()), bits(&cold.channels().unwrap()));
    assert_eq!(bits(&plain.channels().unwrap()), bits(&warm.channels().unwrap()));
    assert_eq!(plain.ducks.len(), warm.ducks.len());
    assert_eq!(plain.tracks.iter().map(|t| t.lufs.to_bits()).collect::<Vec<_>>(), warm.tracks.iter().map(|t| t.lufs.to_bits()).collect::<Vec<_>>());
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn one_changed_track_re_renders_alone_and_the_mix_matches() {
    let dir = folder("one");
    let cache = TrackCache::at(dir.clone());
    let a = Schedule::parse(SCHEDULE).unwrap();
    render_with(&a, Some(&cache)).unwrap();
    // The fx track's level changes; the keys track's name and ducks act after it renders: same key.
    let changed = SCHEDULE.replace(r#""name":"fx","tone":"neutral","volume":0.9"#, r#""name":"fx","tone":"neutral","volume":0.6"#).replace(r#""name":"keys""#, r#""name":"pads""#);
    let b = Schedule::parse(&changed).unwrap();
    assert_eq!(a.track_keys[0], b.track_keys[0]);
    assert_ne!(a.track_keys[1], b.track_keys[1]);
    let warm = render_with(&b, Some(&cache)).unwrap();
    assert_eq!(files(&dir), 3, "only the changed track was stored again");
    assert_eq!(bits(&render_with(&b, None).unwrap().channels().unwrap()), bits(&warm.channels().unwrap()));
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn a_bus_keys_its_feeders_and_a_named_file_keys_by_its_stamp() {
    // The fx track feeds the keys track (a layered instrument's bus): a change to the feeder changes the bus.
    let fed = SCHEDULE.replace(r#""name":"fx","tone":"neutral","volume":0.9,"pan":0,"reverb":0.2,"#, r#""name":"fx","tone":"neutral","volume":0.9,"pan":0,"reverb":0.2,"into":0,"#);
    let a = Schedule::parse(&fed).unwrap();
    let b = Schedule::parse(&fed.replace(r#""preset":"riser""#, r#""preset":"impact""#)).unwrap();
    assert_ne!(a.track_keys[0], b.track_keys[0], "the bus follows its feeder");
    let dir = folder("bus");
    let cache = TrackCache::at(dir.clone());
    render_with(&a, Some(&cache)).unwrap();
    assert_eq!(bits(&render_with(&a, None).unwrap().channels().unwrap()), bits(&render_with(&a, Some(&cache)).unwrap().channels().unwrap()));
    // A media clip's PCM file: rewriting it changes the key.
    let pcm = dir.join("take.f32");
    std::fs::write(&pcm, vec![0u8; 800]).unwrap();
    let path = pcm.to_string_lossy().replace('\\', "\\\\");
    let media = SCHEDULE.replace(r#"{"kind":"sfx","preset":"riser","material":null,"duration":0.4,"volume":0.9,"pitch":0,"panFrom":-0.8,"panTo":0.8}"#, &format!(r#"{{"kind":"media","pcm":{{"file":"{path}","channels":2,"frames":100}}}}"#));
    let k1 = Schedule::parse(&media).unwrap().track_keys[1].clone();
    std::fs::write(&pcm, vec![1u8; 804]).unwrap();
    assert_ne!(k1, Schedule::parse(&media).unwrap().track_keys[1]);
    let _ = std::fs::remove_dir_all(dir);
}

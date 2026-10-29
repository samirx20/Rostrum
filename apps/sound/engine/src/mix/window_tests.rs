use crate::fx::master::window::Decisions;
use crate::mix::render::render_with;
use crate::mix::schedule::Schedule;

/// 12 s at 44.1 kHz: a pad note every half second (clip reverb, the track's reverb send), the master's hall, a glue and a
/// loudness target the limiter cannot reach without holding the mix down.
fn song() -> Schedule {
    let sr = 44100usize;
    let notes: Vec<String> = (0..24)
        .map(|k| format!(r#"{{"kind":"note","instrument":"warmPad","freqs":[{}],"startIdx":{},"duration":0.45,"velocity":{},"pan":0}}"#, [220.0, 261.63, 329.63, 392.0][k % 4], k * sr / 2, 0.5 + 0.02 * k as f64))
        .collect();
    Schedule::parse(&format!(
        r#"{{"version":7,"layout":"stereo","sampleRate":{sr},"totalSamples":{},"tailSamples":0,"fadeInSamples":0,"fadeOutSamples":0,"masterVolume":1,"masterReverb":"hall","trackReverbSpace":"hall","effects":[],"master":{{"loudness":-14,"truePeak":-1,"glue":0.4,"maxLimit":2}},"timeWarps":[],"tracks":[
        {{"name":"pad","tone":"warm","volume":1,"pan":0,"reverb":0.4,"mix":true,"ducks":[],"effects":[],"automation":{{}},"into":null,"surround":null,"bed":false,"clips":[
        {{"startSample":0,"samples":{},"duration":12,"content":{{"kind":"score","voices":[{}]}},"rate":null,"reverse":null,"glitch":null,"filterSweep":null,"tone":"neutral","fadeIn":0,"fadeOut":0,"volume":1,"pan":0,"reverb":0.3,"repair":[],"effects":[],"matchEq":null}}]}}]}}"#,
        12 * sr,
        12 * sr,
        notes.join(",")
    ))
    .unwrap()
}

#[test]
fn a_stretch_with_the_songs_decisions_is_that_stretch_of_the_whole_render() {
    // The whole song, then 7-9.5 s on its own (its track rendered only around it, the master on it with a lead-in):
    // the same samples. Guards the heard stretch (render_audition) against drifting from what render_mix writes.
    let whole = render_with(&song(), None).unwrap();
    let full = whole.channels().unwrap();
    let mut s = song();
    let (a, b) = (7 * 44100, 9 * 44100 + 22050);
    s.range = Some((a, b));
    s.master_as = Some(Decisions { program: whole.master.program, gain_db: whole.master.gain_db, held_db: whole.master.held_db });
    s.in_song = true;
    assert!(crate::mix::window::master_span(&s).is_some(), "the stretch renders on its own");
    let part = render_with(&s, None).unwrap();
    let got = part.channels().unwrap();
    assert_eq!(got[0].len(), b - a);
    let worst = (0..2).flat_map(|c| (0..b - a).map(move |i| (c, i))).map(|(c, i)| (got[c][i] - full[c][a + i]).abs()).fold(0.0f32, f32::max);
    assert!(worst < 1e-6, "the stretch differs from the whole render by {worst}");
    assert!(whole.master.held_db > 0.0 || whole.master.gain_db.abs() > 0.1, "the master did act: {:?}", whole.master);
}

#[test]
fn a_stretch_heard_in_the_song_without_decisions_is_cut_from_the_whole_render() {
    let whole = render_with(&song(), None).unwrap();
    let mut s = song();
    let (a, b) = (3 * 44100, 5 * 44100);
    s.range = Some((a, b));
    s.in_song = true;
    let part = render_with(&s, None).unwrap();
    assert_eq!(part.channels().unwrap()[1], whole.channels().unwrap()[1][a..b].to_vec());
    assert_eq!(part.master.gain_db, whole.master.gain_db, "the song's decisions are reported");
}

.pragma library
// The tempo map on the screen: beats to seconds, the same maths as rostrum_sound/doc/tempo.py (its one JS port: keep
// the two the same). `map` is backend.song.tempoMap, tempo.segments: [start beat, bpm, start seconds, bpm at its end,
// end beat] per stretch, the last ending at Infinity. A ramp glides evenly per beat: seconds = 60/k·ln(1 + k·beats/bpm0).

function _slope(s) { return s[3] === s[1] || s[4] === Infinity ? 0 : (s[3] - s[1]) / (s[4] - s[0]) }

// The stretch `beat` is in (before the song's start: the first), as tempo._by_beat
function _seg(map, beat) {
    var lo = 0, hi = map.length
    while (lo < hi) { var m = (lo + hi) >> 1; if (map[m][0] <= beat + 1e-12) lo = m + 1; else hi = m }
    return map[Math.max(0, lo - 1)]
}

function seconds(map, beat) {
    var s = _seg(map, beat), k = _slope(s)
    return s[2] + (k === 0 ? (beat - s[0]) * 60.0 / s[1] : 60.0 / k * Math.log1p(k * (beat - s[0]) / s[1]))
}

// The map as a short text: two maps that read the same are the same (each read of backend.song is a new object)
function key(map) { return JSON.stringify(map) }

// Where `t` seconds falls among sorted times `ts` (song.beats or song.bars): how many lie before it, plus the
// fraction of the way to the next (song.beats: the beat number from 0). Past the last: on at `step` seconds apart.
function along(ts, t, step) {
    var n = ts.length
    if (!n) return t / step
    var lo = 0, hi = n
    while (lo < hi) { var m = (lo + hi) >> 1; if (ts[m] <= t + 1e-9) lo = m + 1; else hi = m }
    var i = lo - 1
    if (i < 0) return (t - ts[0]) / step
    var gap = i + 1 < n ? ts[i + 1] - ts[i] : step
    return i + (t - ts[i]) / gap
}

// A drag chip's place: "bar 9" on a bar line, else "bar 9.3" (its beat in the bar), as the ruler names them
function barName(song, t) {
    var bars = song.bars || [], barSec = song.spb * song.barBeats, b = Math.floor(along(bars, t, barSec) + 1e-6)
    var last = bars.length - 1, start = b <= last ? bars[Math.max(0, b)] : (last >= 0 ? bars[last] : 0) + (b - Math.max(0, last)) * barSec
    var beat = along(song.beats || [], t, song.spb) - along(song.beats || [], start, song.spb)
    var whole = Math.round(beat * 4) / 4
    return "bar " + (b + 1) + (Math.abs(whole) < 1e-6 ? "" : "." + (Math.floor(whole + 1e-6) + 1))
}

// A drag chip's amount in beats: "−1 bar 2" (a bar and two beats earlier), "+2 beats", "+0.5 beat", "0"
function amount(beats, perBar) {
    var d = Math.round(beats * 100) / 100
    if (Math.abs(d) < 1e-6) return "0"
    var a = Math.abs(d), bars = Math.floor(a / perBar + 1e-6), rest = Math.round((a - bars * perBar) * 100) / 100
    var s = d < 0 ? "−" : "+"
    if (!bars) return s + rest + (rest <= 1 ? " beat" : " beats")
    return s + bars + (bars === 1 ? " bar" : " bars") + (rest > 0 ? " " + rest : "")
}

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

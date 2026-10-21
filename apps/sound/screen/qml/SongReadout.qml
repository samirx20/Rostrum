import QtQuick
import RostrumKit

// The playhead as text: bar.beat first, seconds after ("5.1  9.60 s"), digits all one width; the tempo and key
// playing there when the song has a key or changes tempo ("♩ 132  D minor"); then the sound's state when there is
// one to tell (rendering, no output here, a failed render: red). Bars and beats follow the tempo map (song.beats).
Row {
    id: ro
    spacing: Theme.gap
    readonly property var song: backend.song
    readonly property int bpb: song.beatsPerBar
    function lastAt(list, t, timeOf) {   // the last entry at or before t (lists are in time order), -1 when none
        var lo = 0, hi = list.length - 1, best = -1
        while (lo <= hi) {
            var mid = (lo + hi) >> 1
            if (timeOf(list[mid]) <= t + 1e-6) { best = mid; lo = mid + 1 } else hi = mid - 1
        }
        return best
    }
    readonly property int beat: Math.max(0, lastAt(song.beats, backend.time, b => b))
    readonly property int tempoAt: Math.max(0, lastAt(song.tempos, backend.time, c => c.t))
    readonly property int keyAt: lastAt(song.keys, backend.time, c => c.t)
    Item { width: 2; height: 1 }
    Text { text: (Math.floor(ro.beat / ro.bpb) + 1) + "." + (ro.beat % ro.bpb + 1)
           width: 36; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
           anchors.verticalCenter: parent.verticalCenter }
    Text { text: backend.time.toFixed(2) + " s"; width: 52; color: Theme.fg3; font.family: uiFont
           font.pixelSize: Theme.label; font.features: { "tnum": 1 }; anchors.verticalCenter: parent.verticalCenter }
    Text { visible: ro.song.tempos.length > 1 || ro.song.keys.length > 0; anchors.verticalCenter: parent.verticalCenter
           text: "♩ " + Math.round(ro.song.tempos[ro.tempoAt].bpm) + (ro.keyAt >= 0 ? "  " + ro.song.keys[ro.keyAt].key : "")
           color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 } }
    Text { visible: text !== ""; text: backend.soundState; anchors.verticalCenter: parent.verticalCenter
           color: /^Render failed/.test(text) ? Theme.danger : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
}

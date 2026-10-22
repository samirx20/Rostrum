import QtQuick
import RostrumKit

// The arrangement header's position and song: where the playhead is ("5.3 · 0:09.60": bar.beat, then the time; digits
// all one width) and what plays there — tempo, beats per bar, key — as fields: their one home (drag or type the tempo,
// pick the beats and key; nothing has to be selected first). Then the
// sound's state when there is one to tell (rendering, no output here, a failed render: red). Bars and beats follow
// the tempo map (song.beats). `compact` (a small window, §2.5): bar.beat only (the time on hover) and the key short.
Row {
    id: ro
    property bool compact: false
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
    function clock(t) {
        var m = Math.floor(t / 60), s = t - 60 * m
        return m + ":" + (s < 10 ? "0" : "") + s.toFixed(2)
    }
    readonly property int beat: Math.max(0, lastAt(song.beats, backend.time, b => b))
    readonly property int tempoAt: Math.max(0, lastAt(song.tempos, backend.time, c => c.t))
    readonly property int keyAt: lastAt(song.keys, backend.time, c => c.t)
    readonly property string key: keyAt >= 0 ? song.keys[keyAt].key : ""
    readonly property string tonic: key.split(" ")[0]
    readonly property string mode: key.split(" ")[1] || "major"

    Text {
        id: place
        text: (Math.floor(ro.beat / ro.bpb) + 1) + "." + (ro.beat % ro.bpb + 1) + (ro.compact ? "" : "  ·  " + ro.clock(backend.time))
        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
        anchors.verticalCenter: parent.verticalCenter
        HoverHandler { id: placeHover }
        HoverTip { text: ro.compact ? ro.clock(backend.time) : ""; hovered: placeHover.hovered }
    }
    Row {   // tempo, beats per bar and key: their one home. Each edits what plays at the playhead (song_panel.py)
        anchors.verticalCenter: parent.verticalCenter; spacing: Theme.grid
        readonly property int tempoNow: Math.round(ro.song.tempos[ro.tempoAt].bpm)
        NumberField {   // the unit inside the field: one control, "100 bpm"
            width: 76; value: parent.tempoNow; from: 20; to: 400; step: 1; unit: "bpm"
            onEdited: (v) => songPanel.setTempo(v)
            onScrubStarted: songPanel.beginTempo()
            onScrubbed: (v) => songPanel.scrubTempo(v)
            onScrubEnded: songPanel.endScrub()
            HoverTip { text: "Tempo (beats a minute) here: drag or type"; hovered: parent.hovered }
        }
        ChoiceField {
            width: 56; current: ro.bpb
            options: [2, 3, 4, 5, 6, 7, 8, 9, 12].map(n => ({ value: n, label: n + "/4" }))
            onPicked: (v) => songPanel.setValue("beatsPerBar", v)
            HoverTip { text: "Beats in a bar"; hovered: parent.hovered && !parent.opened }
        }
        ChoiceField {   // the key playing here: tonic (or "No key" until one is chosen), then the mode
            width: ro.key !== "" ? 56 : 84; current: ro.tonic
            options: (ro.key !== "" ? [] : [{ value: "", label: songPanel.noKey }]).concat(
                ["C", "C#", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"])
            onPicked: (v) => { if (v !== "") songPanel.setKey(v, ro.mode) }
        }
        ChoiceField {
            visible: ro.key !== ""; width: ro.compact ? 64 : 92; current: ro.mode
            options: ["major", "minor", "dorian", "phrygian", "lydian", "mixolydian", "locrian"]
                .map(m => ({ value: m, label: ro.compact ? m.charAt(0).toUpperCase() + m.slice(1, 3) : m.charAt(0).toUpperCase() + m.slice(1) }))
            onPicked: (v) => songPanel.setKey(ro.tonic, v)
        }
    }
    Text { visible: text !== ""; text: backend.soundState; anchors.verticalCenter: parent.verticalCenter
           color: /^Render failed/.test(text) ? Theme.danger : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
}

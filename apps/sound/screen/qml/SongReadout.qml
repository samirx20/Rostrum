import QtQuick
import RostrumKit

// The top bar's position and song: where the playhead is ("5.3 · 0:09.60": bar.beat, then the time; digits all one
// width) and what plays there ("♩ 100 · 4/4 · C major"; click: the tempo / key popover, SongEditor.qml); then the
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
    function shortKey(k) {   // "C minor" -> "Cm", "D major" -> "D", a mode -> its first three letters
        var p = k.split(" ")
        return p[0] + (p[1] === "minor" ? "m" : p[1] === "major" || !p[1] ? "" : " " + p[1].slice(0, 3))
    }
    readonly property int beat: Math.max(0, lastAt(song.beats, backend.time, b => b))
    readonly property int tempoAt: Math.max(0, lastAt(song.tempos, backend.time, c => c.t))
    readonly property int keyAt: lastAt(song.keys, backend.time, c => c.t)
    readonly property string key: keyAt >= 0 ? song.keys[keyAt].key : ""
    function open() { editor.open() }

    Text {
        id: place
        text: (Math.floor(ro.beat / ro.bpb) + 1) + "." + (ro.beat % ro.bpb + 1) + (ro.compact ? "" : "  ·  " + ro.clock(backend.time))
        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
        anchors.verticalCenter: parent.verticalCenter
        HoverHandler { id: placeHover }
        HoverTip { text: ro.compact ? ro.clock(backend.time) : ""; hovered: placeHover.hovered }
    }
    Text {
        id: tempoText; anchors.verticalCenter: parent.verticalCenter   // click: the tempo / key popover
        text: "♩ " + Math.round(ro.song.tempos[ro.tempoAt].bpm) + "  ·  " + ro.bpb + "/4"
              + (ro.key ? "  ·  " + (ro.compact ? ro.shortKey(ro.key) : ro.key) : "")
        color: tempoArea.containsMouse || editor.opened ? Theme.fg : Theme.fg2
        font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
        MouseArea { id: tempoArea; anchors { fill: parent; margins: -4 } hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor; onClicked: editor.opened ? editor.close() : editor.open() }
        SongEditor { id: editor; y: tempoText.height + 10 }
    }
    Text { visible: text !== ""; text: backend.soundState; anchors.verticalCenter: parent.verticalCenter
           color: /^Render failed/.test(text) ? Theme.danger : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
}

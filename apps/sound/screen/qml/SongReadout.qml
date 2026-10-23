import QtQuick
import RostrumKit

// The arrangement header's position and song: where the playhead is ("5.3  0:09.60": bars.beats, then the time, from the one formatter, musical.py via
// backend.positionText(time); digits all one width) and what plays there — tempo, beats per bar, key — as fields: the quick way to them (drag or type the tempo,
// pick the beats and key; nothing has to be selected first; every change is listed in the song panel, SongList.qml). Then the
// sound's state when there is one to tell (rendering, no output here, a failed render: red). `compact` (a small window, §2.5): bar.beat only (the time on hover) and the key short.
Row {
    id: ro
    property bool compact: false
    property bool tight: false                        // a squeezed strip (a drawer open on a small window): the key fields step aside
    spacing: Theme.gap
    readonly property var song: backend.song
    readonly property string meter: { backend.time; song; return songPanel.meterHere() }   // what plays here
    function lastAt(list, t, timeOf) {   // the last entry at or before t (lists are in time order), -1 when none
        var lo = 0, hi = list.length - 1, best = -1
        while (lo <= hi) {
            var mid = (lo + hi) >> 1
            if (timeOf(list[mid]) <= t + 1e-6) { best = mid; lo = mid + 1 } else hi = mid - 1
        }
        return best
    }
    readonly property int tempoAt: Math.max(0, lastAt(song.tempos, backend.time, c => c.t))
    readonly property int keyAt: lastAt(song.keys, backend.time, c => c.t)
    readonly property string key: keyAt >= 0 ? song.keys[keyAt].key : ""
    readonly property string tonic: key.split(" ")[0]
    readonly property string mode: key.split(" ")[1] || "major"

    FieldFrame {   // type "5.3" (bars.beats) or "9.6 s" and Enter to jump there; a refusal says why
        id: place
        readonly property string full: backend.positionText(backend.time, ro.song)
        readonly property var parts: full.split("  ")     // bars.beats, then the clock (musical.py)
        text: ro.compact ? parts[0] : full
        editable: true
        width: Math.ceil(measure.width) + 2 * Theme.gap + 4
        anchors.verticalCenter: parent.verticalCenter
        TextMetrics { id: measure; font: place.input.font; text: ro.compact ? "999.9" : "999.9  0:00.00" }
        onCommitted: (t) => { const why = backend.jumpTo(t); if (why !== "") place.problem = why }
        HoverTip { text: place.problem === "" ? (ro.compact ? place.parts[1] + " · type a bar.beat or seconds to jump" : "Type a bar.beat (5.3) or seconds (9.6 s) to jump") : ""
                   hovered: place.hovered && !place.active }
    }
    Row {   // tempo, time signature and key: the tempo and key edit what plays at the playhead (song_panel.py)
        anchors.verticalCenter: parent.verticalCenter; spacing: Theme.grid
        readonly property int tempoNow: Math.round(ro.song.tempos[ro.tempoAt].bpm)
        NumberField {   // the unit inside the field: one control, "100 bpm"
            width: 76; label: "Tempo"; value: parent.tempoNow; from: 20; to: 400; step: 1; unit: "bpm"
            onEdited: (v) => songPanel.setTempo(v)
            onScrubStarted: songPanel.beginTempo()
            onScrubbed: (v) => songPanel.scrubTempo(v)
            onScrubEnded: songPanel.endScrub()
            HoverTip { text: "Tempo (beats a minute) here: drag or type"; hovered: parent.hovered }
        }
        ChoiceField {
            width: 56; current: ro.meter
            options: songPanel.meters.map(m => ({ value: m, label: m }))
            onPicked: (v) => songPanel.setMeter(v)
            HoverTip { text: "Time signature: beats in a bar / what a beat is"; hovered: parent.hovered && !parent.opened }
        }
        ChoiceField {   // the key playing here: tonic (or "No key" until one is chosen), then the mode
            visible: !ro.tight; width: ro.key !== "" ? 56 : 84; current: ro.tonic
            options: (ro.key !== "" ? [] : [{ value: "", label: songPanel.noKey }]).concat(songPanel.tonics)
            onPicked: (v) => { if (v !== "") songPanel.setKey(v, ro.mode) }
        }
        ChoiceField {
            visible: ro.key !== "" && !ro.tight; width: ro.compact ? 64 : 92; current: ro.mode
            options: ["major", "minor", "dorian", "phrygian", "lydian", "mixolydian", "locrian"]
                .map(m => ({ value: m, label: ro.compact ? m.charAt(0).toUpperCase() + m.slice(1, 3) : m.charAt(0).toUpperCase() + m.slice(1) }))
            onPicked: (v) => songPanel.setKey(ro.tonic, v)
        }
    }
    Text { visible: text !== ""; text: backend.soundState; anchors.verticalCenter: parent.verticalCenter
           color: /^Render failed/.test(text) ? Theme.danger : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
}

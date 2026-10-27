import QtQuick
import RostrumKit

// The arrangement header's position and song: where the playhead is ("5.3  0:09.60": bars.beats, then the time, from the one formatter, musical.py via
// backend.positionText(time); digits all one width) and what plays there — tempo, beats per bar, key — as fields: the quick way to them (drag or type the tempo,
// pick the beats and key; nothing has to be selected first; every change is listed in the song panel, SongList.qml). Then the
// sound's state when there is one to tell (rendering, no output here, a failed render: red). `compact` (a small window, §2.5): bar.beat only (the time on hover) and the key short.
Row {
    id: ro
    property bool compact: false
    property real room: -1                            // the strip's width left of the right-hand buttons: the state text steps aside (elides) to fit
    property bool tight: false                        // a squeezed strip (a drawer open on a small window): the key fields step aside
    // The room decides too, not only the window's width: with the Library open the strip is short at any window size,
    // and the key's Minor box ran under the Picture button (critic r9 + r10). Full while everything fits, then short
    // (bar.beat only, "Min"), then the key fields step aside.
    function keyW(short) { return key === "" ? 84 : short ? 76 : 124 }
    function needs(short) { return (short ? measureShort.width : measureFull.width) + 2 * Theme.gap + 4 + Theme.grid
                                   + 76 + 56 + keyW(short) + 2 * Theme.grid }
    readonly property bool isCompact: compact || (room >= 0 && room < needs(false))
    readonly property bool isTight: tight || (room >= 0 && room < needs(true))
    TextMetrics { id: measureFull; font: place.input.font; text: "999.9  0:00.00" }
    TextMetrics { id: measureShort; font: place.input.font; text: "999.9" }
    spacing: Theme.gap
    readonly property var song: backend.song
    function ask() { place.input.forceActiveFocus(); place.input.selectAll() }       // Alt+Shift+J (the kit's go_to_time)
    function openKey() { keyPick.open() }      // (the scripted `key-open` step)
    function askBar() { goBar.problem = ""; goBar.input.text = ""; barPop.open() }      // Ctrl+B, Ctrl+K "Go to bar…"
    Component.onCompleted: { const w = Window.window; if (w && w.timeBox !== undefined) w.timeBox = ro }
    Component.onDestruction: { const w = Window.window; if (w && w.timeBox === ro) w.timeBox = null }
    readonly property string meter: { backend.time; song; return songPanel.meterHere() }   // what plays here
    function lastAt(list, t, timeOf) {   // the last entry at or before t (lists are in time order), -1 when none
        var lo = 0, hi = list.length - 1, best = -1
        while (lo <= hi) {
            var mid = (lo + hi) >> 1
            if (timeOf(list[mid]) <= t + 1e-6) { best = mid; lo = mid + 1 } else hi = mid - 1
        }
        return best
    }
    // the entry in force here, read from the list in the same step (an index kept apart went stale when an undo shrank the list)
    function here(list) { const i = lastAt(list, backend.time, c => c.t); return i >= 0 ? list[i] : null }
    readonly property var tempoHere: here(song.tempos) || song.tempos[0] || null
    readonly property var keyHere: here(song.keys)
    readonly property string key: keyHere ? keyHere.key : ""

    FieldFrame {   // type "5.3" (bars.beats) or "9.6 s" and Enter to jump there; a refusal says why
        id: place
        objectName: "songPosition"
        readonly property string full: backend.positionText(backend.time, ro.song.length)   // (the length: a dependency on the song, not the whole map sent)
        readonly property var parts: full.split("  ")     // bars.beats, then the clock (musical.py)
        text: ro.isCompact ? parts[0] : full
        editable: true
        width: Math.ceil(ro.isCompact ? measureShort.width : measureFull.width) + 2 * Theme.gap + 4
        anchors.verticalCenter: parent.verticalCenter
                onCommitted: (t) => { const why = backend.jumpTo(t); if (why !== "") place.problem = why }
        // Go to bar (Ctrl+B): a small typed field under the position; Return goes there (the playhead, and the
        // arrangement and the roll turn to show it), Esc closes. A refusal stays in the field to be put right.
        SmallPopup {
            id: barPop
            objectName: "goToBar"
            y: place.height + 2
            padding: Theme.grid; margins: Theme.gap
            focus: true
            background: Rectangle { color: Theme.raised; radius: Theme.radiusCtl; border.color: Theme.popupEdge }
            onOpened: goBar.input.forceActiveFocus()
            contentItem: Row {
                spacing: Theme.gap
                Text { anchors.verticalCenter: parent.verticalCenter; text: "Go to bar"; color: Theme.fg2
                       font.family: uiFont; font.pixelSize: Theme.body }
                FieldFrame {
                    id: goBar
                    objectName: "goToBarField"
                    width: 120; editable: true; keepOnRefusal: true
                    placeholder: "24 or 1:02.5"
                    onEntered: { const why = backend.goToBar(goBar.input.text); if (why === "") barPop.close(); else goBar.problem = why }
                    onEscaped: barPop.close()
                }
            }
        }
        HoverTip { text: place.problem === "" ? (ro.isCompact ? place.parts[1] + " · type a bar.beat or seconds to jump" : "Type a bar.beat (5.3) or seconds (9.6 s) to jump; Alt+Shift+J") : ""
                   hovered: place.hovered && !place.active }
    }
    Row {   // tempo, time signature and key: the tempo and key edit what plays at the playhead (song_panel.py)
        anchors.verticalCenter: parent.verticalCenter; spacing: Theme.grid
        readonly property real tempoNow: ro.tempoHere ? ro.tempoHere.bpm : 120
        NumberField {   // the unit inside the field: one control, "100 bpm"; drags in whole bpm, keeps a typed 99.5
            objectName: "songTempo"
            width: 76; label: "Tempo"; value: parent.tempoNow; from: 20; to: 400; step: 1; typeStep: 0.01; unit: "bpm"
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
        KeyPicker {   // the key playing here, tonic and mode in one click ("No key" until one is chosen)
            id: keyPick
            objectName: "songKey"
            visible: !ro.isTight; width: ro.keyW(ro.isCompact); key: ro.key; compact: ro.isCompact
            onPicked: (t, m) => songPanel.setKey(t, m)
        }
    }
    // "Updating the sound…" / "No sound output…"; a failed render is not repeated here: the Problems chip keeps it
    Text { visible: text !== "" && (ro.room < 0 || width > 0); anchors.verticalCenter: parent.verticalCenter
           text: /^Can't make the sound/.test(backend.soundState) ? "" : backend.soundState
           elide: Text.ElideRight; width: ro.room < 0 ? implicitWidth : Math.max(0, Math.min(implicitWidth, ro.room - x))
           color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
           MouseArea { id: stateHover; anchors.fill: parent; hoverEnabled: true }
           HoverTip { text: parent.truncated ? backend.soundState : ""; hovered: stateHover.containsMouse } }
}

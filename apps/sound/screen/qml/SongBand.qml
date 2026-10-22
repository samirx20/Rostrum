import QtQuick
import RostrumKit

// The song's tempo changes and key changes on the ruler, each a small flag at its time ("♩ 96", "D minor").
// Click selects it (the inspector edits it; Delete removes it); drag moves it (one gesture = one undo step; a tempo
// change on its beat, a quarter beat grid, Ctrl = free). The key at the start is not flagged (the header strip and the song view say it). Absent while the song has none. Clicks are taken here in
// one place, as in MarkerBand.
Item {
    id: band
    property var ruler
    readonly property var song: backend.song
    readonly property var marks: song.tempoMarks.map(c => ({ id: c.id, t: c.t, text: "♩ " + Math.round(c.bpm), tempo: true }))
                                 .concat(song.keys.filter(k => k.t > 0.001).map(k => ({ id: k.id, t: k.t, text: k.key, tempo: false })))
    clip: true
    visible: marks.length > 0
    function flagWidth(text) { return metrics.advanceWidth(text) + 14 }
    function markAt(x) {
        var best = ""
        for (var i = 0; i < marks.length; i++) {
            var mx = ruler.xOf(marks[i].t)
            if (x >= mx - 4 && x <= mx + flagWidth(marks[i].text)) best = marks[i].id
        }
        return best
    }
    FontMetrics { id: metrics; font.family: uiFont; font.pixelSize: Theme.label; font.features: { "tnum": 1 } }

    Repeater {
        model: band.marks
        delegate: Rectangle {
            required property var modelData
            readonly property bool on: modelData.id === backend.selected
            x: Math.round(band.ruler.xOf(modelData.t)); y: 1
            visible: x + width > 0 && x < band.width
            width: band.flagWidth(modelData.text) - 2; height: band.height - 2
            radius: 3; color: on ? Theme.accent : Theme.raised
            Rectangle { width: 2; height: parent.height; radius: 1; color: parent.on ? Theme.fg : modelData.tempo ? Theme.fg3 : Theme.fg4 }
            Text { x: 7; anchors.verticalCenter: parent.verticalCenter; text: modelData.text
                   color: parent.on ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                   font.features: { "tnum": 1 } }
        }
    }
    MouseArea {
        anchors.fill: parent
        preventStealing: true
        property real x0: 0
        property bool dragging: false
        hoverEnabled: true
        cursorShape: band.markAt(mouseX) !== "" ? Qt.SizeHorCursor : Qt.ArrowCursor
        onPressed: (m) => {
            var id = band.markAt(m.x)
            dragging = id !== "" && backend.beginDrag(id)
            x0 = m.x
            if (!dragging) m.accepted = false
        }
        onPositionChanged: (m) => { if (dragging && pressed)
            backend.dragBy((m.x - x0) / band.ruler.perSec, 0, (m.modifiers & Qt.ControlModifier) !== 0) }
        onWheel: (w) => backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                          (w.modifiers & Qt.ShiftModifier) !== 0, w.x / band.width, false)
        onReleased: { if (dragging) backend.endDrag(); dragging = false }
        onCanceled: { if (dragging) backend.cancelDrag(); dragging = false }
    }
}

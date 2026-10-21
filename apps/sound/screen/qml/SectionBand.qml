import QtQuick
import RostrumKit

// The song's sections (intro, verse, drop) under the markers: each a bar from its start to its end with its name.
// Click selects the section (the inspector edits its name, start and end); drag moves it and everything that
// starts inside it (one `section.move` per step, the whole drag one undo step; a quarter beat grid, Shift = free).
// Drag the left or right edge: that edge only moves (`section.set`, one undo step), the section's contents stay.
// Absent when the song has no sections. The clicks are taken here in one place, as in MarkerBand.
Item {
    id: band
    property var ruler
    readonly property var sections: backend.song.sections
    clip: true
    visible: sections.length > 0
    function sectionAt(x) {
        var best = ""
        for (var i = 0; i < sections.length; i++) {
            var s = sections[i]
            if (x >= ruler.xOf(s.t) && x <= ruler.xOf(s.end)) best = s.id
        }
        return best
    }

    function edgeAt(id, x) {   // "at" / "end" when x is on that edge of section `id` (a few px; the middle stays a move)
        var s = sections.find(s => s.id === id)
        if (!s) return ""
        var l = ruler.xOf(s.t), r = ruler.xOf(s.end), grip = Math.min(6, (r - l) / 3)
        return x <= l + grip ? "at" : x >= r - grip ? "end" : ""
    }

    Repeater {
        model: band.sections
        delegate: Rectangle {
            required property var modelData
            readonly property bool on: modelData.id === backend.selected
            x: Math.round(band.ruler.xOf(modelData.t)); y: 1
            width: Math.max(2, Math.round(band.ruler.wOf(modelData.end - modelData.t)) - 1); height: band.height - 2
            visible: x + width > 0 && x < band.width
            radius: 3; color: on ? Theme.accent : Theme.raised; border.width: 1; border.color: on ? Theme.fg3 : Theme.line
            Text { x: 6; width: parent.width - 10; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
                   text: modelData.name; color: parent.on ? Theme.fg : Theme.fg2
                   font.family: uiFont; font.pixelSize: Theme.label }
        }
    }
    MouseArea {
        anchors.fill: parent
        preventStealing: true
        property real x0: 0
        property bool dragging: false
        hoverEnabled: true
        cursorShape: { var id = band.sectionAt(mouseX), e = band.edgeAt(id, mouseX)
                       return e !== "" ? Qt.SplitHCursor : id !== "" ? Qt.SizeHorCursor : Qt.ArrowCursor }
        onPressed: (m) => {
            var id = band.sectionAt(m.x), e = band.edgeAt(id, m.x)
            dragging = id !== "" && (e !== "" ? backend.beginEdge(id, e) : backend.beginDrag(id))
            x0 = m.x
            if (!dragging) m.accepted = false
        }
        onPositionChanged: (m) => { if (dragging && pressed)
            backend.dragBy((m.x - x0) / band.ruler.perSec, 0, (m.modifiers & Qt.ShiftModifier) !== 0) }
        onWheel: (w) => backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                          (w.modifiers & Qt.ShiftModifier) !== 0, w.x / band.width, false)
        onReleased: { if (dragging) backend.endDrag(); dragging = false }
        onCanceled: { if (dragging) backend.cancelDrag(); dragging = false }
    }
}

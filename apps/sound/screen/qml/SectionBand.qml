import QtQuick
import RostrumKit
import "Picks.js" as Picks
import "Pointers.js" as Pointers
import "Tempo.js" as Tempo

// The song's sections (intro, verse, drop) under the markers: each a bar from its start to its end with its name.
// Click selects the section (the inspector edits its name, start and end); double-click or F2 renames it in place.
// Drag moves it and everything that started inside it at the press (markers stay) as one picture (PLAN S2): the band,
// its outline and a picture of the lanes' notes under it (`shift`, drawn by the Timeline) ride the pointer every frame,
// nothing in the song changes until the release, which is one `section.move` by the whole amount, one undo step. It
// lands on the nearest beat (Ctrl: free); the chip names where ("bar 9.3"). Esc while dragging puts it back.
// Drag the left or right edge: that edge only moves (`section.set` on release, one undo step), its contents stay.
// Absent when the song has no sections. The clicks are taken here in one place, as in MarkerBand.
Item {
    id: band
    property var ruler
    readonly property var sections: ruler.song.sections     // the ruler's song (one read, shared)
    clip: true
    visible: sections.length > 0
    // the drag in flight: the section, which part ("" = all of it, "at" / "end" = an edge), how far its picture has
    // moved (px, landed on a beat) and the lanes' stretch it carries at the press ({x0, x1}: the Timeline draws them)
    property string dragId: ""
    property string dragEdge: ""
    property real dx: 0
    property var shift: null
    readonly property bool dragging: dragId !== ""
    function landed(t, free) {   // where a dragged time lands: the nearest beat (the song's beat lines), Ctrl: free
        if (free) return Math.max(0, t)
        var b = ruler.song.beats || [], i = Math.round(Tempo.along(b, t, ruler.song.spb))
        return i < 0 ? 0 : i < b.length ? b[i] : (b.length ? b[b.length - 1] : 0) + (i - b.length + 1) * ruler.song.spb
    }
    function finish(keep) {      // the release (keep) or Esc: the one write, or none
        if (!dragging) return
        var s = sections.find(s => s.id === dragId), dt = dx / ruler.perSec
        if (keep && s && Math.abs(dx) >= 0.5) backend.dragBy(dt, 0, true)
        if (keep) backend.endDrag(); else backend.cancelDrag()     // (a click: nothing moved, nothing written)
        dragId = ""; dragEdge = ""; dx = 0; shift = null
        if (press.focusWas) press.focusWas.forceActiveFocus(); press.focusWas = null
    }
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

    Repeater {   // by count: a tempo drag moves the sections without making them again (each read is the held list)
        model: band.sections.length
        delegate: Rectangle {
            required property int index
            readonly property var modelData: band.sections[index]
            readonly property bool on: !!Picks.heads(backend, backend.pickStamp)[modelData.id]
            readonly property bool naming: backend.renaming === modelData.id
            readonly property bool held: band.dragId === modelData.id      // its picture rides the pointer
            readonly property real x0: band.ruler.xOf(modelData.t) + (held && band.dragEdge !== "end" ? band.dx : 0)
            readonly property real x1: band.ruler.xOf(modelData.end) + (held && band.dragEdge !== "at" ? band.dx : 0)
            x: Math.round(x0); y: 1; z: held ? 1 : 0
            width: Math.max(2, Math.round(x1 - x0) - 1); height: band.height - 2
            visible: x + width > 0 && x < band.width
            radius: 3; color: on ? Theme.accent : Theme.raised; border.width: 1
            border.color: held ? Theme.fg : on ? Theme.fg3 : Theme.line
            NameLabel { x: 6; width: parent.width - 10; anchors.verticalCenter: parent.verticalCenter
                        text: modelData.name; color: parent.on ? Theme.fg : Theme.fg2; visible: !parent.naming
                        font.pixelSize: Theme.label }
            NameBox {   // the name field, in place (Enter keeps, Esc cancels)
                objectName: "sectionNameBox"
                visible: parent.naming; x: 6; width: Math.max(60, parent.width - 10); anchors.verticalCenter: parent.verticalCenter
                font.pixelSize: Theme.label; selectionColor: Theme.app
                current: modelData.name; keepOnAway: true
                onDone: (t) => backend.finishRename(modelData.id, t)
                onCancelled: backend.finishRename(modelData.id, "")
                // Space before a letter is typed plays (M then Space: the name it was given stays, critic r12 #14);
                // once something is typed, it is a space in the name
                Keys.onSpacePressed: (e) => { if (text !== current) { e.accepted = false; return }
                                              backend.finishRename(modelData.id, ""); backend.togglePlay() }
            }
        }
    }
    MouseArea {
        id: press
        anchors.fill: parent
        preventStealing: true
        property real x0: 0
        property real t0: 0                  // the dragged time at the press (the start, or the edge held)
        property var focusWas: null          // Esc is the drag's while it runs (before the kit's Step back), then handed back
        hoverEnabled: true
        Keys.onShortcutOverride: (e) => { e.accepted = band.dragging && e.key === Qt.Key_Escape }
        Keys.onEscapePressed: band.finish(false)            // puts it back
        onDoubleClicked: (m) => { var id = band.sectionAt(m.x); if (id !== "") backend.startRename(id) }
        cursorShape: { if (band.dragging) return Pointers.of(band.dragEdge !== "" ? "trim" : "moving")
                       var id = band.sectionAt(mouseX), e = band.edgeAt(id, mouseX)
                       return Pointers.of(e !== "" ? "trim" : id !== "" ? "pick" : "") }
        onPressed: (m) => {
            var id = band.sectionAt(m.x), e = band.edgeAt(id, m.x), s = band.sections.find(s => s.id === id)
            if (!s || !(e !== "" ? backend.beginEdge(id, e) : backend.beginDrag(id))) { m.accepted = false; return }
            x0 = m.x; t0 = e === "end" ? s.end : s.t
            band.dragEdge = e; band.dx = 0
            band.shift = e === "" ? { x0: band.ruler.xOf(s.t), x1: band.ruler.xOf(s.end) } : null
            band.dragId = id
            focusWas = Window.activeFocusItem; forceActiveFocus()
        }
        onPositionChanged: (m) => { if (!band.dragging || !pressed) return
            var to = band.landed(t0 + (m.x - x0) / band.ruler.perSec, (m.modifiers & Qt.ControlModifier) !== 0 || !backend.snapOn)
            if (band.dragEdge !== "") {                     // an edge keeps a quarter beat from the other (song_edit.py)
                var s = band.sections.find(s => s.id === band.dragId), q = band.ruler.song.spb / 4
                to = band.dragEdge === "at" ? Math.max(0, Math.min(to, s.end - q)) : Math.max(to, s.t + q)
            }
            band.dx = (to - t0) * band.ruler.perSec }       // a picture only: nothing is written while it moves
        onWheel: (w) => backend.viewWheel(w.angleDelta.x, w.angleDelta.y, (w.modifiers & Qt.ControlModifier) !== 0,
                                          (w.modifiers & Qt.ShiftModifier) !== 0, w.x / band.width, false)
        onReleased: band.finish(true)
        onCanceled: band.finish(false)
    }
    DragLabel {   // where it lands, as the ruler names it
        parent: band.parent; z: 1000
        at: Qt.point(band.x + press.mouseX, band.y + band.height / 2)
        text: band.dragging && Math.abs(band.dx) >= 0.5
              ? Tempo.barName(band.ruler.song, press.t0 + band.dx / band.ruler.perSec) : ""
    }
}

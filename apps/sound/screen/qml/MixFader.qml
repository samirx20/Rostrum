import QtQuick
import RostrumKit
import "MixFormat.js" as F

// A vertical level fader (gain, taper in MixFormat.js). Press jumps there, dragging follows; press to release is
// one gesture: scrubStarted, scrubbed(gain)…, scrubEnded (the app records it as ONE change). Only the knob is grabbed
// (a stray click on the track does nothing); Alt-click resets to 0 dB, double-click asks to type the value (typeIt),
// and the wheel nudges: 1 dB a notch, Shift 3 dB, Alt 0.1 dB (nudged(gain): one change on its own).
// While the knob is dragged the kit's chip beside it says the level ("−3.0 dB"); Esc puts it back: scrubCancelled
// (the owner drops the gesture, no undo step; the release then does nothing). A control, not a canvas: the pointing
// hand stays.
Item {
    id: f
    property real gain: 1
    readonly property real pos: F.posOf(gain)
    signal scrubStarted()
    signal scrubbed(real gain)
    signal scrubEnded()
    signal scrubCancelled()
    signal reset()
    signal typeIt()
    signal nudged(real gain)
    implicitWidth: 28

    readonly property real travel: height - knob.height
    Rectangle {  // track
        id: track
        anchors.horizontalCenter: parent.horizontalCenter
        y: knob.height / 2; height: f.travel; width: 4; radius: 2
        color: hover.hovered ? Theme.lineHover : Theme.active
        Rectangle { anchors.bottom: parent.bottom; width: parent.width; radius: 2; color: Theme.accent
                    height: parent.height * f.pos }
    }
    Rectangle {  // knob
        id: knob
        anchors.horizontalCenter: parent.horizontalCenter
        y: f.travel * (1 - f.pos)
        width: 22; height: 14; radius: 3; color: "white"
        border.width: drag.pressed ? 2 : 0; border.color: Theme.accent
        Rectangle { anchors.centerIn: parent; width: parent.width - 8; height: 2; color: Theme.fg4 }
    }
    HoverHandler { id: hover }
    WheelHandler {
        acceptedModifiers: Qt.KeyboardModifierMask
        onWheel: (e) => {
            const notch = (e.angleDelta.y || e.angleDelta.x) / 120
            const db = F.dbOf(f.gain) === -Infinity ? F.FLOOR : F.dbOf(f.gain)
            const unit = e.modifiers & Qt.AltModifier ? 0.1 : e.modifiers & Qt.ShiftModifier ? 3 : 1
            f.nudged(F.gainOf(F.posOfDb(db + notch * unit)))
        }
    }
    MouseArea {
        id: drag
        anchors.fill: parent
        preventStealing: true
        cursorShape: Qt.PointingHandCursor
        property real grab: 0           // where in the knob the press landed: the knob follows the pointer, it never jumps
        property bool live: false
        function at(y) { return F.gainOf(1 - Math.max(0, Math.min(1, (y - grab) / f.travel))) }
        property real y0: 0
        property bool holding: false    // the scrub holds Esc (dragEsc) once it has moved 4 px
        function letGo() { if (holding) { holding = false; dragEsc.letEsc() } }
        onPressed: (m) => {
            if (m.modifiers & Qt.AltModifier) { f.reset(); return }
            live = m.y >= knob.y - 3 && m.y <= knob.y + knob.height + 3
            if (!live) return
            grab = m.y - knob.y; y0 = m.y
            f.scrubStarted()
        }
        onPositionChanged: (m) => { if (!live) return
            if (!holding && Math.abs(m.y - y0) >= 4) { holding = true; dragEsc.holdEsc() }
            f.scrubbed(at(m.y)) }
        onReleased: { if (live) f.scrubEnded(); live = false; letGo() }
        onCanceled: { if (live) f.scrubEnded(); live = false; letGo() }
        onDoubleClicked: f.typeIt()
    }
    Connections {   // Esc while the knob is dragged: the level as it was
        target: dragEsc
        function onCancelled() { if (drag.holding) { drag.holding = false; drag.live = false; f.scrubCancelled() } }
    }
    DragLabel {   // the level while dragging, beside the knob (over the window: the strip is narrow)
        parent: f.Window.contentItem || f; z: 1000
        beside: true
        at: { var p = f.mapToItem(parent, knob.x + knob.width, knob.y + knob.height / 2); return Qt.point(p.x, p.y) }
        text: drag.holding ? F.faderText(f.gain) : ""
    }
}

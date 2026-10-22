import QtQuick
import RostrumKit

// The small label while keys or bars are dragged in time (INTERACTION 1.10): the offset in whole frames from where the
// drag began ("+6 f", "−3 f") and, when it snapped, what it caught ("+6 f · drop"). It sits beside the dragged edge or
// key on its layer's row, placed from the drag itself (backend.timeSnap: its time and row, screen2d/time_snap.py), not
// from the pointer, so it is right for the mouse, the steps and agents alike. `at`: that place in the parent's px.
Rectangle {
    id: lbl
    readonly property var ts: backend.timeSnap
    property point at: Qt.point(0, 0)
    visible: ts.text !== ""
    z: 1000
    x: Math.max(0, Math.min(at.x + 10, parent.width - width - 4))
    y: Math.max(0, Math.min(at.y - height / 2, parent.height - height - 4))
    width: words.implicitWidth + 2 * Theme.grid + 4; height: words.implicitHeight + Theme.grid
    radius: Theme.radiusCtl
    color: Theme.raised; border.color: Theme.popupEdge
    Text {
        id: words
        anchors.centerIn: parent
        text: lbl.ts.text
        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
    }
}

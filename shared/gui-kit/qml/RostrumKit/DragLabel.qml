import QtQuick
import "."

// The small label while dragging (INTERACTION.md 1.10): the value, never a name for it ("X 120  Y 48", "120 × 48",
// "15°", "+6 f · drop", "1.20 s → 3.40 s", "−4.0 dB"). It sits just right of `at` (the pointer, or the dragged edge
// or key, in the parent's px) and is kept inside the parent. Bind it to a DragView (rostrum_gui/drag.py):
// `text` = view.text, `at` = Qt.point(view.x, view.y). Empty text: hidden.
Rectangle {
    id: lbl
    property string text: ""
    property point at: Qt.point(0, 0)
    visible: text !== ""
    z: 1000
    x: Math.max(0, Math.min(at.x + 12, parent.width - width - 4))
    y: Math.max(0, Math.min(at.y - height / 2, parent.height - height - 4))
    width: words.implicitWidth + 2 * Theme.grid + 4; height: words.implicitHeight + Theme.grid
    radius: Theme.radiusCtl
    color: Theme.raised; border.color: Theme.popupEdge
    Text {
        id: words
        anchors.centerIn: parent
        text: lbl.text
        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.features: { "tnum": 1 }
    }
}

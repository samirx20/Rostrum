import QtQuick
import RostrumKit

// ◂ ▸ on a voice line's block: the earlier / later take (editorSide.stepTake = `line.set {seed}`, one undo step, instant:
// the audio is in the cache). Only on a line with more than one take, and each arrow only when there is a take that way
// (rule of individuality); only on a block wide enough to carry them. Sits above the lanes' mouse area, so a press on
// an arrow steps the take and never starts a drag.
Row {
    id: a
    property var block
    property var ruler
    property int xOffset: 0          // where the ruler's left edge sits in the parent (the roll has a keys column)
    property real inset: 5             // from the top of the parent
    readonly property real w: Math.max(2, ruler.wOf(block.dur) - 1)
    visible: w >= 70 && (block.canBack || block.canNext) && ruler.visibleX(Math.round(ruler.xOf(block.t)) + w - width - 8)
    x: xOffset + Math.round(ruler.xOf(block.t)) + w - width - 8; y: inset
    spacing: 2
    Repeater {
        model: [{"step": -1, "glyph": "◂", "tip": "Earlier take", "on": !!block.canBack},
                {"step": 1, "glyph": "▸", "tip": "Later take", "on": !!block.canNext}]
        delegate: Rectangle {
            required property var modelData
            visible: modelData.on
            width: 16; height: 14; radius: 3
            color: area.containsMouse ? Theme.accent : Qt.rgba(0, 0, 0, 0.45)
            Text { anchors.centerIn: parent; text: modelData.glyph; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
            MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: editorSide.stepTake(a.block.id, modelData.step) }
            HoverTip { text: modelData.tip; hovered: area.containsMouse; pressed: area.pressed }
        }
    }
}

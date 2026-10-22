import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Lip sync… (UX_SPEC 3.23): opened by the context bar's action on a mouth swap set, under the bar, at the right edge. The project's voice
// lines (RostrumSound's own: click one), a row per mouth shape with its drawing (guessed from the names; pick another to
// fix it), Apply = one change. Esc or a click away closes it with nothing changed (backend.lipsync: rig_lipsync.py).
QQC.Popup {
    id: pop
    readonly property var ls: backend.lipsync
    modal: true; dim: false
    padding: Theme.pad
    width: 380
    x: parent.width - width - Theme.gap; y: 104      // the right edge, under the bar: the face on the canvas stays in view
    closePolicy: QQC.Popup.CloseOnPressOutside | QQC.Popup.CloseOnEscape
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    onClosed: ls.close()
    Connections {
        target: pop.ls
        function onOpened() { pop.open() }
        function onChanged() { if (!pop.ls.open && pop.opened) pop.close() }
    }
    component Words: Text { color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; elide: Text.ElideRight }
    contentItem: Column {
        spacing: Theme.grid
        Text { text: "Lip sync · " + pop.ls.what; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
        Words { text: "Voice line"; color: Theme.fg3; font.pixelSize: Theme.label }
        Repeater {          // the project's voice lines with a voice: click one
            model: pop.ls.lines
            delegate: Rectangle {
                id: line
                required property var modelData
                width: pop.availableWidth; height: Theme.row; radius: Theme.radiusCtl
                color: modelData.picked ? Theme.accentSoft : lineArea.containsMouse ? Theme.hover : "transparent"
                Words { anchors { left: parent.left; right: parent.right; margins: Theme.grid; verticalCenter: parent.verticalCenter }
                        text: line.modelData.label; color: Theme.fg }
                MouseArea { id: lineArea; anchors.fill: parent; hoverEnabled: true; onClicked: pop.ls.pickLine(line.modelData.id) }
            }
        }
        Words { visible: text !== ""; width: pop.availableWidth; wrapMode: Text.WordWrap; elide: Text.ElideNone; text: pop.ls.note; color: Theme.fg3 }
        Words { text: "Mouth shapes"; color: Theme.fg3; font.pixelSize: Theme.label; visible: pop.ls.lines.length > 0 }
        Repeater {          // a row per shape: the drawing that shows for it
            model: pop.ls.lines.length > 0 ? pop.ls.rows : []
            delegate: Item {
                id: shape
                required property var modelData
                width: pop.availableWidth; height: Theme.row
                Words { anchors.verticalCenter: parent.verticalCenter; width: parent.width - pick.width - Theme.grid
                        text: shape.modelData.shape + "  " + shape.modelData.words }
                ChoiceField {
                    id: pick
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    width: 150
                    options: shape.modelData.options; current: shape.modelData.layer
                    onPicked: (v) => pop.ls.setShape(shape.modelData.shape, v)
                }
            }
        }
        Row {
            anchors.right: parent.right
            spacing: Theme.grid
            Button { text: "Cancel"; onClicked: pop.close() }
            Button { text: "Apply"; kind: "primary"; visible: pop.ls.ready; onClicked: pop.ls.apply()
                     help: "Key the mouth to the voice line: one change you can undo." }
        }
    }
}

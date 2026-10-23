import QtQuick
import RostrumKit

// Lip sync… (UX_SPEC 3.23): opened by the context bar's action on a mouth swap set, a sheet in the settings panel's place
// (Inspector `sheets`), so the face on the canvas stays in view. The project's voice lines (RostrumSound's own: click
// one), a row per mouth shape with its drawing (guessed from the names; pick another to fix it), Apply = one change.
// Esc or × closes it with nothing changed (backend.lipsync: rig_lipsync.py).
Panel {
    id: pop
    anchors.fill: parent
    readonly property var ls: backend.lipsync
    readonly property real availableWidth: width - 2 * bodyPad
    visible: pop.ls.open
    title: "Lip sync · " + pop.ls.what
    onVisibleChanged: if (visible) forceActiveFocus()
    Keys.onEscapePressed: pop.close()
    function close() { pop.ls.close() }
    headerRight: IconButton { glyph: "×"; kind: "ghost"; tip: "Close  Esc"; onClicked: pop.close() }
    component Words: Text { color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; elide: Text.ElideRight }
    SheetScroll {
        spacing: Theme.grid
        Words { text: "Voice line"; color: Theme.fg3; font.pixelSize: Theme.label; visible: pop.ls.lines.length > 0 }
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
                width: pop.availableWidth; height: Math.max(Theme.row, said.implicitHeight + 4)
                Words { id: said; anchors.verticalCenter: parent.verticalCenter; width: parent.width - pick.width - Theme.grid
                        wrapMode: Text.WordWrap; elide: Text.ElideNone   // a long shape name wraps, never cut
                        text: shape.modelData.shape + "  "     // "(OO W)" stays whole on its line
                              + shape.modelData.words.replace(/\([^)]*\)/, m => m.replace(/ /g, "\u00a0")) }
                ChoiceField {
                    id: pick
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    width: 150
                    options: shape.modelData.options; current: shape.modelData.layer
                    onPicked: (v) => pop.ls.setShape(shape.modelData.shape, v)
                }
            }
        }
        Button { anchors.right: parent.right; text: "Apply"; kind: "primary"; visible: pop.ls.ready; onClicked: pop.ls.apply()
                 help: "Key the mouth to the voice line: one change you can undo." }   // × or Esc closes: no second way
    }
}

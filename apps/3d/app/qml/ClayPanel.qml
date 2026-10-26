import QtQuick
import RostrumKit

// The settings panel while the Clay tool is on (3d-visual DESIGN mockup 2, § 2; screen3d/clay_tool_qt.py). The clay's
// name and kind; then Make (Lump; Draw and Spin join in CL2) and, with a clay selected, Brush (Add, Carve, Smooth), one
// choice across both: what a drag in the viewport does. Then the brush's Size, Strength and Mirror, the clay's own
// fields drawn by the kit's rows (clay.set, one undo step each). Nothing else: no helper text (the tiles' hover says
// what each does). Q, V or Esc leaves.
Item {
    id: panel
    objectName: "clayPanel"
    readonly property bool tight: (Window.window ? Window.window.height : 900) < 800
    readonly property int groupSpace: tight ? Theme.groupGap : 20       // DESIGN § 4.1: 20 between groups, 16 under 800 high
    Flickable {
        anchors.fill: parent
        contentHeight: col.height + 2 * Theme.pad
        clip: true
        Column {
            id: col
            // the kit's rows end 4 px from the panel's edge (their key gutter inside); the tiles keep 12 px, as on the left
            anchors { left: parent.left; right: parent.right; top: parent.top
                      leftMargin: Theme.padLeft; rightMargin: Theme.padRight; topMargin: Theme.pad }
            readonly property real inner: width - Theme.padLeft + Theme.padRight

            Text {      // what is sculpted: the clay's name (or the tool's, before there is one)
                objectName: "clayName"
                width: col.inner; elide: Text.ElideRight
                text: viewport.clay.itemName || "Clay"
                color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.heading; font.weight: Font.DemiBold
            }
            Text {
                visible: viewport.clay.itemName !== ""
                text: "Clay"; color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label
            }

            Item { width: 1; height: panel.groupSpace }
            Text { text: "Make"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
            Item { width: 1; height: Theme.gap }
            ClayTiles {
                objectName: "clayMake"
                width: col.inner; tight: panel.tight; prefix: "clayMake"
                tiles: viewport.clay.make
                onPicked: (v) => viewport.clay.choose(v)
            }

            Column {    // Brush and its rows: only with a clay to sculpt (rule of individuality)
                width: parent.width
                visible: viewport.clay.brushes.length > 0
                Item { width: 1; height: panel.groupSpace }
                Text { text: "Brush"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
                Item { width: 1; height: Theme.gap }
                ClayTiles {
                    objectName: "clayBrushes"
                    width: col.inner; tight: panel.tight; prefix: "clayBrush"
                    tiles: viewport.clay.brushes
                    onPicked: (v) => viewport.clay.choose(v)
                }
                Item { width: 1; height: Theme.pad }
                Repeater {      // Size, Strength, Mirror
                    model: viewport.clay.brushObj.rows
                    delegate: InspectorRow { width: col.width; bridge: viewport.clay.brushObj
                                             instant: viewport.clay.brushObj.rows.instant }
                }
            }
        }
    }
}

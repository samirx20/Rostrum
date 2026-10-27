import QtQuick
import RostrumKit

// The settings panel while the Clay tool is on (3d-visual DESIGN mockup 2, § 2; screen3d/clay_tool_qt.py). The clay's
// name and kind; then Make (Lump) and, with a clay selected, Brush: the six that shape (Add, Carve, Smooth / Pull,
// Flatten, Crease: two full rows of three) and Mask on a row of its own a little apart (it protects, it does not shape).
// One choice across all of them: what a drag in the viewport does. Then the brush's rows, the clay's own fields drawn by
// the kit's rows (clay.set, one undo step each): Size, Strength, Mirror, then Falloff, Spacing, Front faces only.
// After a Draw, the drawn shape's Puff sits under the name until the next stroke (claystep.set puff on that step); with
// a clay selected, Steps lists its steps (ClaySteps.qml).
// Nothing else: no helper text (the tiles' hover says what each does, Ctrl's opposite included). Q, V or Esc leaves.
Item {
    id: panel
    objectName: "clayPanel"
    readonly property bool tight: (Window.window ? Window.window.height : 900) < 800
    readonly property int groupSpace: tight ? Theme.groupGap : 20       // DESIGN § 4.1: 20 between groups, 16 under 800 high
    Flickable {
        id: flick
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

            Column {    // the last drawn shape's Puff, until the next stroke (clay_steps_qt.py)
                objectName: "clayPuff"
                width: parent.width
                visible: viewport.clay.stepsObj.hasPuff
                Item { width: 1; height: Theme.gap }
                Repeater {
                    model: viewport.clay.stepsObj.puff.rows
                    delegate: InspectorRow { width: col.width; bridge: viewport.clay.stepsObj.puff
                                             instant: viewport.clay.stepsObj.puff.rows.instant }
                }
            }

            Item { width: 1; height: panel.groupSpace }
            Text { objectName: "clayMakeHead"; text: "Make"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
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
                Text { objectName: "clayBrushHead"; text: "Brush"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
                Item { width: 1; height: Theme.gap }
                ClayTiles {
                    objectName: "clayBrushes"
                    width: col.inner; tight: panel.tight; prefix: "clayBrush"
                    tiles: viewport.clay.brushes
                    onPicked: (v) => viewport.clay.choose(v)
                }
                Item { width: 1; height: Theme.gap + 4 }      // DESIGN § 4.1: 12 after a grid; Mask sits apart from the six
                ClayTiles {
                    objectName: "clayMasks"
                    width: col.inner; tight: panel.tight; prefix: "clayBrush"
                    tiles: viewport.clay.masks
                    onPicked: (v) => viewport.clay.choose(v)
                }
                Item { width: 1; height: Theme.pad }
                Repeater {      // Size, Strength, Mirror, Falloff, Spacing, Front faces only (clay_brush_qt.py)
                    model: viewport.clay.brushObj.rows
                    delegate: InspectorRow { width: col.width; bridge: viewport.clay.brushObj
                                             instant: viewport.clay.brushObj.rows.instant }
                }
                Item { width: 1; height: panel.groupSpace }
                ClaySteps { width: col.width; inner: col.width - Theme.keyGutter }   // the list ends where the fields do
            }
        }
    }
    EdgeFade { flick: flick; anchors.fill: flick }    // under 800 high the rows scroll: a half-scrolled row fades
}

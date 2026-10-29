import QtQuick
import RostrumKit

// The settings panel while the Clay tool is on (3d-visual DESIGN mockup 2, § 2; screen3d/clay_tool_qt.py). The clay's
// name and kind; then Make (Lump) and, with a clay selected, Brush: the six that shape (Add, Carve, Smooth / Pull,
// Flatten, Crease: two full rows of three) and Mask on a row of its own a little apart (it protects, it does not shape).
// One choice across all of them: what a drag in the viewport does. Then the brush's rows, the clay's own fields drawn by
// the kit's rows (clay.set, one undo step each): Size and Strength; then Layers once the clay has a sculpt layer
// (ClayLayers.qml); then Steps, the clay's steps (ClaySteps.qml); then Clean mesh (Faces, Make clean mesh: ClayClean.qml); then
// the kit's More fold (closed at first, kept as left for the session) with Falloff, Spacing, Front faces only and
// Mirror. Steps sits above the fold so a 900 px high window shows it without scrolling (3d-v4).
// After a Draw, the drawn shape's Puff sits under the name until the next stroke (claystep.set puff on that step).
// Nothing else: no helper text (the tiles' hover says what each does, Ctrl's opposite included). Q, V or Esc leaves.
Item {
    id: panel
    objectName: "clayPanel"
    // DESIGN § 4.1: 20 between groups, 16 when tight. Tight below 960 high (3d-v4; DESIGN said 800): at 900 the 52 px
    // tiles leave room for Steps and the More fold's head with nothing scrolled
    readonly property bool tight: (Window.window ? Window.window.height : 900) < 960
    readonly property int groupSpace: tight ? Theme.groupGap : 20
    Flickable {
        id: flick
        anchors.fill: parent
        contentHeight: col.height + 2 * Theme.pad
        clip: true
        WheelScroll { flick: flick }   // the first click after a wheel scroll lands (the kit's WheelScroll.qml)
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
                Repeater {      // Size, Strength (clay_brush_qt.py)
                    model: viewport.clay.brushObj.rows
                    delegate: InspectorRow { width: col.width; bridge: viewport.clay.brushObj
                                             instant: viewport.clay.brushObj.rows.instant }
                }
                Item { width: 1; height: panel.groupSpace }
                ClayLayers { id: sculptLayers; width: col.width; inner: col.width - Theme.keyGutter }   // once the clay has one
                Item { width: 1; height: sculptLayers.visible ? panel.groupSpace : 0 }
                ClaySteps { width: col.width; inner: col.width - Theme.keyGutter }   // the list ends where the fields do
                Item { width: 1; height: panel.groupSpace }
                ClayClean { id: cleanMesh; width: col.width; inner: col.width - Theme.keyGutter }   // Make clean mesh
                Item { width: 1; height: panel.groupSpace }
                Repeater {      // More, then Falloff, Spacing, Front faces only, Mirror behind it (clay_brush_qt.py)
                    objectName: "clayMore"
                    model: viewport.clay.brushObj.finer
                    delegate: InspectorRow { width: col.width; bridge: viewport.clay.brushObj
                                             instant: viewport.clay.brushObj.finer.instant }
                }
            }
        }
    }
    // More opened: its rows follow into view while they ease in (at 900 high they start under the panel's edge)
    property bool moreWasOpen: false
    property bool following: false
    Connections {
        target: viewport.clay.brushObj
        function onChanged() {
            const open = viewport.clay.brushObj.moreOpen
            if (open && !panel.moreWasOpen) { panel.following = true; followEnd.restart(); panel.showMore() }
            panel.moreWasOpen = open
        }
    }
    Component.onCompleted: moreWasOpen = viewport.clay.brushObj.moreOpen
    Timer { id: followEnd; interval: 400; onTriggered: panel.following = false }
    Connections { target: flick; function onContentHeightChanged() { if (panel.following) panel.showMore() } }
    function showMore() { flick.contentY = Math.max(0, flick.contentHeight - flick.height) }
    EdgeFade { flick: flick; anchors.fill: flick }    // rows that don't fit scroll: a half-scrolled row fades
}

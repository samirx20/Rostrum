import QtQuick
import RostrumKit

// The settings panel while Paint is on (SPEC §5, mockup 06; screen3d/paint_mode_qt.py). "Painting on Lid", then Brush:
// where the brush lands (On the surface: on the canvas where you drag; From the view: as drawn on the picture, on every
// item it crosses), the kit's bar settings (tip, size, colour, opacity) as the kit's own rows, and Paints (what the active layer paints:
// Colour, Roughness, Relief, Metal, Glow); then Paint layers, top first, + for a new one; each row: its eye, its name
// (click: paint on it), what it paints. A drag on the viewport paints on the active layer, one undo step per stroke.
// Only what applies now is shown: Paints only with a layer to set it on. B or Esc leaves.
Item {
    Flickable {
        anchors.fill: parent
        contentHeight: col.height + 2 * Theme.pad
        clip: true
        Column {
            id: col
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: Theme.pad }
            spacing: Theme.gap

            Row {   // what this is, and how to leave
                width: parent.width; spacing: Theme.grid
                Text { text: "Painting"; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold
                       anchors.verticalCenter: parent.verticalCenter }
                Text { text: "on " + paintMode.itemName; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
                       elide: Text.ElideRight; width: parent.width - 80; anchors.verticalCenter: parent.verticalCenter }
            }

            Segmented {   // where the brush lands
                objectName: "paintWhere"; width: parent.width
                options: paintMode.wheres; current: paintMode.where
                onPicked: (v) => paintMode.setWhere(v)
            }
            Repeater {   // Brush: the kit's rows (InspectorRow talks to paintMode.brushObj as its bridge)
                model: paintMode.brushObj.rows
                delegate: InspectorRow { width: col.width; bridge: paintMode.brushObj; instant: paintMode.brushObj.rows.instant }
            }
            Row {   // what the active layer paints
                visible: paintMode.activeChannel !== ""
                width: parent.width; spacing: Theme.grid
                Text { width: 72; text: "Paints"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
                       anchors.verticalCenter: parent.verticalCenter }
                ChoiceField { objectName: "paintChannel"; width: parent.width - 72 - Theme.grid
                              options: paintMode.channels; current: paintMode.activeChannel
                              onPicked: (v) => paintMode.setChannel(v) }
            }

            Item { width: 1; height: Theme.grid }
            Row {   // Paint layers  [tint]  +
                width: parent.width
                Text { text: "Paint layers"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
                       width: parent.width - addLayer.width - tint.width; anchors.verticalCenter: parent.verticalCenter }
                IconButton { id: tint; objectName: "paintCoverage"; glyph: "▨"; kind: "ghost"
                             down: paintMode.coverageObj.on
                             help: paintMode.coverageObj.on ? "Hide the unpainted tint"
                                                            : "Tint what the shot sees and isn't painted yet (orange hatch)"
                             onClicked: paintMode.coverageObj.toggle() }
                IconButton { id: addLayer; objectName: "paintAddLayer"; glyph: "+"; kind: "ghost"
                             help: "A new paint layer on top, painting what the active one paints"; onClicked: paintMode.addLayer() }
            }
            Text {   // coverage: how much of what the shot sees is painted
                objectName: "paintCoverageLine"
                visible: text !== ""; width: parent.width; elide: Text.ElideRight
                text: paintMode.coverageObj.line
                color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
            }
            Text { visible: paintMode.layers.length === 0; width: parent.width; wrapMode: Text.Wrap
                   color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label
                   text: "Drag on " + paintMode.itemName + " to paint · right-drag turns the view" }
            Repeater {
                model: paintMode.layers
                delegate: Rectangle {
                    width: col.width; height: Theme.button; radius: Theme.radiusCtl
                    color: modelData.active ? Theme.active : rowArea.containsMouse ? Theme.hover : "transparent"
                    MouseArea { id: rowArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: paintMode.setActive(modelData.id) }
                    IconButton { id: eye; kind: "ghost"; glyph: modelData.visible ? "◉" : "○"
                                 help: modelData.visible ? "Hide this layer" : "Show this layer"
                                 anchors.verticalCenter: parent.verticalCenter; onClicked: paintMode.toggleVisible(modelData.id) }
                    Text { x: eye.width + Theme.grid; width: parent.width - x - kindWord.width - Theme.pad
                           text: modelData.name; elide: Text.ElideRight
                           color: modelData.visible ? Theme.fg : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
                           anchors.verticalCenter: parent.verticalCenter }
                    Text { id: kindWord; text: modelData.paints; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                           anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter } }
                }
            }
        }
    }
}

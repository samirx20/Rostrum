import QtQuick
import RostrumKit

// A grid of Clay tiles (3d-visual DESIGN § 4.2): three per row, 8 px apart, 64 px high (52 under 800 high), a picture
// (ClayIcon) over its name. At rest transparent, hover grey, the chosen one a soft blue with its picture in blue and its
// name semibold. Hover: the name, one line of what it does, and the key. `tiles`: [{value, label, help, on}].
// (Kit gap, DESIGN § 4.6: when the kit's ToolTiles lands, this becomes it.)
Grid {
    id: grid
    property var tiles: []
    property string prefix: "clayTile"
    property bool tight: false
    signal picked(string value)
    columns: 3
    spacing: Theme.gap
    readonly property real tileW: Math.floor((width - 2 * spacing) / 3)
    Repeater {
        model: grid.tiles
        delegate: Item {
            id: tile
            required property var modelData
            objectName: grid.prefix + modelData.label
            width: grid.tileW; height: grid.tight ? 52 : 64
            readonly property bool on: modelData.on
            Rectangle {
                anchors.fill: parent; radius: Theme.radiusCtl
                color: tile.on ? Theme.accentSoft : hover.hovered ? Theme.hover : "transparent"
                Behavior on color { ColorAnimation { duration: Theme.fast } }
            }
            ClayIcon {
                name: tile.modelData.value
                ink: tile.on ? Theme.accent : Theme.fg
                anchors.horizontalCenter: parent.horizontalCenter
                y: grid.tight ? 5 : 9
                scale: grid.tight ? 0.8 : 1
            }
            Text {
                anchors { horizontalCenter: parent.horizontalCenter; bottom: parent.bottom; bottomMargin: grid.tight ? 4 : 7 }
                width: Math.min(implicitWidth, tile.width - 6)
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: Theme.label    // "Turn into clay" in a narrow panel
                horizontalAlignment: Text.AlignHCenter
                text: tile.modelData.label
                color: tile.on ? Theme.fg : Theme.fg2
                font.family: uiFont; font.pixelSize: Theme.body; font.weight: tile.on ? Font.DemiBold : Font.Normal
            }
            HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
            MouseArea { id: area; anchors.fill: parent; onClicked: grid.picked(tile.modelData.value) }
            HoverTip { text: tile.modelData.label; help: tile.modelData.help; hovered: hover.hovered; pressed: area.pressed }
        }
    }
}

import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Look harness for the colour pickers: a fill field and a colour field in an inspector-like column.
QQC.ApplicationWindow {
    id: win
    visible: true; width: 1646; height: 900
    color: Theme.app
    property var fill: ({})
    property string tint: "#4c8dff"
    function openFill() { paintField.open() }
    Rectangle { x: parent.width - 296; width: 296; height: parent.height; color: Theme.panel
        Column { x: 16; y: 120; width: parent.width - 32; spacing: 8
            Row { height: Theme.row; Text { width: 104; text: "Fill"; color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont; anchors.verticalCenter: parent.verticalCenter }
                  PaintField { id: paintField; width: 160; paint: win.fill; scrubbed: true; onLive: (p) => win.fill = p } }
            Row { height: Theme.row; Text { width: 104; text: "Colour"; color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont; anchors.verticalCenter: parent.verticalCenter }
                  ColorField { width: 160; hex: win.tint; onEdited: (v) => win.tint = v } }
        } }
}

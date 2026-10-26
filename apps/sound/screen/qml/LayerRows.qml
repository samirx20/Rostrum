import QtQuick
import RostrumKit

// The settings panel's "Layers" group (Main.qml's Inspector `below`): the selected clip is one layer
// of a layered sound, so its group's layers are listed in time order, this one marked; a click selects that layer.
// Absent unless the selection has a group with another layer (rule of individuality; screensound/layers.py).
Column {
    id: lr
    // (follows `pickStamp`: a number; `picked` is a copy of every id for each reader, 3,607 on Ctrl+A)
    readonly property var info: { backend.pickStamp; backend.historyCount; return backend.layers() }
    visible: !!info.group
    width: parent ? parent.width - Theme.keyGutter : 0     // ends where the fields above end (the key gutter is theirs)
    Text { text: "Layers"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
           height: Theme.groupGap + Theme.rowDense; verticalAlignment: Text.AlignBottom }
    NameLabel { width: parent.width; height: Theme.rowDense; text: lr.info.group || ""; color: Theme.fg2
                font.pixelSize: Theme.label; verticalAlignment: Text.AlignVCenter }
    Repeater {
        model: lr.info.rows || []
        delegate: Item {
            id: line
            required property var modelData
            width: lr.width; height: Theme.row
            Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: Theme.hover
                        visible: !line.modelData.here && area.containsMouse }
            NameLabel { anchors { left: parent.left; leftMargin: Theme.grid; right: kind.left; rightMargin: Theme.gap
                                  verticalCenter: parent.verticalCenter }
                        text: line.modelData.label; color: line.modelData.here ? Theme.accent : Theme.fg }
            Text { id: kind; anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
                   text: line.modelData.what; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; enabled: !line.modelData.here
                        cursorShape: Qt.PointingHandCursor; onClicked: backend.select(line.modelData.id) }
        }
    }
}

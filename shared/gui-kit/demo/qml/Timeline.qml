import QtQuick
import RostrumKit

// Stand-in timeline: a ruler and one track per item, full width.
Panel {
    id: panel
    title: "Timeline"
    readonly property int labelWidth: 140
    Item {
        id: ruler
        x: panel.labelWidth; width: parent.width - panel.labelWidth; height: 20
        Repeater {
            model: 21
            delegate: Item {
                required property int index
                x: index * ruler.width / 20; height: 20
                Rectangle { width: 1; height: index % 5 === 0 ? 8 : 4; y: 20 - height; color: Theme.line }
                Text { visible: index % 5 === 0 && index < 20; x: 4; text: index + "s"
                       color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            }
        }
    }
    Column {
        y: 26; width: parent.width; spacing: Theme.grid
        Repeater {
            model: backend.items
            delegate: Item {
                required property var modelData
                required property int index
                width: parent.width; height: Theme.rowDense
                Text { width: panel.labelWidth - Theme.gap; anchors.verticalCenter: parent.verticalCenter; elide: Text.ElideRight
                       text: parent.modelData.label; color: parent.modelData.id === backend.selected ? Theme.fg : Theme.fg3
                       font.family: uiFont; font.pixelSize: Theme.body }
                Rectangle { x: panel.labelWidth; width: parent.width - panel.labelWidth; height: parent.height
                            radius: Theme.radiusCtl; color: Theme.sunken
                    Rectangle { x: parent.width * (0.06 + 0.12 * parent.parent.index); width: parent.width * 0.38; height: parent.height
                                radius: Theme.radiusCtl
                                color: parent.parent.modelData.id === backend.selected ? Theme.accentSoft : Theme.raised } }
            }
        }
    }
}

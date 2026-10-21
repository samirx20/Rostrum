import QtQuick
import "."

// Stand-in timeline: a ruler and three empty tracks.
Panel {
    id: panel
    title: "Timeline"
    Repeater {
        model: 21
        delegate: Item {
            required property int index
            x: index * (panel.width - 2 * panel.bodyPad) / 20; height: 20
            Rectangle { width: 1; height: index % 5 === 0 ? 8 : 4; y: 20 - height; color: Theme.border }
            Text { visible: index % 5 === 0 && index < 20; x: 4; text: index + "s"; color: Theme.fg3; font.pixelSize: Theme.label }
        }
    }
    Column {
        y: 28; width: parent.width; spacing: Theme.grid
        Repeater {
            model: 3
            delegate: Rectangle { width: parent.width; height: Theme.row; radius: Theme.radiusCtl; color: Theme.app }
        }
    }
}

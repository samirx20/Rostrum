import QtQuick
import QtQuick.Layouts
import "."

// The selected item's settings, most important first. Tint and turn speed drive the live viewport.
Panel {
    id: panel
    property var app
    readonly property var item: app.current
    title: "Inspector"

    component Field: RowLayout {
        property string label
        property string value
        Layout.fillWidth: true; Layout.preferredHeight: Theme.row
        spacing: Theme.gap
        Text { text: parent.label; color: Theme.fg2; font.pixelSize: Theme.body; Layout.preferredWidth: 88 }
        Text { text: parent.value; color: Theme.fg; font.pixelSize: Theme.body; elide: Text.ElideRight; Layout.fillWidth: true }
    }
    component GroupLabel: Text {
        color: Theme.fg3; font.pixelSize: Theme.label; font.weight: Font.DemiBold
        Layout.topMargin: Theme.groupGap; Layout.bottomMargin: Theme.grid
    }

    ColumnLayout {
        anchors.left: parent.left; anchors.right: parent.right
        spacing: 0

        Text { text: panel.item ? panel.item.name : ""; color: Theme.fg; font.pixelSize: 16; font.weight: Font.DemiBold
               Layout.fillWidth: true; elide: Text.ElideRight }
        Text { text: panel.item ? panel.item.kind : ""; color: Theme.fg3; font.pixelSize: Theme.body; Layout.topMargin: 2 }

        GroupLabel { text: "Item" }
        Field { label: "Length"; value: panel.item ? panel.item.length : "" }
        Field { label: "Size"; value: panel.item ? panel.item.size : "" }
        Field { label: "Frame rate"; value: panel.item ? panel.item.rate : "" }

        GroupLabel { text: "Viewport" }
        RowLayout {
            Layout.fillWidth: true; Layout.preferredHeight: Theme.row; spacing: Theme.gap
            Text { text: "Tint"; color: Theme.fg2; font.pixelSize: Theme.body; Layout.preferredWidth: 88 }
            Repeater {
                model: ["#c9ccd4", "#7fa8ff", "#e0b48a", "#9ad1b4", "#d9a3c7"]
                delegate: Rectangle {
                    required property string modelData
                    readonly property bool on: panel.item && Qt.colorEqual(panel.item.tint, modelData)
                    width: 20; height: 20; radius: 10; color: modelData
                    border.width: 2; border.color: on ? Theme.fg : "transparent"
                    MouseArea { anchors.fill: parent; anchors.margins: -2; cursorShape: Qt.PointingHandCursor
                                onClicked: panel.app.setTint(modelData) }
                }
            }
            Item { Layout.fillWidth: true }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.preferredHeight: Theme.row; spacing: Theme.gap
            Text { text: "Turn speed"; color: Theme.fg2; font.pixelSize: Theme.body; Layout.preferredWidth: 88 }
            Item {  // slider: track, fill, handle
                id: slider
                Layout.fillWidth: true; Layout.preferredHeight: 20
                readonly property real frac: (panel.app.speed - 0) / 3
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 4; radius: 2; color: Theme.active }
                Rectangle { anchors.verticalCenter: parent.verticalCenter; width: slider.frac * parent.width; height: 4; radius: 2; color: Theme.accent }
                Rectangle { x: slider.frac * (parent.width - width); anchors.verticalCenter: parent.verticalCenter
                            width: 14; height: 14; radius: 7; color: Theme.fg }
                MouseArea {
                    anchors.fill: parent
                    function set(mx) { panel.app.speed = Math.round(Math.max(0, Math.min(1, mx / width)) * 30) / 10 }
                    onPressed: (m) => set(m.x)
                    onPositionChanged: (m) => set(m.x)
                }
            }
            Text { text: panel.app.speed.toFixed(1) + "×"; color: Theme.fg; font.pixelSize: Theme.body
                   font.family: monoFont; Layout.preferredWidth: 32; horizontalAlignment: Text.AlignRight }
        }
    }
}

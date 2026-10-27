import QtQuick
import "."

// A few choices side by side, one picked (a page switch: Design | Animate). Click picks: one picked(value).
Rectangle {
    id: s
    property var options: []              // [{value, label}] or plain strings
    property string current: ""
    signal picked(string value)
    implicitHeight: Theme.button; implicitWidth: row.implicitWidth + 4
    radius: Theme.radiusCtl; color: Theme.sunken

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 2
        Repeater {
            model: s.options
            delegate: Rectangle {
                id: opt
                required property var modelData
                readonly property string value: typeof modelData === "string" ? modelData : modelData.value
                readonly property bool on: value === s.current
                width: label.implicitWidth + 2 * Theme.pad; height: s.height - 4
                radius: Theme.radiusCtl - 2
                color: area.containsMouse ? Theme.raised : "transparent"      // the hover fades in ...
                Behavior on color { ColorAnimation { duration: Theme.fast } }
                Rectangle { anchors.fill: parent; radius: parent.radius; color: Theme.active
                            visible: opt.on || area.pressed }                  // ... the pick and the press never do
                Text { id: label; anchors.centerIn: parent
                       text: typeof opt.modelData === "string" ? opt.modelData : opt.modelData.label
                       color: opt.on ? Theme.fg : Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
                       font.weight: opt.on ? Font.DemiBold : Font.Normal; z: 1 }
                MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: if (!opt.on) { if (typeof ack !== "undefined" && ack) ack.by(opt); s.picked(opt.value) } }
            }
        }
    }
}

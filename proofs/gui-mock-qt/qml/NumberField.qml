import QtQuick
import "."

// A compact number: value + unit. Drag sideways, use the wheel or the arrows (shown on hover) to change it.
Rectangle {
    id: f
    property real value: 0
    property real from: 0
    property real to: 1
    property real step: 1
    property string unit: ""
    signal edited(real value)
    implicitWidth: 112; implicitHeight: 24; radius: Theme.radiusCtl
    color: hover.containsMouse || drag.pressed ? Theme.hover : Theme.raised
    Behavior on color { ColorAnimation { duration: Theme.fast } }

    readonly property int decimals: Math.max(0, Math.ceil(-Math.log10(step) - 1e-9))
    function bump(n) { edited(Math.max(from, Math.min(to, value + n * step))) }

    Text {
        anchors.centerIn: parent
        text: f.unit === "f/" ? "f/" + f.value.toFixed(f.decimals)
              : f.value.toFixed(f.decimals) + (/^[a-z]/i.test(f.unit) ? " " : "") + f.unit
        color: Theme.fg; font.pixelSize: Theme.body; font.family: monoFont
    }
    MouseArea {
        id: hover; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton
        onWheel: (w) => f.bump(w.angleDelta.y > 0 ? 1 : -1)
    }
    MouseArea {  // drag the field itself
        id: drag; anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 20; cursorShape: Qt.SizeHorCursor
        property real startX; property real startValue
        onPressed: (m) => { startX = m.x; startValue = f.value }
        onPositionChanged: (m) => {
            var n = Math.round((m.x - startX) / 6)
            f.edited(Math.max(f.from, Math.min(f.to, startValue + n * f.step)))
        }
    }
    Repeater {
        model: [{ s: "‹", d: -1 }, { s: "›", d: 1 }]
        delegate: Item {
            required property var modelData
            x: modelData.d < 0 ? 0 : f.width - width; width: 20; height: f.height
            opacity: hover.containsMouse ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Theme.fast } }
            Text { anchors.centerIn: parent; text: modelData.s; color: Theme.fg2; font.pixelSize: 14 }
            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: f.bump(modelData.d) }
        }
    }
}

import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import "."

// Transport + a ruler and three tracks. Click or drag anywhere below the transport to scrub.
Panel {
    id: panel
    property var app
    title: "Timeline"
    readonly property real pxPerSec: tracks.width / app.duration

    function tc(t) {
        var s = Math.floor(t), f = Math.floor((t - s) * 100)
        return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0") + "." + String(f).padStart(2, "0")
    }

    headerRight: [
        Text { anchors.verticalCenter: parent.verticalCenter; font.family: monoFont; font.pixelSize: Theme.body; color: Theme.fg2
               text: panel.tc(panel.app.playhead) + " / " + panel.tc(panel.app.duration); rightPadding: Theme.gap },
        Rectangle {
            width: 28; height: 24; radius: Theme.radiusCtl
            color: playHover.containsMouse ? Theme.hover : Theme.raised
            Row {  // pause: two bars
                anchors.centerIn: parent; spacing: 3; visible: panel.app.playing
                Repeater { model: 2; Rectangle { width: 3; height: 10; radius: 1; color: Theme.fg } }
            }
            Shape {  // play: a triangle
                anchors.centerIn: parent; anchors.horizontalCenterOffset: 1; width: 9; height: 10; visible: !panel.app.playing
                preferredRendererType: Shape.CurveRenderer
                ShapePath { fillColor: Theme.fg; strokeWidth: -1
                            startX: 0; startY: 0; PathLine { x: 9; y: 5 } PathLine { x: 0; y: 10 } PathLine { x: 0; y: 0 } }
            }
            MouseArea { id: playHover; anchors.fill: parent; hoverEnabled: true; onClicked: panel.app.togglePlay() }
        }
    ]

    Item {
        id: tracks
        anchors.fill: parent
        // ruler
        Repeater {
            model: panel.app.duration + 1
            delegate: Item {
                required property int index
                x: index * panel.pxPerSec; y: 0; height: 20
                Rectangle { width: 1; height: index % 5 === 0 ? 8 : 4; y: 20 - height; color: Theme.border }
                Text { visible: index % 5 === 0 && index < panel.app.duration; x: 4; y: 0; text: index + "s"
                       color: Theme.fg3; font.pixelSize: Theme.label }
            }
        }
        Column {
            y: 28; width: parent.width; spacing: Theme.grid
            Repeater {
                model: [[{ s: 0, e: 20, n: "Launch film · video" }], [{ s: 0, e: 6, n: "Logo reveal" }, { s: 6.5, e: 18, n: "Hero product" }],
                        [{ s: 0, e: 20, n: "Score" }]]
                delegate: Rectangle {
                    required property var modelData
                    width: parent.width; height: Theme.row; radius: Theme.radiusCtl; color: Theme.app
                    Repeater {
                        model: modelData
                        delegate: Rectangle {
                            required property var modelData
                            x: modelData.s * panel.pxPerSec + 1; width: (modelData.e - modelData.s) * panel.pxPerSec - 2
                            height: parent.height; radius: Theme.radiusCtl; color: Theme.raised
                            Text { anchors.left: parent.left; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                                   text: modelData.n; color: Theme.fg2; font.pixelSize: Theme.label }
                        }
                    }
                }
            }
        }
        // playhead
        Item {
            x: panel.app.playhead * panel.pxPerSec; height: parent.height
            Rectangle { x: -0.5; width: 1.5; height: parent.height; color: Theme.accent }
            Rectangle { x: -5; y: 0; width: 10; height: 10; radius: 3; color: Theme.accent }
        }
        MouseArea {
            anchors.fill: parent
            function scrub(mx) { panel.app.seek(mx / panel.pxPerSec) }
            onPressed: (m) => scrub(m.x)
            onPositionChanged: (m) => scrub(m.x)
        }
    }
}

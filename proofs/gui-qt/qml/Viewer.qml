import QtQuick
import QtMultimedia
import Rostrum
import "."

// The centre: the live OpenGL viewport or the 1080p video, one switch apart, with a small frame-rate readout.
Panel {
    id: panel
    property var app
    property alias videoOutput: videoOut
    title: app.viewMode === "video" ? "Video" : "Viewport"
    bodyPad: 0

    headerRight: [
        Row {
            spacing: 2
            Repeater {
                model: [{ key: "viewport", label: "Viewport" }, { key: "video", label: "Video" }]
                delegate: Rectangle {
                    required property var modelData
                    readonly property bool on: panel.app.viewMode === modelData.key
                    width: segLabel.implicitWidth + 2 * Theme.pad; height: 24; radius: Theme.radiusCtl
                    color: on ? Theme.active : segHover.containsMouse ? Theme.hover : "transparent"
                    Text { id: segLabel; anchors.centerIn: parent; text: modelData.label
                           color: parent.on ? Theme.fg : Theme.fg2; font.pixelSize: Theme.body }
                    MouseArea { id: segHover; anchors.fill: parent; hoverEnabled: true; onClicked: panel.app.setMode(modelData.key) }
                }
            }
        },
        Rectangle {
            width: fpsLabel.implicitWidth + 2 * Theme.pad; height: 24; radius: Theme.radiusCtl
            color: fpsHover.containsMouse ? Theme.hover : "transparent"
            Text { id: fpsLabel; anchors.centerIn: parent; text: "FPS"
                   color: panel.app.showFps ? Theme.accent : Theme.fg3; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
            MouseArea { id: fpsHover; anchors.fill: parent; hoverEnabled: true; onClicked: panel.app.showFps = !panel.app.showFps }
        }
    ]

    Rectangle {  // letterbox colour behind video
        anchors.fill: parent
        color: "#0e0e0e"
        GLViewport {
            id: viewport
            objectName: "viewport"
            anchors.fill: parent
            visible: panel.app.viewMode === "viewport"
            time: panel.app.sceneTime * panel.app.speed
            tint: panel.app.current ? panel.app.current.tint : "#c9ccd4"
        }
        VideoOutput {
            id: videoOut
            objectName: "videoOut"
            anchors.fill: parent
            visible: panel.app.viewMode === "video"
            fillMode: VideoOutput.PreserveAspectFit
        }
        Rectangle {
            visible: panel.app.showFps
            anchors.left: parent.left; anchors.top: parent.top; anchors.margins: Theme.pad
            width: readout.implicitWidth + 2 * Theme.gap + 4; height: 24; radius: Theme.radiusCtl
            color: Qt.rgba(0, 0, 0, 0.55)
            Text {
                id: readout
                anchors.centerIn: parent
                font.family: monoFont; font.pixelSize: Theme.label; color: Theme.fg2
                text: {
                    var s = stats, w = s.windowFps.toFixed(0) + " fps"
                    var v = panel.app.viewMode === "video" ? "video " + s.videoFps.toFixed(0) + " fps · window " + w : w
                    return v + " · " + s.memoryMb.toFixed(0) + " MB"
                }
            }
        }
    }
}

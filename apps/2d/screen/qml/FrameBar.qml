import QtQuick
import RostrumKit

// Draw page, bottom, full width: the selected drawing's frames on a ruler (a mark where each drawing starts, a bar
// for how long it is held, numbered), the frame-by-frame buttons, play and time.
Panel {
    id: panel
    title: "Drawing"
    property int labelWidth: 236
    headerRight: [
        FrameTools { anchors.verticalCenter: parent.verticalCenter },
        Item { width: Theme.gap; height: 1 },
        PlayOptions { id: opts; anchors.verticalCenter: parent.verticalCenter },
        Item { width: Theme.gap; height: 1; visible: opts.visible },
        TimeReadout { anchors.verticalCenter: parent.verticalCenter },
        Item { width: Theme.gap; height: 1 },
        PlayButton { playing: backend.playing; onClicked: backend.togglePlay(); implicitHeight: 24; implicitWidth: 24 }
    ]
    TimeRuler {
        id: ruler
        x: panel.labelWidth + Theme.gap + 8; width: parent.width - x - Theme.gap - 8; height: 22
        duration: backend.frameInfo.duration; fps: backend.frameInfo.fps; time: backend.time
    }
    Text {
        visible: painter.drawingId === ""
        anchors { left: parent.left; top: ruler.bottom; topMargin: Theme.gap + Theme.grid }
        text: "Select a drawing layer to see its frames"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
    }
    Item {
        visible: painter.drawingId !== ""
        anchors { left: parent.left; right: parent.right; top: ruler.bottom; topMargin: Theme.gap }
        height: 36
        Text {
            x: Theme.gap; width: panel.labelWidth - Theme.gap; anchors.verticalCenter: parent.verticalCenter
            elide: Text.ElideRight
            text: painter.drawingId; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
        }
        Rectangle {
            id: track
            x: ruler.x - 8; width: ruler.width + 16; height: parent.height; radius: Theme.radiusCtl; color: Theme.sunken
            MouseArea { anchors.fill: parent; onPressed: (m) => backend.setTime(ruler.tOf(m.x - 8))
                        onPositionChanged: (m) => backend.setTime(ruler.tOf(m.x - 8)) }
            FrameMarks { anchors.fill: parent; frames: painter.frameMarks; timeRuler: ruler; numbered: true }
        }
    }
    Rectangle {  // the playhead line through the track
        visible: painter.drawingId !== ""
        x: ruler.x + Math.round(ruler.xOf(backend.time)); y: ruler.y + ruler.height
        width: 1; height: 36 + Theme.gap; color: Theme.accent; opacity: 0.8
    }
}

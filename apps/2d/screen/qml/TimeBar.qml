import QtQuick
import RostrumKit

// Design page, bottom: play, the time, a full-width ruler with the playhead, and Add marker (in a project).
Rectangle {
    id: bar
    color: Theme.panel; radius: Theme.radiusPanel

    PlayButton {
        id: play
        anchors.left: parent.left; anchors.leftMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
        playing: backend.playing; onClicked: backend.togglePlay()
    }
    TimeReadout {
        id: readout
        anchors.left: play.right; anchors.leftMargin: Theme.pad; anchors.verticalCenter: parent.verticalCenter
        width: 128
    }
    AddMarker {
        id: addMarker
        anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
    }
    Rectangle {
        id: well
        anchors { right: addMarker.visible ? addMarker.left : parent.right; left: readout.right; verticalCenter: parent.verticalCenter
                  leftMargin: Theme.pad; rightMargin: addMarker.visible ? Theme.pad : Theme.gap }
        height: 32; radius: Theme.radiusCtl; color: Theme.sunken
        TimeRuler {
            id: ruler
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: Theme.gap; rightMargin: Theme.gap }
            height: parent.height
            duration: backend.frameInfo.duration; fps: backend.frameInfo.fps; time: backend.time
        }
    }
}

import QtQuick
import RostrumKit

// The Clay panel's Clean mesh group (PR4; screen3d/clean_mesh_qt.py, `viewport.clay.cleanObj`), there while a clay is
// selected. Faces (about how many four-sided faces the mesh gets) and Make clean mesh. While it rebuilds, the row is a
// bar with what it does and for how long, and Cancel. A failure is one red line under it until the next try.
Column {
    id: box
    objectName: "clayClean"
    property real inner: width
    readonly property var job: viewport.clay.cleanObj
    visible: job.shown

    Text { objectName: "clayCleanHead"; text: "Clean mesh"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold }
    Item { width: 1; height: Theme.gap }
    Item {      // Faces and the button; while it runs, the bar and Cancel in the same place
        width: box.inner; height: Theme.field
        Text {
            visible: !box.job.running
            anchors.verticalCenter: parent.verticalCenter
            text: "Faces"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
        }
        NumberField {
            objectName: "clayCleanFaces"
            visible: !box.job.running
            x: 56; width: Math.max(72, box.inner - x - make.width - Theme.gap)
            anchors.verticalCenter: parent.verticalCenter
            value: box.job.faces; from: box.job.lo; to: box.job.hi; step: 500; typeStep: 1
            defaultValue: 4000; label: "Faces"
            onEdited: (v) => box.job.setFaces(v)
            onScrubbed: (v) => box.job.setFaces(v)
        }
        Button {
            id: make
            objectName: "clayCleanMake"
            visible: !box.job.running
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            text: "Make clean mesh"
            help: "Rebuilds the clay's surface as an even mesh of four-sided faces, added beside it as a new mesh (the clay is hidden, not removed)."
            onClicked: box.job.make()
        }
        Rectangle {     // the running bar: no share to fill (the library says nothing until it is done), so it pulses
            objectName: "clayCleanBar"
            visible: box.job.running
            anchors { left: parent.left; right: cancel.left; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
            height: Theme.rowDense - 4; radius: Theme.radiusCtl; clip: true
            color: "transparent"; border.width: 1; border.color: Theme.accent
            Rectangle {
                id: pulse
                width: parent.width * 0.3; height: parent.height; radius: Theme.radiusCtl; color: Theme.accentSoft
                SequentialAnimation on x {
                    running: box.job.running; loops: Animation.Infinite
                    NumberAnimation { from: -pulse.width; to: pulse.parent.width; duration: 1400; easing.type: Easing.InOutQuad }
                }
            }
            Text {
                objectName: "clayCleanLabel"
                anchors { left: parent.left; leftMargin: Theme.gap; right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                text: box.job.label; elide: Text.ElideRight
                color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label
            }
        }
        Button {
            id: cancel
            objectName: "clayCleanCancel"
            visible: box.job.running
            width: visible ? implicitWidth : 0
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            text: "Cancel"
            onClicked: box.job.cancel()
        }
    }
    Text {
        objectName: "clayCleanFailure"
        visible: box.job.failure !== ""
        width: box.inner; topPadding: Theme.gap; wrapMode: Text.Wrap
        text: box.job.failure; color: Theme.danger; font.family: uiFont; font.pixelSize: Theme.label
    }
}

import QtQuick
import RostrumKit

// The last render, over the viewport: the picture (fitted), where its file is, how long it took, and a close
// button. A failed render shows its error in red here and in the top bar; never a picture.
Rectangle {
    id: view
    readonly property string state_: backend.renderJob.state
    visible: state_ === "done" || state_ === "failed"
    color: Theme.sunken
    radius: Theme.radiusCtl
    clip: true

    MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onWheel: (w) => w.accepted = true }  // the viewport stays still under it
    Image {
        anchors { fill: parent; margins: Theme.pad; bottomMargin: bar.height + Theme.pad }
        visible: view.state_ === "done"
        source: backend.renderJob.picture
        fillMode: Image.PreserveAspectFit; smooth: true; cache: false; asynchronous: true
    }
    Text {
        visible: view.state_ === "failed"
        anchors.centerIn: parent; width: parent.width - 4 * Theme.pad
        horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
        text: backend.renderJob.note; color: Theme.danger; font.family: uiFont; font.pixelSize: Theme.body
    }
    Rectangle {
        id: bar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: Theme.header + Theme.gap; color: Theme.panel
        Text {
            anchors { left: parent.left; leftMargin: Theme.pad; right: close.left; rightMargin: Theme.pad
                      verticalCenter: parent.verticalCenter }
            elide: Text.ElideMiddle; font.family: uiFont; font.pixelSize: Theme.label
            text: view.state_ === "done" ? backend.renderJob.note + "  ·  " + backend.renderJob.path : "Render failed"
            color: view.state_ === "done" ? Theme.fg2 : Theme.danger
        }
        Button { id: close; text: "Close"; hint: "Esc"; kind: "ghost"
                 anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                 onClicked: backend.renderJob.dismiss() }
    }
}

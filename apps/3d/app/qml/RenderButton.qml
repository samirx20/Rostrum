import QtQuick
import RostrumKit

// The top bar's Render: one final (Cycles) picture of the playhead frame through the shot's camera. While a render
// runs, the button is replaced by what is happening (nothing greyed out).
Item {
    implicitWidth: running ? busy.implicitWidth : button.implicitWidth
    implicitHeight: Theme.button
    readonly property bool running: backend.renderJob.state === "running"

    Button {
        id: button
        visible: !parent.running
        text: "Render"; hint: "F12"
        onClicked: backend.renderStill()
    }
    Row {
        id: busy
        visible: parent.running
        anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.gap
        Rectangle {  // a slow pulse: the job is alive
            width: 8; height: 8; radius: 4; color: Theme.accent; anchors.verticalCenter: parent.verticalCenter
            SequentialAnimation on opacity {
                running: busy.visible; loops: Animation.Infinite
                NumberAnimation { from: 1; to: 0.3; duration: 600 }
                NumberAnimation { from: 0.3; to: 1; duration: 600 }
            }
        }
        Text { text: backend.renderJob.note; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body
               anchors.verticalCenter: parent.verticalCenter }
        Button { text: "Cancel"; kind: "ghost"; onClicked: backend.renderJob.cancel() }
    }
}

import QtQuick
import RostrumKit

// The header's Render (F12): opens the render sheet (the kit's export sheet in the settings panel's place: what, quality,
// size, save as, the measured time, Render). While a render runs, the button is replaced by what is happening (nothing
// greyed out); the sheet's own job shows in the kit's job chip.
Item {
    implicitWidth: running ? busy.implicitWidth : button.implicitWidth
    implicitHeight: Theme.button
    readonly property bool running: backend.renderJob.state === "running"

    Button {
        id: button
        visible: !parent.running
        text: "Render"; hint: "F12"; kind: "primary"
        onClicked: backend.exporter.openFor()
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

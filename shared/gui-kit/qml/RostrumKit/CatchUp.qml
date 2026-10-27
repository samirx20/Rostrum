import QtQuick
import "."

// The screen never lies (INTERACTION.md 1.21 rule 7): a soft "Updating" mark in a corner of a picture that is catching
// up, so an older picture is never presented as now. It shows only once `behind` has held for 0.2 s (a quick redraw
// never flickers it) and goes the moment the new picture is served. Bind it to the picture worker's `behind`
// (rostrum_gui/frames.py PictureWorker): CatchUp { behind: backend.frames.behind; anchors.right: …; anchors.bottom: … }
Rectangle {
    id: c
    property bool behind: false
    property bool late: false
    objectName: "catchUp"
    onBehindChanged: if (behind) wait.restart(); else { wait.stop(); late = false }
    Timer { id: wait; interval: 200; onTriggered: c.late = c.behind }
    visible: late
    enabled: false                         // only a sign: never takes a click meant for the canvas
    width: row.implicitWidth + 2 * Theme.grid; height: Theme.field - 4
    radius: height / 2
    color: Qt.rgba(0, 0, 0, 0.55)
    Row {
        id: row
        anchors.centerIn: parent
        spacing: Theme.grid
        Rectangle { width: 6; height: 6; radius: 3; color: Theme.fg2; anchors.verticalCenter: parent.verticalCenter }
        Text { text: "Updating"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
    }
}

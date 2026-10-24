import QtQuick
import RostrumKit

// One row of the Render page's queue (RenderPage.qml; a row of queue_rows.job_row). Line 1: the shot, its quality and
// size, and on the right what it is doing; line 2: the progress bar (running), its place (waiting), the time taken and
// folder (done) or the reason in red (failed, cancelled). Only what applies shows: ↑ ↓ on a waiting render that can
// move, ✕ on a waiting or running one; a click on a finished one shows its last frame over the viewport.
Rectangle {
    id: r
    required property var modelData
    property var queue
    property int waiting: 0
    readonly property string st: modelData.status
    readonly property bool live: st === "queued" || st === "running"
    readonly property bool bad: st === "failed" || st === "cancelled"
    height: 44; radius: Theme.radiusCtl
    color: st === "done" && area.containsMouse ? Theme.hover : st === "running" ? Theme.raised : "transparent"

    component Small: Text { color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label; elide: Text.ElideRight }

    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; enabled: r.st === "done"
                cursorShape: Qt.PointingHandCursor; onClicked: r.queue.show(r.modelData.id) }

    Text { id: name; x: Theme.gap; y: 5; width: Math.min(implicitWidth, r.width * 0.3); elide: Text.ElideRight
           text: r.modelData.shot; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body; font.weight: Font.DemiBold }
    Small { id: what; anchors { left: name.right; leftMargin: Theme.gap; baseline: name.baseline }
            width: Math.min(implicitWidth, r.width * 0.3); text: r.modelData.quality + " · " + r.modelData.size }
    Text {
        anchors { left: what.right; leftMargin: Theme.gap; right: buttons.left; rightMargin: Theme.gap; baseline: name.baseline }
        horizontalAlignment: Text.AlignRight; elide: Text.ElideRight; font.family: uiFont; font.pixelSize: Theme.label
        color: r.bad ? Theme.danger : r.st === "done" ? Theme.ok : Theme.fg2
        text: r.st === "running" ? "frames " + r.modelData.done + " of " + r.modelData.total + (r.modelData.left ? " · " + r.modelData.left : "")
              : r.st === "queued" ? (r.modelData.place === 0 ? "Next" : "Waiting · " + (r.modelData.place + 1) + " in line")
              : r.st === "done" ? "Done · " + r.modelData.took : r.modelData.word
    }
    Rectangle {    // progress
        visible: r.st === "running"
        x: Theme.gap; y: 28; width: buttons.x - 2 * Theme.gap; height: 4; radius: 2; color: Theme.sunken
        Rectangle { width: parent.width * (r.modelData.total ? r.modelData.done / r.modelData.total : 0); height: parent.height
                    radius: 2; color: Theme.accent }
    }
    Small {
        visible: r.st !== "running"
        x: Theme.gap; y: 24; width: buttons.x - 2 * Theme.gap
        elide: Text.ElideMiddle
        color: r.bad ? Theme.danger : Theme.fg3
        text: r.bad ? r.modelData.reason : r.st === "done" ? r.modelData.folder : r.modelData.total + " frames"
    }
    Row {
        id: buttons
        anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: parent.verticalCenter }
        spacing: 0
        IconButton { visible: r.st === "queued" && r.modelData.place > 0; glyph: "↑"; tip: "Earlier"
                     onClicked: r.queue.move(r.modelData.id, r.modelData.place - 1) }
        IconButton { visible: r.st === "queued" && r.modelData.place < r.waiting - 1; glyph: "↓"; tip: "Later"
                     onClicked: r.queue.move(r.modelData.id, r.modelData.place + 1) }
        IconButton { visible: r.live; glyph: "✕"; tip: "Cancel"; onClicked: r.queue.cancel(r.modelData.id) }
    }
}

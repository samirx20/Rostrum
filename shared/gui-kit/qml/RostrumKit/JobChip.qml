import QtQuick
import QtQuick.Controls as QQC
import "."

// The job chip in the top bar (INTERACTION.md 1.14): "Exporting Main.mp4 · 42 %" while a job runs; click it to see it,
// open its sheet or Cancel. A failed job stays, in red, with the reason, until read (Dismiss). A finished one says so,
// "Exported Main.mp4 ▾", until the next message (`doneShown`: the top bar knows the message): its list has Play and Show
// in folder (clickable things live in chips, never as loose words in the bar). Absent otherwise. `narrow` (the top bar
// ran short): the dot and the per cent (a finished job: the dot and "Done").
// `job`: an object with state, note, progress (0..1, or -1), cancellable, cancel(), dismiss(), setOpen(bool)
// (rostrum_gui.export_sheet.ExportSheet is one; so is a running action's, rostrum_gui.ack.AckJob, with no sheet to open:
// a job that can't be cancelled says so, never shows a Cancel that does nothing).
Rectangle {
    id: chip
    property var job
    property bool narrow: false
    property bool doneShown: false           // the job is done and the bar's message still says so (TopBar)
    readonly property string state_: job ? job.state : ""
    readonly property bool failed: state_ === "failed"
    readonly property bool done: state_ === "done" && doneShown && !!job && !!job.doneMessage
    readonly property bool shown: state_ === "running" || failed || done
    readonly property bool sheet: !!job && typeof job.setOpen === "function"      // an export's: "Open Export" (an action's run has none: ack.py)
    readonly property string pct: job && job.progress >= 0 ? Math.round(job.progress * 100) + " %" : ""
    // a finished job in the chip: its message when short ("Exported Main.mp4"), else the verb alone (a run of 120
    // pictures); the whole line is in its list
    readonly property string words: !shown ? "" : failed ? "Export failed"
                                    : done ? (job.doneMessage.length <= 40 ? job.doneMessage : job.doneWord || "Done")
                                    : (job.note || "Working") + (pct ? " · " + pct : "…")
    readonly property real fullWidth: shown ? full.implicitWidth + 2 * Theme.gap : 0
    readonly property real narrowWidth: shown ? small.implicitWidth + 2 * Theme.gap : 0
    visible: shown
    implicitWidth: shown ? (narrow ? narrowWidth : fullWidth) : 0
    implicitHeight: Theme.button
    radius: Theme.radiusCtl
    color: failed ? Qt.rgba(1, 0.42, 0.42, 0.14) : Theme.raised
    clip: true

    component Dot: Rectangle {
        width: 8; height: 8; radius: 4; color: chip.failed ? Theme.danger : chip.done ? Theme.ok : Theme.accent
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
    }
    Row {
        id: full
        x: Theme.gap; height: parent.height; spacing: Theme.gap
        opacity: chip.narrow ? 0 : 1
        Dot { }
        Text { anchors.verticalCenter: parent.verticalCenter; text: chip.words
               color: chip.failed ? Theme.danger : Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
        Chevron { visible: chip.done; anchors.verticalCenter: parent.verticalCenter; width: 8; open: pop.opened }
    }
    Row {
        id: small
        x: Theme.gap; height: parent.height; spacing: Theme.grid + 2
        opacity: chip.narrow ? 1 : 0
        Dot { }
        Text { anchors.verticalCenter: parent.verticalCenter; text: chip.failed ? "!" : chip.done ? "Done" : chip.pct || "…"
               color: chip.failed ? Theme.danger : Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
    }
    HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: pop.opened ? pop.close() : pop.open() }
    HoverTip { text: chip.narrow ? chip.words : ""; hovered: hover.hovered && !pop.opened }

    SmallPopup {     // the job: what it is doing or why it failed, and what can be done
        id: pop
        objectName: "jobPopup"
        y: chip.height + Theme.grid
        x: Math.min(0, chip.width - width)          // under the chip, its right edge on the chip's
        width: 300
        padding: Theme.pad
        background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
        contentItem: Column {
            spacing: Theme.gap
            Text { width: parent.width; wrapMode: Text.Wrap
                   text: !chip.job ? "" : chip.failed ? chip.job.note.replace(/^Error: [a-z_ ]+: /, "") : chip.done ? chip.job.note || chip.words : chip.words
                   color: chip.failed ? Theme.danger : Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
            Rectangle {
                visible: !chip.failed && !chip.done
                width: parent.width; height: 4; radius: 2; color: Theme.sunken
                Rectangle { height: parent.height; radius: 2; color: Theme.accent
                            width: chip.job && chip.job.progress >= 0 ? parent.width * chip.job.progress : parent.width / 4 }
            }
            Text { visible: !chip.failed && !chip.done && !!chip.job && !chip.job.cancellable; width: parent.width; wrapMode: Text.Wrap
                   text: "This can't be stopped part-way: it finishes by itself."
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            Text { visible: chip.failed; width: parent.width; wrapMode: Text.Wrap; text: "Nothing was replaced: the old file is kept."
                   color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            Row {
                anchors.right: parent.right; spacing: Theme.gap
                Button { visible: chip.sheet && !chip.done; text: "Open Export"; kind: "ghost"; onClicked: { pop.close(); chip.job.setOpen(true) } }
                Button { visible: chip.done; text: "Show in folder"; kind: "ghost"; onClicked: { pop.close(); chip.job.showInFolder() } }
                Button { visible: chip.done; text: "Play"; onClicked: { pop.close(); chip.job.play() } }
                Button { visible: !chip.failed && !chip.done && chip.job && chip.job.cancellable; text: "Cancel"
                         onClicked: { pop.close(); chip.job.cancel() } }
                Button { visible: chip.failed; text: "Dismiss"; onClicked: { pop.close(); chip.job.dismiss() } }
            }
        }
    }
}

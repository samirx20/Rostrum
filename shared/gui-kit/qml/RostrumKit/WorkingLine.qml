import QtQuick
import QtQuick.Controls as QQC
import "."

// "Still working" under the top bar (INTERACTION.md principle 2; rostrum_gui/ack.py): while an action a person started
// runs, a thin line moves along the bar's lower edge and its words ("Group · 200 layers…") hang at the right, from
// `lineAfter` ms in (0.2 s; at once for an action known to be long); from 1 s the job chip shows instead of the words,
// with Cancel for a job that can stop, else saying it can't be stopped part-way. Nothing shows for a quicker action.
// Everything is put in place when the run is armed, BEFORE it starts, and comes in by render-thread animators: they
// keep running while the action holds the GUI thread, which can change nothing on screen until it is done.
// Nothing here moves the bar's own items: the line lies over the bar's lower edge, the words and chip hang below its
// right end in the window's overlay (above the panels, as a popup is). `source`: the `ack`.
Item {
    id: w
    property var source: typeof ack !== "undefined" ? ack : null
    readonly property bool on: !!source && source.working
    readonly property int after: source ? source.lineAfter : 200
    readonly property int chipAfter: source ? source.chipAfter : 1000
    implicitHeight: 2
    visible: on
    // under the bar's right end, in the overlay's coordinates (worked out when a run is armed: the bar doesn't move)
    property real hangY: 0
    property real hangRight: 0
    function hangX(width) { return hangRight - width - Theme.gap }
    function place() {
        const ov = words.parent
        const p = w.mapToItem(ov, w.width, w.height)
        hangRight = p.x; hangY = p.y + Theme.grid
    }

    Item {      // the line
        id: line
        anchors.fill: parent
        clip: true
        opacity: 0
        Rectangle { anchors.fill: parent; color: Theme.accentSoft }
        Rectangle { id: runner; objectName: "workingRunner"; width: Math.max(64, w.width / 6); height: parent.height
                    radius: 1; color: Theme.accent; x: -width }
    }
    Rectangle {     // its words, until the chip
        id: words
        objectName: "workingWords"
        parent: QQC.Overlay.overlay ? QQC.Overlay.overlay : w
        x: w.hangX(width); y: w.hangY; visible: false
        width: wordsText.implicitWidth + 2 * Theme.gap; height: Theme.popupRow - 4
        radius: Theme.radiusCtl; color: Theme.raised; border.color: Theme.popupEdge
        opacity: 0
        Text { id: wordsText; anchors.centerIn: parent; text: w.source ? w.source.note : ""
               color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
    }
    Item {          // the job chip, over the words (wider than they are: it covers them)
        id: chipBox
        objectName: "workingChip"
        z: 1                        // over the words
        parent: QQC.Overlay.overlay ? QQC.Overlay.overlay : w
        x: w.hangX(width); y: w.hangY; visible: false
        width: chip.width; height: chip.height
        opacity: 0
        enabled: false              // takes clicks only once shown (a turn-by-turn job leaves the GUI thread free for it)
        JobChip { id: chip; job: w.source ? w.source.job : null; width: implicitWidth; height: implicitHeight }
    }
    Timer { id: chipLive; interval: w.chipAfter; onTriggered: chipBox.enabled = true }

    // a value below 0 is drawn as 0: running linearly from -after/50 to 1 over after + 50 ms, each shows at `after`
    OpacityAnimator { id: lineIn; target: line; from: -w.after / 50; to: 1; duration: w.after + 50 }
    OpacityAnimator { id: wordsIn; target: words; from: -w.after / 50; to: 1; duration: w.after + 50 }
    OpacityAnimator { id: chipIn; target: chipBox; from: -w.chipAfter / 80; to: 1; duration: w.chipAfter + 80 }
    XAnimator { id: running; target: runner; from: -runner.width; to: w.width; duration: 1100
                loops: Animation.Infinite; easing.type: Easing.InOutQuad }
    onOnChanged: {
        for (const a of [lineIn, wordsIn, chipIn, running]) a.stop()
        line.opacity = 0; words.opacity = 0; chipBox.opacity = 0; chipBox.enabled = false; chipLive.stop()
        words.visible = chipBox.visible = on        // (in the overlay: not hidden with this item)
        if (!on) return
        place()
        lineIn.start(); chipIn.start(); chipLive.start()
        if (!Theme.reduceMotion) running.start()
        wordsIn.start()
    }
}

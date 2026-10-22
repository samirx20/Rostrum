import QtQuick
import "."

// The agent chip in the top bar (INTERACTION.md 1.18): "● Claude is working · 6 changes" while an agent's changes
// keep arriving, then "● Claude: 12 changes · Review · Undo all" after 5 s of quiet. Absent when there is nothing to
// say. `narrow` (the top bar ran short): the dot and the count only, hover says the rest.
// Reads `bridge.agent.chip` (rostrum_gui/agent_watch.py). Review → review(session) (the top bar opens History on
// that run, through bridge.agent.historyAsked); Keep folds the chip away (not a change); Undo all → bridge.undoRun(session), ONE step.
Rectangle {
    id: chip
    property var bridge
    property bool narrow: false
    readonly property var info: bridge && bridge.agent ? bridge.agent.chip : ({ state: "" })
    readonly property bool working: info.state === "working"
    readonly property real fullWidth: full.implicitWidth + 2 * Theme.gap
    readonly property real narrowWidth: small.implicitWidth + 2 * Theme.gap
    signal review(string session)
    function openReview() { review(info.session); bridge.agent.askHistory(info.session) }   // the shell opens History
    visible: info.state !== ""
    implicitWidth: info.state !== "" ? (narrow ? narrowWidth : fullWidth) : 0
    implicitHeight: Theme.button
    radius: Theme.radiusCtl
    color: Theme.agentSoft
    clip: true

    property real breath: 1                 // a slow breath on the dot while the agent works; still when done
    SequentialAnimation on breath {
        running: chip.working; loops: Animation.Infinite
        NumberAnimation { to: 0.35; duration: 700; easing.type: Easing.InOutSine }
        NumberAnimation { to: 1; duration: 700; easing.type: Easing.InOutSine }
    }
    component Dot: Rectangle {
        width: 8; height: 8; radius: 4; color: Theme.agent
        opacity: chip.working ? chip.breath : 1
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
    }
    component Act: Text {                     // a word to click: Review, Keep, Undo all
        signal clicked()
        anchors.verticalCenter: parent ? parent.verticalCenter : undefined
        height: Math.max(implicitHeight, 16); verticalAlignment: Text.AlignVCenter     // a click target of at least 16 px
        color: hover.hovered ? Theme.fg : Theme.agent
        font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
        HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: parent.clicked() }
    }

    Row {  // the whole chip
        id: full
        x: Theme.gap; height: parent.height
        spacing: Theme.gap
        opacity: chip.narrow ? 0 : 1; enabled: !chip.narrow     // measured always, shown when there is room
        Dot { }
        Text { anchors.verticalCenter: parent.verticalCenter; text: chip.info.text || ""
               color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
        Act { visible: !chip.working; text: "Review"; onClicked: chip.openReview() }
        Act { visible: !chip.working; text: "Keep"; onClicked: chip.bridge.agent.keep() }
        Act { visible: !chip.working; text: "Undo all"; onClicked: chip.bridge.undoRun(chip.info.session) }
    }
    Row {  // narrow: dot and count
        id: small
        x: Theme.gap; height: parent.height
        spacing: Theme.grid + 2
        opacity: chip.narrow ? 1 : 0; enabled: chip.narrow
        Dot { }
        Text { anchors.verticalCenter: parent.verticalCenter; text: String(chip.info.count || 0)
               color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
        HoverHandler { id: smallHover }
        TapHandler { onTapped: chip.openReview() }
        HoverTip { text: chip.narrow ? (chip.info.text || "") + (chip.working ? "" : "  ·  click to review") : ""
                   hovered: smallHover.hovered }
    }
}

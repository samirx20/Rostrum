import QtQuick
import "."

// The agent chip in the top bar (INTERACTION.md 1.18): small, "● Claude · 6 changes ▾" (the dot breathes while the
// agent works). Absent when there is nothing to say. `narrow` (the top bar ran short): the dot and the count.
// A click opens its dropdown: the agent's sentence (its last change, or what it said), then Review · Keep · Undo all
// once the run has gone quiet. Reads `bridge.agent.chip` (rostrum_gui/agent_watch.py). Review → review(session) (the
// top bar opens History on that run, through bridge.agent.historyAsked); Keep folds the chip away (not a change);
// Undo all → bridge.undoRun(session), ONE step.
Rectangle {
    id: chip
    property var bridge
    property bool narrow: false
    readonly property var info: bridge && bridge.agent ? bridge.agent.chip : ({ state: "" })
    readonly property bool working: info.state === "working"
    readonly property real fullWidth: full.implicitWidth + 2 * Theme.gap
    readonly property real narrowWidth: small.implicitWidth + 2 * Theme.gap
    signal review(string session)
    function openReview() { pop.close(); review(info.session); bridge.agent.askHistory(info.session) }   // the shell opens History
    visible: info.state !== ""
    implicitWidth: info.state !== "" ? (narrow ? narrowWidth : fullWidth) : 0
    implicitHeight: Theme.button
    radius: Theme.radiusCtl
    color: area.containsMouse || pop.opened ? Theme.hover : Theme.agentSoft
    clip: true
    onVisibleChanged: if (!visible) pop.close()

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

    Row {  // the whole chip
        id: full
        x: Theme.gap; height: parent.height
        spacing: Theme.gap
        opacity: chip.narrow ? 0 : 1     // measured always, shown when there is room
        Dot { }
        Text { anchors.verticalCenter: parent.verticalCenter; text: chip.info.text || ""
               color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
        Chevron { anchors.verticalCenter: parent.verticalCenter; open: pop.opened }
    }
    Row {  // narrow: dot and count
        id: small
        x: Theme.gap; height: parent.height
        spacing: Theme.grid + 2
        opacity: chip.narrow ? 1 : 0
        Dot { }
        Text { anchors.verticalCenter: parent.verticalCenter; text: String(chip.info.count || 0)
               color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.label }
    }
    MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: pop.opened ? pop.close() : pop.openAt(chip) }
    HoverTip { text: chip.narrow && !pop.opened ? chip.info.text || "" : ""; hovered: area.containsMouse }

    Popover {
        id: pop
        Text {   // the agent's sentence: up to 360 px wide, then it wraps
            visible: text !== ""; text: chip.info.say || ""
            width: Math.min(360, sayWidth.advanceWidth + 1)
            wrapMode: Text.Wrap; maximumLineCount: 4; elide: Text.ElideRight
            color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
            TextMetrics { id: sayWidth; font.family: uiFont; font.pixelSize: Theme.body; text: chip.info.say || "" }
        }
        Row {
            visible: !chip.working
            spacing: Theme.gap
            Button { text: "Review"; onClicked: chip.openReview() }
            Button { text: "Keep"; onClicked: { pop.close(); chip.bridge.agent.keep() } }
            Button { text: "Undo all"; onClicked: { pop.close(); chip.bridge.undoRun(chip.info.session) } }
        }
    }
}

import QtQuick
import "."

// A 2 px outline round something an agent just changed (the agent colour), or that the person's own undo / redo just
// took back or put again (the accent colour: `bridge.agent.flashMine`); it fades out over 1 s and is gone
// (INTERACTION.md 1.18, 1.21 rule 9: undo you can see). Place one per id in `bridge.agent.flash` over that item's rect on screen, in this item's
// parent's coordinates: ChangeOutline { x: r.x; y: r.y; width: r.width; height: r.height }. `again()` shows it anew.
Item {
    id: o
    property int pad: 2                      // a little outside the item, so the item itself stays readable
    // whose change it shows: bound to the app's bridge (`backend` in both apps); no bridge (a kit demo): the agent's
    property bool mine: typeof backend !== "undefined" && backend && backend.agent ? backend.agent.flashMine === true : false
    property color tint: "transparent"     // an app's own colour for this outline (unset: accent for the person's, agent's colour)
    enabled: false                           // never takes a click: it is only a sign
    function again() { fade.restart() }
    Component.onCompleted: fade.start()
    Rectangle {
        anchors.fill: parent; anchors.margins: -o.pad
        color: "transparent"; border.width: 2; border.color: o.tint.a > 0 ? o.tint : o.mine ? Theme.accent : Theme.agent; radius: Theme.radiusCtl - 2
    }
    NumberAnimation { id: fade; target: o; property: "opacity"; from: 1; to: 0; duration: 1000
                      easing.type: Easing.InQuad
                      onStarted: o.visible = true
                      onFinished: o.visible = false }
}

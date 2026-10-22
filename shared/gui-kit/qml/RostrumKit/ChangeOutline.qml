import QtQuick
import "."

// A 2 px outline in the agent colour round something an agent just changed; it fades out over 1 s and is gone
// (INTERACTION.md 1.18). Place one per id in `bridge.agent.flash` over that item's rect on screen, in this item's
// parent's coordinates: ChangeOutline { x: r.x; y: r.y; width: r.width; height: r.height }. `again()` shows it anew.
Item {
    id: o
    property int pad: 2                      // a little outside the item, so the item itself stays readable
    enabled: false                           // never takes a click: it is only a sign
    function again() { fade.restart() }
    Component.onCompleted: fade.start()
    Rectangle {
        anchors.fill: parent; anchors.margins: -o.pad
        color: "transparent"; border.width: 2; border.color: Theme.agent; radius: Theme.radiusCtl - 2
    }
    NumberAnimation { id: fade; target: o; property: "opacity"; from: 1; to: 0; duration: 1000
                      easing.type: Easing.InQuad
                      onStarted: o.visible = true
                      onFinished: o.visible = false }
}

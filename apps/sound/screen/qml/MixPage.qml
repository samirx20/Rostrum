import QtQuick
import RostrumKit

// The Mix page: a strip per track, then per bus, left to right, the master at the right end, the listen pictures below.
Panel {
    id: page
    title: "Mix"

    Item {
        anchors.fill: parent
        Flickable {   // the track strips (scroll sideways when there are many)
            id: scroller
            anchors { left: parent.left; top: parent.top; bottom: listen.top; bottomMargin: Theme.gap }
            width: Math.min(parent.width - master.width - Theme.gap, row.width)
            contentWidth: row.width; clip: true; boundsBehavior: Flickable.StopAtBounds
            Row {
                id: row
                height: scroller.height
                spacing: Theme.gap
                Repeater { id: strips; model: mixer.tracks; delegate: MixStrip { height: row.height } }
                Repeater { model: mixer.buses; delegate: MixStrip { height: row.height } }   // buses, before the master
                Item {
                    width: addBus.width; height: row.height
                    Button { id: addBus; text: "+ Bus"; kind: "ghost"; onClicked: mixer.addBus() }
                }
            }
        }
        Text {
            visible: strips.count === 0
            anchors.centerIn: scroller
            text: "No tracks yet — add one with Ctrl+K"
            color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.title
        }
        MixMaster { id: master; anchors { right: parent.right; top: parent.top; bottom: listen.top; bottomMargin: Theme.gap } }
        MixListen { id: listen; anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: implicitHeight }
    }
}

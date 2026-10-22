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
            width: Math.min(parent.width - master.width - Theme.gap - (plug.visible || duck.visible ? plug.width + Theme.gap : 0), row.width)
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
            text: "No tracks yet. Add one with + Track at the top."
            color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.title
        }
        Rectangle {   // the selected plug-in effect's settings (only while one is selected)
            id: plug
            readonly property var panel: mixer.plugins.selectedPanel
            visible: !!panel
            width: 280; color: Theme.app; radius: Theme.radiusPanel
            anchors { right: master.left; rightMargin: Theme.gap; top: parent.top; bottom: listen.top; bottomMargin: Theme.gap }
            Flickable {
                anchors { fill: parent; margins: Theme.gap + 2 }
                contentHeight: settings.height; clip: true; boundsBehavior: Flickable.StopAtBounds
                PluginSettings { id: settings; ownerId: plug.panel ? plug.panel.owner : "" }
            }
        }
        Rectangle {   // the open duck's settings (only while a duck is open; the panel closes with the track's selection)
            id: duck
            visible: !!mixer.ducks.panel.id
            width: plug.width; color: Theme.app; radius: Theme.radiusPanel
            anchors { right: master.left; rightMargin: Theme.gap; top: parent.top; bottom: listen.top; bottomMargin: Theme.gap }
            Flickable {
                anchors { fill: parent; margins: Theme.gap + 2 }
                contentHeight: duckSettings.height; clip: true; boundsBehavior: Flickable.StopAtBounds
                DuckPanel { id: duckSettings }
            }
        }
        MixMaster { id: master; anchors { right: parent.right; top: parent.top; bottom: listen.top; bottomMargin: Theme.gap } }
        MixListen { id: listen; anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: implicitHeight }
    }
}

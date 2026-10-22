import QtQuick
import RostrumKit

// The Mixer in the bottom dock (DESIGN.md §2.2, W3): a strip per track, then per group (bus), left to right, scrolling
// sideways when they don't fit; the Master pinned at the right (fader, meter, loudness). The selected plug-in effect's
// settings or the open duck sit beside the master while there is one. Clicking a strip selects its track everywhere.
Rectangle {
    id: page
    color: Theme.panel; radius: Theme.radiusPanel; clip: true

    Item {
        anchors { fill: parent; margins: Theme.gap }
        Flickable {   // the track strips (scroll sideways when there are many)
            id: scroller
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
            width: Math.min(parent.width - master.width - Theme.gap - (plug.visible || duck.visible ? plug.width + Theme.gap : 0), row.width)
            contentWidth: row.width; clip: true; boundsBehavior: Flickable.StopAtBounds
            Row {
                id: row
                height: scroller.height
                spacing: Theme.gap
                Repeater { id: strips; model: mixer.tracks; delegate: MixStrip { height: row.height } }
                Repeater { model: mixer.buses; delegate: MixStrip { height: row.height } }   // groups, before the master
                Item {   // "+ Group" at the end of the strips, level with the strip names
                    width: addGroup.width; height: row.height
                    Button { id: addGroup; y: Theme.gap + 2 + (22 - height) / 2; text: "+ Group"; kind: "ghost"
                             tip: "New group"; help: "A shared channel several tracks play into (a bus)"; onClicked: mixer.addBus() }
                }
            }
        }
        Text {
            visible: strips.count === 0
            anchors.centerIn: scroller
            text: "Your tracks' faders will be here."
            color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.title
        }
        Rectangle {   // the selected plug-in effect's settings (only while one is selected)
            id: plug
            readonly property var panel: mixer.plugins.selectedPanel
            visible: !!panel
            width: 280; color: Theme.app; radius: Theme.radiusPanel
            anchors { right: master.left; rightMargin: Theme.gap; top: parent.top; bottom: parent.bottom }
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
            anchors { right: master.left; rightMargin: Theme.gap; top: parent.top; bottom: parent.bottom }
            Flickable {
                anchors { fill: parent; margins: Theme.gap + 2 }
                contentHeight: duckSettings.height; clip: true; boundsBehavior: Flickable.StopAtBounds
                DuckPanel { id: duckSettings }
            }
        }
        MixMaster { id: master; anchors { right: parent.right; top: parent.top; bottom: parent.bottom } }
    }
}

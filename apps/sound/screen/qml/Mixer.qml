import QtQuick
import RostrumKit

// The Mixer in the bottom dock (DESIGN.md §2.2, W3; mockup s51 #2): strips side by side from the left (tracks, then
// groups; "+ Group" sits on the Master strip), the Master strip right after them, and the room left over to the right is the loudness
// panel (MixLoudness). Too many strips: they scroll sideways and the Master stays pinned after the visible ones. The
// selected plug-in effect's settings or the open duck sit at the right end while there is one, taking room from the
// loudness panel. Clicking a strip selects its track everywhere.
Rectangle {
    id: page
    color: Theme.panel; radius: Theme.radiusPanel; clip: true
    // The plug-in scan (the chips drop a plug-in's vendor from its name) starts when the Mixer first shows, not when it
    // is made ahead (Dock.qml).
    onVisibleChanged: if (visible) mixer.plugins.scan()
    Component.onCompleted: if (visible) mixer.plugins.scan()
    readonly property real loudMin: 200          // the loudness panel's least width: strips come first, it takes what is left
    // (layout reads conditions, never `visible`: that turns false while the Editor shows, and the Mixer was laid out
    // again on every X)
    readonly property bool side: !!plug.panel || !!mixer.ducks.panel.id
    readonly property real head: {   // the tallest strip's parts above its fader: every fader, the master's too, starts there
        let m = master.naturalHead
        for (let i = 0; i < row.children.length; i++)
            if (row.children[i].naturalHead !== undefined) m = Math.max(m, row.children[i].naturalHead)
        return m
    }

    Item {
        id: body
        anchors { fill: parent; margins: Theme.gap }
        Flickable {   // tracks and groups (scroll sideways when there are many)
            id: scroller
            anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
            readonly property real room: body.width - master.width - Theme.gap - page.loudMin - Theme.gap
                                         - (page.side ? plug.width + Theme.gap : 0)
            // whole strips only: when they overflow, the view ends on a strip's edge, never through one
            width: row.width <= room ? row.width
                 : Math.max(0, Math.floor((room + Theme.gap) / (master.width + Theme.gap)) * (master.width + Theme.gap) - Theme.gap)
            contentWidth: row.width; clip: true; boundsBehavior: Flickable.StopAtBounds
            readonly property bool over: contentWidth > width + 1     // the strips overflow: the scroll bar shows
            flickableDirection: Flickable.HorizontalFlick
            Row {
                id: row
                height: scroller.height - (scroller.over ? bar.height + 2 : 0)
                spacing: Theme.gap
                Item {   // an empty song: the hint where the strips will be
                    visible: strips.count === 0; width: 220; height: row.height
                    Text { anchors.centerIn: parent; width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                           text: "Your tracks' faders will be here."; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.title }
                }
                Repeater { id: strips; model: mixer.tracks; delegate: MixStrip { height: row.height; head: page.head } }
                Repeater { model: mixer.buses; delegate: MixStrip { height: row.height; head: page.head } }   // groups, before the master
            }
            Rectangle {   // where the view is along the strips, only while they overflow (drag or wheel to scroll)
                id: bar
                visible: scroller.over
                y: scroller.height - height; height: Theme.scrollWidth; radius: height / 2; color: Theme.line
                x: scroller.contentX + scroller.contentX / scroller.contentWidth * scroller.width
                width: scroller.width * scroller.width / scroller.contentWidth
            }
        }
        MixStrip {   // the Master: right after the last strip, pinned there when the strips scroll
            id: master
            model: mixer.master; head: page.head
            anchors { left: scroller.right; leftMargin: scroller.width > 0 ? Theme.gap : 0; top: parent.top; bottom: parent.bottom
                      bottomMargin: scroller.over ? bar.height + 2 : 0 }   // level with the strips above the scroll bar
        }
        MixLoudness {
            anchors { left: master.right; leftMargin: Theme.gap; right: page.side ? plug.left : parent.right
                      rightMargin: page.side ? Theme.gap : 0; top: parent.top; bottom: parent.bottom }
        }
        Rectangle {   // the selected plug-in effect's settings (only while one is selected)
            id: plug
            readonly property var panel: mixer.plugins.selectedPanel
            visible: !!panel
            width: Theme.sidePanel; color: Theme.app; radius: Theme.radiusPanel
            anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
            Flickable {
                anchors { fill: parent; margins: Theme.gap + 2 }
                contentHeight: settings.height; clip: true; boundsBehavior: Flickable.StopAtBounds
                Loader {   // made while a plug-in effect is selected (a Mixer made ahead, hidden, starts no plug-in scan)
                    id: settings
                    width: parent.width; active: !!plug.panel
                    sourceComponent: PluginSettings { ownerId: plug.panel ? plug.panel.owner : "" }
                }
            }
        }
        Rectangle {   // the open duck's settings (only while a duck is open; the panel closes with the track's selection)
            id: duck
            visible: !!mixer.ducks.panel.id
            width: plug.width; color: Theme.app; radius: Theme.radiusPanel
            anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
            Flickable {
                anchors { fill: parent; margins: Theme.gap + 2 }
                contentHeight: duckSettings.height; clip: true; boundsBehavior: Flickable.StopAtBounds
                DuckPanel { id: duckSettings }
            }
        }
    }
}

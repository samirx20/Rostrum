import QtQuick
import RostrumKit

// The settings panel while nothing is selected: the song (DESIGN.md decision 4, W1) — titled "Song" (its name is
// the top bar's tab, renamed there). First the song's timeline as lists (SongList.qml: Bar 1's tempo and time
// signature edited in place, every tempo, time signature and key change and the sections; a click selects one and
// moves the playhead there; "+" adds one at the playhead where that is valid), then the song's own settings under
// "Song": its length (the rest behind More). The arrangement header (SongReadout.qml) stays the quick way to the
// tempo, time signature and key; this panel is where every change is seen and added. The Song rows are the kit's
// InspectorRow on `songPanel` (song_panel.py: the `doc.set` fields); each change is one undo step.
Panel {
    id: p
    Text { id: kind; text: songPanel.mainMix === "main" ? "Song · Main mix" : "Song"   // its name is the top bar's tab
           color: songPanel.mainMix === "main" ? Theme.accent : Theme.fg; font.family: uiFont
           font.pixelSize: Theme.heading; font.weight: Font.DemiBold }
    Flickable {
        anchors { left: parent.left; right: parent.right; top: kind.bottom; bottom: parent.bottom; topMargin: Theme.gap }
        contentHeight: list.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: list
            width: parent.width
            ActionsSection { width: parent.width; hub: backend.actions }   // a time range's actions (Make a section …)
            Item {   // not the main mix yet: the one action for it (absent once it is, the title says so)
                visible: songPanel.mainMix === "other"
                width: parent.width; height: visible ? Theme.row + Theme.grid : 0
                Button { anchors.verticalCenter: parent.verticalCenter; text: "Make this the main mix"
                         onClicked: songPanel.makeMain() }
            }
            SongList { width: parent.width }      // ends on the "Song" heading for the rows below
            Repeater { model: songPanel.rows; delegate: InspectorRow { bridge: songPanel } }
        }
    }
}

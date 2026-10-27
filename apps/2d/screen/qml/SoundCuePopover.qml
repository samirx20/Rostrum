import QtQuick
import QtQuick.Controls as QQC
import RostrumKit

// Add a sound here… (UX_SPEC 3.28 Sync sound): one layer selected → this popover under the context bar lists a note / hit
// on the song's instruments first, then the person's recordings (typed words search Sound's library too); typed words narrow it as you type; a click ties the sound to the
// layer's start (backend.cuePick, screen2d/sound_cue_pick.py) and closes it. Esc or a click outside closes it.
SmallPopup {     // Esc: the window's one Esc (OpenPopups); a click outside closes it
    id: pop
    readonly property var cp: backend.cuePick
    width: 360
    modal: true; dim: false
    padding: Theme.pad
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    Connections { target: pop.cp; function onOpened() { pop.open() } }
    onOpened: search.input.forceActiveFocus()       // type at once
    contentItem: Column {
        spacing: Theme.gap
        Text { width: parent.width; text: "Add a sound to " + pop.cp.what; color: Theme.fg; font.family: uiFont
               font.pixelSize: Theme.body; font.weight: Font.DemiBold; elide: Text.ElideRight }
        TextField { id: search; objectName: "cueSearch"; width: parent.width; value: pop.cp.words; placeholder: "Search recordings (cello, tap …)"
                    onEdited: (v) => pop.cp.search(v)
                    // as you type, like the Library's search: the worker keeps only the newest words (sound_cue_pick.py)
                    Connections { target: search.input; function onTextChanged() { if (search.input.activeFocus) pop.cp.search(search.input.text) } } }
        Text { objectName: "cueStatus"; visible: pop.cp.searching || pop.cp.sounds.length === 0; width: parent.width; wrapMode: Text.Wrap
               text: pop.cp.searching ? "Searching…" : "No sounds match. Try fewer words, or add a sound folder in RostrumSound."
               color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
        ListView {
            id: list
            visible: pop.cp.sounds.length > 0
            width: parent.width; height: Math.min(contentHeight, Theme.row * 8)
            clip: true; model: pop.cp.sounds; boundsBehavior: Flickable.StopAtBounds
            delegate: Rectangle {
                id: rowItem
                required property var modelData
                width: list.width - (bar.needed ? 8 : 0); height: Theme.row; radius: Theme.radiusCtl
                color: hover.hovered ? Theme.active : "transparent"
                HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
                Text { x: Theme.grid; width: parent.width - hint.width - 3 * Theme.grid; height: parent.height
                       verticalAlignment: Text.AlignVCenter; text: rowItem.modelData.label; color: Theme.fg
                       font.family: uiFont; font.pixelSize: Theme.body; elide: Text.ElideRight }
                Text { id: hint; anchors.right: parent.right; anchors.rightMargin: Theme.grid; height: parent.height
                       verticalAlignment: Text.AlignVCenter; text: rowItem.modelData.hint; color: Theme.fg3
                       font.family: uiFont; font.pixelSize: Theme.label }
                TapHandler { onTapped: if (pop.cp.pick(rowItem.modelData.path)) pop.close() }
            }
            VScrollBar { id: bar; flick: list; anchors.right: parent.right; height: parent.height }
        }
    }
}

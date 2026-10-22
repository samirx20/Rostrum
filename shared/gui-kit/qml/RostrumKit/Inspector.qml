import QtQuick
import "."

// The selected item's settings: ONE generic list of InspectorRow built from the item kind's field operation
// (bridge.rows). Nothing in here knows about cameras or lights.
// A bridge with rows by importance (bridge.sectioned) also gets a "Find a setting" box under the name (Ctrl F
// focuses it, Esc clears it; bridge.setSearch), "No setting matches" when nothing does, and the jump to a field:
// bridge.revealField opens its group, then `fieldRevealed` scrolls here, flashes the row and focuses its widget.
Panel {
    id: panel
    property var bridge
    property bool keyMarks: false        // an app with keys: rows show key marks (see InspectorRow)
    readonly property bool finds: !!panel.bridge.sectioned
    title: "Inspector"

    Text { id: name; text: panel.bridge.selectedItem.label; color: Theme.fg; font.family: uiFont
           font.pixelSize: Theme.heading; font.weight: Font.DemiBold
           anchors.left: parent.left; anchors.right: parent.right; elide: Text.ElideRight }
    Text { id: kind; text: Theme.sentence(panel.bridge.selectedItem.kind); color: Theme.fg3; font.family: uiFont
           font.pixelSize: Theme.body
           anchors.top: name.bottom; anchors.topMargin: 2 }
    FieldFrame {
        id: find
        objectName: "findSetting"
        visible: panel.finds && panel.bridge.selected !== ""
        anchors { left: parent.left; right: parent.right; top: kind.bottom; topMargin: Theme.gap }
        height: visible ? Theme.field : 0
        editable: true
        placeholder: "Find a setting"
        text: panel.finds ? panel.bridge.search : ""
        Connections { target: find.input; function onTextEdited() { panel.bridge.setSearch(find.input.text) } }
        onEscaped: panel.bridge.setSearch("")
        trailing: KeyHint { text: "Ctrl F"; visible: find.input.text === "" && !find.input.activeFocus }
    }
    Shortcut { sequence: StandardKey.Find; enabled: find.visible && panel.visible
               onActivated: { find.input.forceActiveFocus(); find.input.selectAll() } }
    Flickable {      // a long inspector scrolls (wheel or touch, thin bar in the panel's margin); a short one never moves
        id: scroller
        objectName: "inspectorScroll"    // scripted steps scroll it (an app's `inspectorscroll` step)
        anchors { left: parent.left; right: parent.right; top: find.visible ? find.bottom : kind.bottom
                  bottom: parent.bottom; topMargin: Theme.gap }   // scrolled rows stop short of the subtitle
        contentHeight: list.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: list
            width: parent.width
            Repeater {
                id: rowsView
                model: panel.bridge.rows
                delegate: InspectorRow { bridge: panel.bridge; keyMarks: panel.keyMarks }
            }
        }
        Text { visible: panel.finds && panel.bridge.nothingFound; text: "No setting matches"; y: Theme.grid
               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
    }
    VScrollBar { flick: scroller }

    // The jump to a field: after its group's reveal has eased open, scroll the row into view, flash it, focus it.
    Connections {
        target: panel.bridge; ignoreUnknownSignals: true
        function onFieldRevealed(field) { reveal.field = field; reveal.restart() }
    }
    Timer {
        id: reveal
        property string field: ""
        interval: Theme.reveal + 40
        onTriggered: {
            for (let i = 0; i < rowsView.count; i++) {
                const r = rowsView.itemAt(i)
                if (!r || r.model.id !== field || r.model.row !== "param") continue
                const top = r.y, bottom = r.y + r.height
                if (top < scroller.contentY || bottom > scroller.contentY + scroller.height)
                    scroller.contentY = Math.max(0, Math.min(top - Theme.row, scroller.contentHeight - scroller.height))
                r.flash(); r.focusWidget()
                return
            }
        }
    }
}

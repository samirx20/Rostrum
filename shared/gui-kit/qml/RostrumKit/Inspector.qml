import QtQuick
import "."

// The selected item's settings: ONE generic list of InspectorRow built from the item kind's field operation
// (bridge.rows). Nothing in here knows about cameras or lights.
// A bridge with rows by importance (bridge.sectioned) also gets a "Find a setting" box under the name (Ctrl F
// focuses it, Esc clears it; bridge.setSearch), "No setting matches" when nothing does, and the jump to a field:
// bridge.revealField opens its group, then `fieldRevealed` scrolls here, flashes the row and focuses its widget.
// Several items of different kinds: a line per kind at the top ("3 layers ›", bridge.narrowLines); a click keeps only
// that kind (bridge.narrowTo). The last line: who changed the selection last and when (bridge.lastChanged); a click
// opens History (bridge.agent.askHistory). Both are absent when there is nothing to say.
// The name shows once: the kind line is absent when it says the same as the name ("Camera" / "Camera").
// `above`: an app's own group first, above the rows (2D: a rig's Poses); `below`: one under them; `sheets` (Panel): a
// sheet that takes the whole panel's place while shown (2D: Lip sync, Add blinks). No caption over the panel.
// An app with `effects: true` (after rostrum_gui.effects.attach(bridge, spec)) also gets the "Effects (n) +" section under the rows (EffectsRow).
Panel {
    id: panel
    property var bridge
    property bool effects: false         // the "Effects (n) +" section (an app that called rostrum_gui.effects.attach)
    property bool keyMarks: false        // an app with keys: rows show key marks (see InspectorRow)
    property var highlight: []           // field ids marked as in focus (2D: the settings whose keys are picked)
    property alias above: aboveSlot.data // an app's own group above the rows, in the same scroll (2D: a rig's Poses)
    property alias below: belowSlot.data // an app's own group under the rows, in the same scroll (2D: "Paint on …")
    readonly property string kindText: panel.bridge.selectedItem.kindLabel || Theme.sentence(panel.bridge.selectedItem.kind)
    readonly property bool finds: !!panel.bridge.sectioned
    property int tick: 0                 // "2 min ago" ages while the panel stays open
    readonly property var narrow: { panel.bridge.selection; return panel.bridge.narrowLines ? panel.bridge.narrowLines() : [] }
    readonly property var last: { panel.bridge.selection; panel.bridge.historyCount; panel.tick; return panel.bridge.lastChanged ? panel.bridge.lastChanged() : ({}) }   // a page bridge (Brush, Settings) has neither
    readonly property bool hasLast: panel.bridge.selected !== "" && !!panel.last.who

    NameLabel { id: name; text: panel.bridge.selectedItem.label; font.pixelSize: Theme.heading; font.weight: Font.DemiBold
                anchors.left: parent.left; anchors.right: parent.right }   // a long name, whole on hover
    Text { id: kind; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body
           readonly property bool same: panel.kindText.toLowerCase() === String(name.text || "").trim().toLowerCase()
           text: same ? "" : panel.kindText; visible: !same
           height: same ? 0 : implicitHeight
           anchors.top: name.bottom; anchors.topMargin: same ? 0 : 2 }
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
    Shortcut { sequences: [StandardKey.Find]; enabled: find.visible && panel.visible
               onActivated: { find.input.forceActiveFocus(); find.input.selectAll() } }
    Flickable {      // a long inspector scrolls (wheel or touch, thin bar in the panel's margin); a short one never moves
        id: scroller
        objectName: "inspectorScroll"    // scripted steps scroll it (an app's `inspectorscroll` step)
        anchors { left: parent.left; right: parent.right; top: find.visible ? find.bottom : kind.bottom
                  bottom: panel.hasLast ? lastLine.top : parent.bottom; topMargin: Theme.gap }   // scrolled rows stop short of the subtitle
        contentHeight: list.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: list
            width: parent.width
            Column {  // mixed kinds: one line per kind, a click narrows the selection to it
                width: parent.width; visible: panel.narrow.length > 0
                Text { text: "Show only"; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label
                       height: Theme.rowDense; verticalAlignment: Text.AlignVCenter }
                Repeater {
                    model: panel.narrow
                    delegate: Item {
                        id: nline
                        required property var modelData
                        width: list.width; height: Theme.row
                        Rectangle { anchors.fill: parent; radius: Theme.radiusCtl; color: Theme.hover; visible: narrowArea.containsMouse }
                        Text { anchors.left: parent.left; anchors.leftMargin: Theme.grid; anchors.verticalCenter: parent.verticalCenter
                               text: nline.modelData.label; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                        Chevron { anchors.right: parent.right; anchors.rightMargin: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                                  rotation: -90; color: narrowArea.containsMouse ? Theme.fg : Theme.fg3 }
                        MouseArea { id: narrowArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: panel.bridge.narrowTo(nline.modelData.kind) }
                    }
                }
            }
            Column { id: aboveSlot; width: parent.width }
            Repeater {
                id: rowsView
                model: panel.bridge.rows
                delegate: InspectorRow { bridge: panel.bridge; keyMarks: panel.keyMarks
                                         highlighted: model.row === "param" && panel.highlight.indexOf(model.id) >= 0 }
            }
            EffectsRow { part: panel.effects ? panel.bridge.invoke("effects", []) : null }   // "Effects (n) +" (effects.attach)
            Column { id: belowSlot; width: parent.width }
        }
        Text { visible: panel.finds && panel.bridge.nothingFound; text: "No setting matches"; y: Theme.grid
               color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.body }
    }
    EdgeFade { flick: scroller; anchors.fill: scroller }   // a half-scrolled row fades, never a stray "." (S36)
    VScrollBar { flick: scroller }
    Item {  // the last line: who changed the selection last (a click opens History)
        id: lastLine
        visible: panel.hasLast
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: visible ? Theme.row : 0
        NameLabel { anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    text: panel.hasLast ? "Last changed by " + panel.last.who + (panel.last.ago ? " · " + panel.last.ago : "") : ""
                    help: panel.hasLast ? panel.last.label : ""
                    color: lastArea.containsMouse ? Theme.fg2 : Theme.fg3; font.pixelSize: Theme.label }
        MouseArea { id: lastArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: panel.bridge.agent.askHistory(panel.last.session) }
    }
    Timer { interval: 30000; repeat: true; running: panel.visible && panel.hasLast; onTriggered: panel.tick++ }

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

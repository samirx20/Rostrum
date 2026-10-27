import QtQuick
import QtQuick.Controls as QQC
import "."
import "Blocks.js" as Blocks

// The block view's add list: a search line on top, the block types under it (by group while nothing is typed, best
// match first while typing: label, then group and the type's `words`). Up / Down + Enter or a click picks one
// (chosen(type)); Esc closes. `fromKind`: it opened from a wire dropped on nothing, so only the types that wire can
// feed are listed. The app places it (BlockView.openAdd) and sizes nothing: it fits its rows, up to 340 px (less
// where its parent is shorter), always ending on a whole row so the last one is never cut in half.
SmallPopup {
    id: pop
    property var catalogue: []
    property string fromKind: ""
    property var converts: ({})
    property var kindColours: ({})
    property var rows: []                   // [{heading}] or catalogue entries, in list order
    property int current: -1                // the row Enter picks (never a heading)
    property point at                       // where it opens (its top-left), in its parent; it stays inside the parent
    readonly property int headingHeight: 24
    // the list's height: as many whole rows (from the top) as fit in 340 px and in the parent
    readonly property real listHeight: {
        const room = Math.min(340, (parent ? parent.height : 340) - 16 - 2 * padding - Theme.button - 4)
        let h = 0
        for (const r of rows) {
            const next = h + (r.heading ? headingHeight : Theme.popupRow)
            if (next > room) break
            h = next
        }
        return h
    }
    signal chosen(string type)
    width: 248
    padding: 6
    ownKeys: ["Up", "Down", "Return", "Enter"]
    background: Rectangle { color: Theme.raised; radius: Theme.radiusPanel; border.color: Theme.popupEdge }

    function refilter() {
        const q = search.input.text.trim()
        const hits = Blocks.search(catalogue, q, fromKind, converts)
        let out = hits
        if (!q) {                           // nothing typed: under each group's name, groups in catalogue order
            out = []
            const groups = []
            for (const e of hits) if (groups.indexOf(e.group || "") < 0) groups.push(e.group || "")
            for (const g of groups) {
                if (g) out.push({ heading: g })
                for (const e of hits) if ((e.group || "") === g) out.push(e)
            }
        }
        rows = out
        current = out.findIndex(r => !r.heading)
        list.positionViewAtBeginning()
    }
    function step(d) {                      // d > 0: up (FieldFrame's arrow), skipping headings
        for (let i = current - d; i >= 0 && i < rows.length; i -= d)
            if (!rows[i].heading) { current = i; list.positionViewAtIndex(i, ListView.Contain); return }
    }
    function pick() { const r = rows[current]; if (r && !r.heading) { close(); chosen(r.type) } }
    onAboutToShow: {
        search.input.text = ""; refilter(); settle()
        x = Math.max(8, Math.min(at.x, parent.width - width - 8))
        y = Math.max(8, Math.min(at.y, parent.height - implicitHeight - 8))
    }
    onOpened: search.input.forceActiveFocus()

    Column {
        objectName: "blockAddList"
        width: pop.availableWidth
        spacing: 4
        FieldFrame {
            id: search
            objectName: "blockAddSearch"
            width: parent.width; height: Theme.button
            editable: true
            placeholder: "Find a block"
            onEntered: pop.pick()
            onEscaped: pop.close()
            onArrow: (d) => pop.step(d)
            Connections { target: search.input; function onTextEdited() { search.text = search.input.text; pop.refilter() } }
        }
        ListView {
            id: list
            width: parent.width
            height: pop.listHeight
            snapMode: ListView.SnapToItem         // a scrolled list rests on a row's top
            model: pop.rows
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            delegate: Item {
                id: row
                required property var modelData
                required property int index
                readonly property bool heading: !!modelData.heading
                objectName: heading ? "" : "blockAddItem:" + modelData.type
                width: ListView.view.width
                height: heading ? pop.headingHeight : Theme.popupRow
                Text {
                    visible: row.heading
                    anchors.left: parent.left; anchors.leftMargin: 8; anchors.bottom: parent.bottom; anchors.bottomMargin: 4
                    text: row.modelData.heading || ""
                    color: Theme.fg4; font.family: uiFont; font.pixelSize: Theme.label
                }
                Rectangle {
                    visible: !row.heading
                    anchors.fill: parent; radius: Theme.radiusCtl
                    color: row.index === pop.current ? Theme.accentSoft : "transparent"
                    Text {
                        anchors.left: parent.left; anchors.leftMargin: 8; anchors.verticalCenter: parent.verticalCenter
                        anchors.right: dots.left; anchors.rightMargin: 8; elide: Text.ElideRight
                        text: row.modelData.label || ""
                        color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body
                    }
                    Row {                   // what it gives: a dot per output kind
                        id: dots
                        anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter
                        spacing: 4
                        Repeater {
                            model: row.heading ? [] : (row.modelData.outputs || [])
                            delegate: Rectangle {
                                required property var modelData
                                width: 8; height: 8; radius: 4
                                color: pop.kindColours[modelData.kind] || Theme.fg4
                            }
                        }
                    }
                    MouseArea {
                        anchors.fill: parent; hoverEnabled: true
                        onEntered: pop.current = row.index
                        onClicked: { pop.current = row.index; pop.pick() }
                    }
                }
            }
        }
        EmptyHint {
            visible: list.count === 0 || (pop.rows.length > 0 && pop.current < 0)
            width: parent.width
            text: pop.fromKind ? "No block takes this wire." : "No block called “" + search.input.text.trim() + "”."
        }
    }
}

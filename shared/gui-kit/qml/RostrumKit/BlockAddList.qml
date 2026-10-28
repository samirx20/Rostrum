import QtQuick
import QtQuick.Controls as QQC
import "."
import "Blocks.js" as Blocks

// The block view's add list: a search line on top, the block types under it (by group while nothing is typed, best
// match first while typing: label, then group and the type's `words`). Up / Down + Enter or a click picks one
// (chosen(type)); Esc closes. `fromKind`: it opened from a wire dropped on nothing, so only the types that wire can
// feed are listed. The app places it (BlockView.openAdd) and sizes nothing. It lives on the window's overlay (BlockView
// sets the parent), so a short panel never squeezes it: it opens under `at`, and when its whole list doesn't fit
// there and there is more room above, it opens upward, its bottom just above `upTo` (the opener's top). It fits its
// rows in that room, always ending on a whole row so the last one is never cut in half. `at` / `upTo` are in `from`'s
// coordinates, measured again while it is open (a panel still settling moves the opener).
SmallPopup {
    id: pop
    property var catalogue: []
    property string fromKind: ""
    property var converts: ({})
    property var kindColours: ({})
    property var rows: []                   // [{heading}] or catalogue entries, in list order
    property int current: -1                // the row Enter picks (never a heading)
    property point at                       // where it opens (its top-left), in `from`
    property real upTo: 0                   // opening upward, its bottom stays above this y, in `from`
    property Item from: null                // the item `at` and `upTo` are in (null: the parent)
    property real atX: 0                    // `at` and `upTo` in the parent, measured by measure()
    property real atY: 0
    property real upY: 0
    readonly property int headingHeight: 24
    readonly property real rowsHeight: {    // the whole list
        let h = 0
        for (const r of rows) h += r.heading ? headingHeight : Theme.popupRow
        return h
    }
    readonly property real chrome: 2 * padding + Theme.button + 4
    readonly property real below: (parent ? parent.height : 340) - 8 - atY - chrome
    readonly property real above: upY - 4 - 8 - chrome
    readonly property bool upward: rowsHeight > below && above > below
    // the list's height: as many whole rows (from the top) as fit in the room it opened into
    readonly property real listHeight: {
        const room = upward ? above : below
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
    function measure() {                    // true when the opener moved since the last time
        const src = from || parent
        if (!src || !parent) return false
        const p = src.mapToItem(parent, at.x, at.y), u = src.mapToItem(parent, at.x, upTo)
        if (p.x === atX && p.y === atY && u.y === upY) return false
        atX = p.x; atY = p.y; upY = u.y
        return true
    }
    function place() {
        x = Math.max(8, Math.min(atX, parent.width - width - 8))
        y = upward ? Math.max(8, upY - 4 - implicitHeight)
                   : Math.max(8, Math.min(atY, parent.height - implicitHeight - 8))
    }
    onAboutToShow: { search.input.text = ""; refilter(); measure(); settle(); place() }
    onOpened: search.input.forceActiveFocus()
    // the opener may still move (its panel settling): follow it, but only then (typing changes the list's height and
    // must not move the search line under the keyboard)
    Timer { interval: 100; repeat: true; running: pop.visible; onTriggered: if (pop.measure()) { pop.settle(); pop.place() } }

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

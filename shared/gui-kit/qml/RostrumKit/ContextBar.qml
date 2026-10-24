import QtQuick
import QtQuick.Controls as QQC
import "."

// The one context bar: what is selected ("3 layers"), its top actions in rank order (up to five), then ⋯.
// Floats at the top-centre of the main view; one row, never wraps. The host places it:
//     ContextBar { hub: actionHub; dragging: view.dragging; toolOptions: optionsComponent
//                  anchors.top: view.top; anchors.topMargin: Theme.gap; anchors.horizontalCenter: view.horizontalCenter
//                  maxWidth: view.width - 2 * toolStripWidth }       // never covers the tool strip
// `hub.bar` = {what, items: [{id, label, keys, menu}], more: [entries]}; an item with a `menu` has a ▾ and opens
// its choices. When maxWidth is too small the lowest-ranked buttons fold into ⋯ one by one. A click calls
// hub.run(id); a choice from a ▾ menu calls hub.run(value). Hidden when `what` is empty (and no toolOptions),
// and while `dragging`. `toolOptions` (a Component): shown instead of the selection actions (a tool's options).
// `showName: false` drops the name chip (an app whose settings panel already shows the selection's name).
Rectangle {
    id: bar
    property var hub
    property real maxWidth: 10000
    property bool dragging: false
    property Component toolOptions: null
    property bool showName: true
    // hidden (`dragging`) it reads nothing: a host that keeps it hidden most of the time (2D: only picked strokes show
    // it) had it re-measure and refill its buttons on every pick
    readonly property var info: hub && hub.bar && !dragging ? hub.bar : ({what: "", items: [], more: []})
    readonly property bool tool: toolOptions !== null
    readonly property int maxActions: 5
    readonly property int shownCount: { labelWidths; return fitCount() }
    readonly property var overflow: (info.items || []).slice(shownCount).map(it => ({
        value: it.id, label: it.label, keys: it.keys, group: "~folded", sub: it.menu && it.menu.length ? it.menu : undefined
    })).concat(info.more || [])

    visible: !dragging && (tool || (!!info.what && (showName || (info.items || []).length + (info.more || []).length > 0)))
    height: Theme.button + 2 * Theme.grid
    width: Math.min(maxWidth, row.implicitWidth + 2 * Theme.gap)
    radius: Theme.radiusPanel; color: Theme.raised; border.color: Theme.popupEdge
    clip: true

    // widths of every ranked label (measured with the font, so they follow it), for folding; a binding, not hidden
    // texts: a new selection made and measured a Text per label, each re-folding the bar (tens of ms per click)
    FontMetrics { id: labelFont; font.pixelSize: Theme.body; font.family: uiFont }
    readonly property var labelWidths: (info.items || []).map(it => labelFont.advanceWidth(it.label))
    function buttonW(i) {
        const it = info.items[i]
        if (!it) return 0
        return Math.ceil(labelWidths[i] || 0) + 2 * Theme.gap + (it.menu && it.menu.length ? 16 : 0)
    }
    Text { id: chipMeasure; visible: false; text: bar.info.what || ""; font.pixelSize: Theme.body; font.family: uiFont; font.weight: Font.DemiBold }
    // how many of the ranked buttons fit beside the count chip and ⋯ within maxWidth
    function fitCount() {
        const all = info.items || []
        const n = Math.min(all.length, maxActions)
        const chip = showName && info.what ? Math.ceil(chipMeasure.implicitWidth) + Theme.pad + 2 * Theme.grid : 0
        const hasMore = (info.more || []).length > 0 || all.length > n
        let k = n
        const total = c => {
            let w = 2 * Theme.gap + chip + ((hasMore || c < n) ? Theme.button + Theme.grid : 0)
            for (let i = 0; i < c; i++) w += buttonW(i) + Theme.grid
            return w
        }
        while (k > 0 && total(k) > maxWidth) k--
        return k
    }

    function closeMore() { moreMenu.close() }
    function openMore() {
        const p = moreBtn.mapToItem(moreMenu.parent, 0, moreBtn.height + 2)
        moreMenu.openAt(p.x, p.y, p.x + moreBtn.width)
    }

    Row {
        id: row
        x: Theme.gap; anchors.verticalCenter: parent.verticalCenter
        spacing: Theme.grid
        Loader { active: bar.tool; visible: bar.tool; sourceComponent: bar.toolOptions; anchors.verticalCenter: parent.verticalCenter }   // an unloaded Loader keeps its last width: out of the row
        Text {
            visible: !bar.tool && bar.showName && !!bar.info.what
            anchors.verticalCenter: parent.verticalCenter
            rightPadding: Theme.pad - Theme.grid
            text: bar.info.what; color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont; font.weight: Font.DemiBold
        }
        Repeater {      // always maxActions buttons, those past shownCount hidden: a count as the model remade every
                        // button (and its tip) whenever a new selection had another number of actions
            model: bar.maxActions
            delegate: Rectangle {
                id: btn
                required property int index
                visible: !bar.tool && index < bar.shownCount
                readonly property var modelData: bar.info.items[index] || ({ id: "", label: "", keys: "", menu: [] })
                readonly property bool hasMenu: !!(modelData.menu && modelData.menu.length)
                width: { bar.labelWidths; return bar.buttonW(index) } height: Theme.button; radius: Theme.radiusCtl
                readonly property bool menuOpen: bar.menuFor === index && choices.visible
                color: ma.pressed || menuOpen ? Theme.active : ma.containsMouse ? Theme.hover : "transparent"
                Behavior on color { ColorAnimation { duration: Theme.fast } }
                Text {
                    x: Theme.gap; anchors.verticalCenter: parent.verticalCenter
                    text: btn.modelData.label; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont
                }
                Chevron {
                    visible: btn.hasMenu; open: btn.menuOpen; anchors.verticalCenter: parent.verticalCenter
                    anchors.right: parent.right; anchors.rightMargin: Theme.grid
                }
                MouseArea {
                    id: ma
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        if (!btn.hasMenu) { bar.hub.run(btn.modelData.id); return }
                        const p = btn.mapToItem(choices.parent, 0, btn.height + 2)
                        bar.menuFor = index; choices.entries = btn.modelData.menu
                        choices.openAt(p.x, p.y)
                    }
                }
                HoverTip {
                    text: btn.modelData.label + (btn.modelData.keys ? "  " + btn.modelData.keys : "")
                    hovered: ma.containsMouse && !btn.menuOpen; pressed: ma.pressed
                }
            }
        }
        Rectangle {
            id: moreBtn
            visible: !bar.tool && bar.overflow.length > 0
            width: Theme.button; height: Theme.button; radius: Theme.radiusCtl
            color: moreArea.pressed || moreMenu.visible ? Theme.active : moreArea.containsMouse ? Theme.hover : "transparent"
            Row {
                anchors.centerIn: parent; spacing: 3
                Repeater { model: 3; Rectangle { width: 3; height: 3; radius: 1.5; color: Theme.fg2 } }
            }
            MouseArea {
                id: moreArea
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: bar.openMore()
            }
            HoverTip { text: "More"; hovered: moreArea.containsMouse && !moreMenu.visible; pressed: moreArea.pressed }
            ActionMenu { id: moreMenu; entries: bar.overflow; onPicked: v => bar.hub.run(v) }
        }
    }
    property int menuFor: -1                 // the button whose ▾ is open: one menu for every button, filled as it opens
    ActionMenu { id: choices; onPicked: v => bar.hub.run(v); onClosed: bar.menuFor = -1 }
}

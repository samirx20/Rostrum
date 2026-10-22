import QtQuick
import "."

// One generic inspector row: a group header, a param, the More row or a fold row — nothing placed per control.
// A fold row (rows by importance) is a group's name with a chevron: click opens or closes the group
// (bridge.toggleGroup(model.fold)). `flash()` briefly marks the row and `focusWidget()` puts the keys in its widget
// (revealField). Several items selected and their values differ (model.mixed): the field says "Mixed" until edited.
// The widget comes from the param's `type` only. The row owns its reveal: when `valid` changes, height and
// opacity ease over Theme.reveal (160 ms); the Column below just follows. A new selection builds fresh rows
// at their final state (a Behavior does not animate the first value), so the list swaps at once.
// With `keyMarks` (an app with keys) every param row keeps a gutter at the right for its key mark (model.anim):
// a filled diamond = a key at the playhead, outlined = animated, faint (always shown, a little stronger on hover) =
// could be animated (INTERACTION 1.5: always visible, not only on hover).
// Clicking the mark is bridge.toggleAnimate (the app decides what that does).
Item {
    id: row
    required property var model           // roles from rostrum_gui.rows.ROLES
    property var bridge
    property bool keyMarks: false
    property bool highlighted: false      // marked while it is in focus elsewhere (2D: its keys picked in the timeline)
    readonly property int gutter: keyMarks ? 22 : 0
    readonly property bool driven: model.row === "param" && !!model.expr      // an expression decides (model.expr)
    readonly property bool tall: model.type === "list" || model.control === "curve"    // a widget taller than a field (top-aligned)
    readonly property int full: model.row === "group" ? Theme.groupGap + (model.label ? Theme.rowDense : 0)   // "": a gap only
                              : model.row === "more" ? Theme.row + Theme.grid
                              : model.row === "fold" ? Theme.row
                              : driven ? Theme.row + exprBox.height + Theme.grid
                              : model.control === "curve" ? Theme.curveBox + Theme.row - Theme.field
                              : tall && widget.item ? Math.max(Theme.row, widget.item.implicitHeight + Theme.row - Theme.field)
                              : Math.max(Theme.row, label.implicitHeight + 2 * Theme.grid)    // a long label wraps
    property real reveal: model.valid ? 1 : 0
    Behavior on reveal { NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }
    width: parent ? parent.width : 0
    height: Math.round(full * reveal)
    opacity: reveal
    visible: reveal > 0
    clip: reveal < 1

    Text {  // group header
        visible: row.model.row === "group"
        anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.bottomMargin: Theme.grid + 2
        text: row.model.label; color: Theme.fg3; font.family: uiFont
        font.pixelSize: Theme.label; font.weight: Font.DemiBold
    }
    Item {  // the More row (deep params live behind it)
        visible: row.model.row === "more"
        anchors.fill: parent
        Chevron { id: moreChev; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                  rotation: row.bridge.moreOpen ? 0 : -90; color: moreArea.containsMouse ? Theme.fg : Theme.fg3 }
        Text { anchors.left: moreChev.right; anchors.leftMargin: Theme.grid + 2; anchors.verticalCenter: parent.verticalCenter
               text: "More"; color: moreArea.containsMouse ? Theme.fg : Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont }
        MouseArea { id: moreArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: row.bridge.toggleMore() }
    }
    Rectangle {  // highlighted: a steady soft mark (the flash below is the same colour, brief)
        anchors.fill: parent; anchors.leftMargin: -Theme.grid; anchors.rightMargin: -Theme.grid
        radius: Theme.radiusCtl; color: Theme.accentSoft; visible: row.highlighted
    }
    Rectangle {  // the flash after a jump to this field (revealField)
        id: flashMark
        anchors.fill: parent; anchors.leftMargin: -Theme.grid; anchors.rightMargin: -Theme.grid
        radius: Theme.radiusCtl; color: Theme.accentSoft; opacity: 0
        SequentialAnimation on opacity { id: flashAnim; running: false
            NumberAnimation { to: 1; duration: Theme.fast } PauseAnimation { duration: 700 }
            NumberAnimation { to: 0; duration: 400 } }
    }
    Item {  // a fold row: chevron + the group's name
        visible: row.model.row === "fold"
        anchors.fill: parent
        Chevron { id: foldChev; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                  rotation: row.model.open ? 0 : -90; color: foldArea.containsMouse ? Theme.fg : Theme.fg3
                  Behavior on rotation { NumberAnimation { duration: Theme.fast; easing.type: Theme.revealEasing } } }
        Text { anchors.left: foldChev.right; anchors.leftMargin: Theme.grid + 2
               anchors.verticalCenter: parent.verticalCenter; text: row.model.label
               color: foldArea.containsMouse ? Theme.fg : Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont
               font.weight: Font.DemiBold }
        MouseArea { id: foldArea; anchors.fill: parent; hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor; onClicked: row.bridge.toggleGroup(row.model.fold) }
    }
    Item {  // a param: label column, then the widget
        visible: row.model.row === "param"
        anchors.left: parent.left; anchors.right: parent.right
        anchors.verticalCenter: row.driven || row.tall ? undefined : parent.verticalCenter
        anchors.top: row.driven || row.tall ? parent.top : undefined
        height: Theme.row
        Text { id: label; width: Theme.labelColumn - Theme.gap; anchors.verticalCenter: parent.verticalCenter
               text: row.model.label; color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont
               wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight; lineHeight: 0.9   // never cut to "Width along the…"
               HoverHandler { id: labelHover }
               HoverTip { text: row.model.help || label.truncated ? row.model.label : ""; help: row.model.help || ""
                          hovered: labelHover.hovered } }   // hover help: the setting's name and its one sentence
        Loader {
            id: widget
            x: Theme.labelColumn
            anchors.verticalCenter: row.tall ? undefined : parent.verticalCenter
            y: row.tall ? (Theme.row - Theme.field) / 2 : 0
            width: row.model.type === "toggle" ? (item ? item.implicitWidth : 0) : parent.width - Theme.labelColumn - row.gutter
            height: row.tall && item ? item.implicitHeight : Theme.field
            active: row.model.row === "param" && !row.driven
            sourceComponent: row.model.control === "curve" ? curve
                           : row.model.control === "file" || row.model.control === "folder" ? path
                           : ({ toggle: toggle, number: number, choice: choice, color: colour, text: text, list: list })[row.model.type] || text
        }
        // A param driven by an expression or binding (model.expr = {text, note}): in place of the widget a note
        // and a clear button on the label line, the expression on its own full-width line under it.
        Text { visible: row.driven; anchors.right: clearMark.left; anchors.rightMargin: Theme.gap
               anchors.verticalCenter: parent.verticalCenter; text: row.driven ? row.model.expr.note : ""
               color: Theme.fg3; font.pixelSize: Theme.label; font.family: uiFont }
        Text { id: clearMark; visible: row.driven; anchors.right: parent.right; anchors.rightMargin: Theme.grid
               anchors.verticalCenter: parent.verticalCenter; text: "×"; font.pixelSize: Theme.heading
               color: clearArea.containsMouse ? Theme.fg : Theme.fg3
               MouseArea { id: clearArea; anchors.fill: parent; anchors.margins: -Theme.grid; hoverEnabled: true
                           cursorShape: Qt.PointingHandCursor; onClicked: row.bridge.clearExpression(row.model.id) } }
        Rectangle {
            id: exprBox
            visible: row.driven
            y: Theme.row; width: parent.width; height: exprText.implicitHeight + 2 * Theme.gap
            radius: Theme.radiusCtl; color: Theme.accentSoft
            Text { id: exprText; x: Theme.gap; y: Theme.gap; width: parent.width - 2 * Theme.gap
                   text: row.driven ? "= " + row.model.expr.text : ""; color: Theme.fg; font.pixelSize: Theme.body
                   font.family: monoFont; wrapMode: Text.WrapAnywhere }
        }
        HoverHandler { id: rowHover }
        Item {  // the key mark
            visible: row.keyMarks && !!row.model.anim
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            width: row.gutter - 4; height: Theme.field
            KeyMark { anchors.centerIn: parent; filled: row.model.anim === "onkey"
                      color: row.model.anim === "still" ? (markArea.containsMouse ? Theme.fg2 : rowHover.hovered ? Theme.fg3 : Theme.fg4)
                           : markArea.containsMouse ? Theme.accentHover : Theme.accent }
            MouseArea { id: markArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: row.bridge.toggleAnimate(row.model.id) }
        }
    }

    readonly property string mixed: model.mixed ? "Mixed" : ""       // a field's words at rest ("" = its value)
    function set(v) { bridge.setValue(model.id, v) }
    function flash() { flashAnim.restart() }
    function focusWidget() {
        const w = widget.item
        if (!w) return
        if (w.input && w.editable) { w.input.forceActiveFocus(); w.input.selectAll() } else w.forceActiveFocus()
    }
    Component { id: toggle; Toggle { checked: !!row.model.value; onToggled: (v) => row.set(v) } }
    Component { id: number; NumberField {
        value: row.model.value === null || row.model.value === undefined ? 0 : row.model.value
        from: row.model.min === null || row.model.min === undefined ? -1e9 : row.model.min
        to: row.model.max === null || row.model.max === undefined ? 1e9 : row.model.max
        step: row.model.step ? row.model.step : 1
        unit: row.model.mixed ? "" : row.model.unit || ""
        atRest: row.mixed
        words: row.model.words || []
        onEdited: (v) => row.set(v)
        onScrubStarted: row.bridge.beginScrub(row.model.id)
        onScrubbed: (v) => row.bridge.scrub(row.model.id, v)
        onScrubEnded: row.bridge.endScrub() } }
    Component { id: choice; ChoiceField { options: row.model.options; current: row.model.value ?? ""; atRest: row.mixed
                                          onPicked: (v) => row.set(v) } }
    Component { id: colour; ColorField { hex: row.model.value || "#000000"; atRest: row.mixed; onEdited: (v) => row.set(v) } }
    Component { id: list; ListField {
        values: row.model.value || []; choices: row.model.options || []
        minItems: row.model.minItems || 0; maxItems: row.model.maxItems === undefined ? null : row.model.maxItems
        onEdited: (v) => row.set(v) } }
    Component { id: curve; CurveField {   // a curve param's max = the top of its out range (above 1: a multiplier)
        value: row.model.value || ""; most: row.model.max ? row.model.max : 1; onEdited: (v) => row.set(v) } }
    Component { id: path; PathField {
        value: row.model.value || ""; folder: row.model.control === "folder"; nameFilters: row.model.filters || []
        onEdited: (v) => row.set(v) } }
    Component { id: text; TextField { value: row.model.value || ""; atRest: row.mixed; onEdited: (v) => row.set(v) } }
}

import QtQuick
import QtQuick.Dialogs
import "."
import "ValueKinds.js" as VK

// One generic inspector row: a group header, a param, the More row or a fold row — nothing placed per control.
// A fold row (rows by importance) is a group's name with a chevron: click opens or closes the group
// (bridge.toggleGroup(model.fold)); only an open group shows its fold row. The "folds" row is every folded group's
// name, every one of them in one wrapping line ("+ Depth  + Timing  + Blend"; no "+ N more": a name behind a click was a
// click to reach a click); a click on a
// name opens that group (a group a switch turns on, model.switch, is added: "+ Outline" puts the outline on, one change, and
// its heading has − to remove it; rows.py) (the "+" says it is a control, so a lone name never reads as an empty heading). `flash()` briefly marks the row and `focusWidget()` puts the keys in its widget
// (revealField). Several items selected and their values differ (model.mixed): the field says "Mixed" until edited.
// The widget comes from the param's `type` only. The row owns its reveal: when `valid` changes, height and
// opacity ease over Theme.reveal (160 ms); the Column below just follows. A new selection shows at once: a new
// layout builds fresh rows at their final state (a Behavior does not animate the first value), and the same kind's
// rows change in place with `instant` true (the list model's, RowsModel.instant), so nothing eases.
// An optional `note` (rows.py: {text, kind "hint" | "warning"}) is one short line under the field: the row grows by its height only
// while there is one, so an empty note leaves no gap. An optional `button` (rows.py: {label, id, menu}) is a small RowButton at the
// right end of the field's own column (the column keeps its width: field and button share it); a click runs bridge.rowAction(id).
// An optional `tag` (rows.py: a word like "Final") shows as a small quiet tag at the end of the label, its `tagHelp` on hover.
// With `keyMarks` (an app with keys) every param row keeps a gutter at the right for its key mark (model.anim):
// a filled diamond = a key at the playhead, outlined = animated, faint (always shown, a little stronger on hover) =
// could be animated (INTERACTION 1.5: always visible, not only on hover).
// Clicking the mark is bridge.toggleAnimate (the app decides what that does).
// Right-click on a param row: Reset puts it back to its default (model.default) through the same set operation, one
// undo step (INTERACTION 1.4). At its default (or with no default, or driven by an expression) there is nothing to
// reset, so the menu is absent. Mixed values count as not at the default.
// A number with a `display` kind (model.display; ValueKinds.js) shows in that kind's words ("80 %", "−1.9 dB", "L 30");
// an amount (VK.slides: pan, a gain, a 0..1 amount) gets the kit Slider with its NumberField beside it.
// The settings grid (Theme.settingsGrid numbers, SPEC 8.0): the label column is Theme.labelColumnFor(width), then ONE field
// column Theme.fieldFor(width) wide, then the key gutter (always reserved, empty without a key mark), so every field starts
// and ends alike. Only Position (X | Y) and Size (W | H) share a row (rows.py `half`: "first" / "second"): the second half's
// row has no height of its own and draws on the first's line, each half Theme.halfFor(width) wide with its small letter inside.
// A row marked `inside` another (rows.py: a fill's Scale, Offset … inside the Fill row) is drawn only by an InspectorRow whose
// `inside` names that row (the Fill picker's), never in the panel's own list. A colour that may be none (options.start) reads
// "no colour  +" while it is none; the "+" sets it to that start, right-click › Reset makes it none again.
Item {
    id: row
    required property var model           // roles from rostrum_gui.rows.ROLES
    objectName: model.row === "param" ? "row:" + model.id : ""      // scripted steps (the layout check) find a row by it
    property var bridge
    property bool keyMarks: false
    property bool highlighted: false      // marked while it is in focus elsewhere (2D: its keys picked in the timeline)
    property bool instant: false          // the list model's `instant`: this change is a new selection, shown at once
    property string inside: ""            // the host row whose picker draws this list ("" = the panel's own list)
    readonly property bool here: (model.inside || "") === inside
    readonly property int gutter: Theme.keyGutter
    readonly property bool second: model.half === "second"      // the right half of a pair: it sits on the previous row's line
    // An absent row (not valid, not easing out) reads nothing more than it must: a kind's layout holds every param
    // and most rows are absent, so each binding below waits for `live` (a kind switch made ~80 absent rows, ~2 ms each).
    readonly property bool live: here && (model.valid || reveal > 0)
    readonly property bool paired: live && (model.half === "first" || second)
    readonly property int labelColumn: live ? Theme.labelColumnFor(width) : 0
    readonly property bool amount: live && model.type === "number" && !paired && VK.slides(model.display || "", model.min ?? 0, model.max ?? 1e9)
    readonly property bool noted: live && model.row === "param" && !!(model.note && model.note.text) && !paired && !tall
    readonly property bool driven: live && model.row === "param" && !!model.expr      // an expression decides (model.expr)
    readonly property var parts: body.item      // the drawn row (null while absent)
    readonly property bool tall: live && (model.type === "list" || model.control === "curve")    // a widget taller than a field (top-aligned)
    readonly property int full: !live ? 0 : model.row === "group" ? Theme.groupGap + (model.label ? Theme.rowDense : 0)   // "": a gap only
                              : model.row === "more" ? Theme.row + Theme.grid
                              : model.row === "fold" ? Theme.row
                              : model.row === "folds" ? (parts ? parts.foldsHeight : 0) + 2 * Theme.grid
                              : driven ? Theme.row + (parts ? parts.exprHeight : 0) + Theme.grid
                              : model.control === "curve" ? Theme.curveBox + Theme.row - Theme.field
                              : tall && parts && parts.widgetItem ? Math.max(Theme.row, parts.widgetItem.implicitHeight + Theme.row - Theme.field)
                              : Math.max(Theme.row, (parts ? parts.labelHeight : 0) + 2 * Theme.grid) + (noted && parts ? parts.noteHeight : 0)    // a long label wraps
    readonly property bool noneable: live && model.type === "color" && !!model.options && model.options.start !== undefined
    readonly property bool canReset: live && model.row === "param" && !driven && model.default !== undefined && (model.default !== null || noneable)
        && (!!model.mixed || JSON.stringify(model.value) !== JSON.stringify(model.default))
    property real reveal: here && model.valid ? 1 : 0
    Behavior on reveal { enabled: !row.instant; NumberAnimation { duration: Theme.reveal; easing.type: Theme.revealEasing } }
    width: parent ? parent.width : 0
    height: second ? 0.01 : Math.round(full * reveal)
    opacity: reveal
    visible: reveal > 0
    clip: reveal < 1 && !second

    // Everything the row draws is made only while it is on screen (valid, or still easing out). A kind's layout holds
    // every param and most rows are absent at any time; building all their parts (chevrons, hover tips, widgets) made
    // each new selection slow (S59: ~0.35 s for a Sound track). An absent row is just its id and its `reveal`.
    Loader {
        id: body
        anchors.fill: parent
        active: row.live
        sourceComponent: Item {
            readonly property real labelHeight: label.implicitHeight     // what `full` reads (the row's own height)
            readonly property real noteHeight: row.noted ? noteText.implicitHeight + Theme.grid : 0
            readonly property real exprHeight: exprBox.height
            readonly property var widgetItem: widget.item
            readonly property real foldsHeight: names.implicitHeight
            function flash() { flashAnim.restart() }
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
                          rotation: row.bridge.moreOpen ? 0 : -90; color: moreArea.containsMouse ? Theme.fg : Theme.fg2 }
                Text { anchors.left: moreChev.right; anchors.leftMargin: Theme.grid + 2; anchors.verticalCenter: parent.verticalCenter
                       text: "More"; color: Theme.fg; font.pixelSize: Theme.body; font.family: uiFont }
                MouseArea { id: moreArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: row.bridge.toggleMore() }
            }
            Rectangle {  // highlighted: a steady soft mark (the flash below is the same colour, brief)
                anchors.fill: parent; anchors.leftMargin: -Theme.grid; anchors.rightMargin: row.gutter
                radius: Theme.radiusCtl; color: Theme.accentSoft; visible: row.highlighted
            }
            Rectangle {  // the flash after a jump to this field (revealField)
                id: flashMark
                anchors.fill: parent; anchors.leftMargin: -Theme.grid; anchors.rightMargin: row.gutter
                radius: Theme.radiusCtl; color: Theme.accentSoft; opacity: 0
                SequentialAnimation on opacity { id: flashAnim; running: false
                    NumberAnimation { to: 1; duration: Theme.fast } PauseAnimation { duration: 700 }
                    NumberAnimation { to: 0; duration: 400 } }
            }
            Item {  // a fold row: chevron + the group's name (a group a switch turns on: its name and a remove control)
                visible: row.model.row === "fold"
                anchors.fill: parent
                readonly property bool plain: !!row.model.own || !!row.model.switch     // no folding: always open while it applies
                Chevron { id: foldChev; visible: !parent.plain; anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                          rotation: row.model.open ? 0 : -90; color: foldArea.containsMouse ? Theme.fg : Theme.fg3
                          Behavior on rotation { NumberAnimation { duration: Theme.fast; easing.type: Theme.revealEasing } } }
                Text { anchors.left: foldChev.right; anchors.leftMargin: parent.plain ? -foldChev.width : Theme.grid + 2
                       anchors.verticalCenter: parent.verticalCenter; text: row.model.label
                       color: foldArea.containsMouse ? Theme.fg : Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont
                       font.weight: Font.DemiBold }
                MouseArea { id: foldArea; anchors.fill: parent; hoverEnabled: true; enabled: !parent.plain
                            cursorShape: Qt.PointingHandCursor; onClicked: row.bridge.toggleGroup(row.model.fold) }
                IconButton {   // a switched group: remove it (its switch off, one change); it goes back to the row of names
                    objectName: "remove:" + row.model.fold
                    visible: !!row.model.switch
                    anchors { right: parent.right; rightMargin: row.keyMarks ? row.gutter : 0; verticalCenter: parent.verticalCenter }
                    glyph: "−"; kind: "ghost"; tip: "Remove " + String(row.model.label).toLowerCase()
                    onClicked: row.bridge.toggleGroup(row.model.fold)
                }
            }
            Flow {  // the "folds" row: the folded groups' names, a click opens one
                id: names
                visible: row.model.row === "folds"
                anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: Theme.grid
                          rightMargin: row.keyMarks ? row.gutter : 0 }     // ends with the fields, not under the key marks
                spacing: Theme.pad
                readonly property var entries: row.model.row === "folds" ? row.model.names || [] : []
                Repeater {
                    model: names.entries
                    delegate: Row {
                        id: nameItem
                        required property var modelData
                        required property int index
                        height: Theme.rowDense
                        Text {
                            objectName: "fold:" + nameItem.modelData.group     // scripted steps open a group by it
                            text: "+ " + (nameItem.modelData.label || nameItem.modelData.group) ; font.family: uiFont; font.pixelSize: Theme.body
                            color: nameArea.containsMouse ? Theme.fg : Theme.fg2; anchors.verticalCenter: parent.verticalCenter
                            font.underline: nameArea.containsMouse
                            Rectangle {  // changed but folded by hand: a small dot says something in here differs from its default
                                visible: !!nameItem.modelData.changed; width: 4; height: 4; radius: 2; color: Theme.accent
                                anchors.left: parent.right; anchors.leftMargin: 2; anchors.top: parent.top; anchors.topMargin: 2 }
                            MouseArea { id: nameArea; anchors.fill: parent; anchors.margins: -3; hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor; onClicked: row.bridge.toggleGroup(nameItem.modelData.group) }
                        }
                    }
                }
            }
            Item {  // a param: label column, then the widget (a pair's halves each take only their own part of the line)
                id: cell
                visible: row.model.row === "param"
                x: row.second ? row.labelColumn + Theme.halfFor(row.width) + Theme.pairGap : 0
                width: row.second ? Theme.halfFor(row.width) : row.paired ? row.labelColumn + Theme.halfFor(row.width) : row.width
                anchors.verticalCenter: row.driven || row.tall || row.second || row.noted ? undefined : parent.verticalCenter
                anchors.top: row.driven || row.tall || row.noted ? parent.top : undefined
                y: row.second ? -Theme.row : 0               // the right half draws on the line above (its own row is 0 high)
                height: Theme.row
                Text { id: label   // the label sits in its own column, one per row (a pair has one: Position, Size)
                       visible: !row.second
                       width: row.labelColumn - Theme.gap - (tag.visible ? tag.width + Theme.grid : 0)
                       anchors.verticalCenter: parent.verticalCenter
                       height: row.model.type === "toggle" ? parent.height : implicitHeight   // a switch's words: the line's full height to click
                       verticalAlignment: Text.AlignVCenter
                       text: row.model.label; color: Theme.fg2; font.pixelSize: Theme.body; font.family: uiFont
                       wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight; lineHeight: 0.9   // never cut to "Width along the…"
                       HoverHandler { id: labelHover }
                       TapHandler { enabled: row.model.type === "toggle"; onTapped: row.set(!row.model.value) }   // a switch's words flip it too (F12, F13)
                       HoverTip { text: row.model.help || label.truncated ? row.model.label : ""; help: row.model.help || ""
                                  hovered: labelHover.hovered } }   // hover help: the setting's name and its one sentence
                Rectangle {  // an optional small tag after the label (model.tag, e.g. "Final"; its hover words model.tagHelp)
                    id: tag
                    visible: !row.second && !!row.model.tag
                    x: row.labelColumn - Theme.gap - width; anchors.verticalCenter: parent.verticalCenter
                    width: tagText.implicitWidth + 2 * Theme.grid; height: Theme.label + Theme.grid + 2
                    radius: Theme.radiusCtl; color: Theme.raised
                    Text { id: tagText; anchors.centerIn: parent; text: row.model.tag || ""; color: Theme.fg3
                           font.pixelSize: Theme.label - 1; font.family: uiFont }
                    HoverHandler { id: tagHover }
                    HoverTip { text: row.model.tagHelp || ""; hovered: tagHover.hovered }
                }
                Loader {
                    id: widget
                    objectName: row.model.type === "toggle" ? "" : "grid:field"   // the layout check reads the grid from these two names
                    // every widget starts at the field column (a slider and its value box share it); the right half of a pair
                    // starts at its own cell (after the left half and the pair gap)
                    x: row.second ? 0 : row.labelColumn
                    anchors.verticalCenter: row.tall ? undefined : parent.verticalCenter
                    y: row.tall ? (Theme.row - Theme.field) / 2 : 0
                    width: row.model.type === "toggle" ? (item ? item.implicitWidth : 0)
                         : row.paired ? Theme.halfFor(row.width) : Theme.fieldFor(row.width)
                    height: row.tall && item ? item.implicitHeight : Theme.field
                    // made only while the row is on screen (valid, or still easing out): a kind's layout holds every param and
                    // most are absent, so building all their widgets made each selection change slow (S59)
                    active: row.model.row === "param" && !row.driven && (row.model.valid || row.reveal > 0)
                    sourceComponent: row.model.button && row.model.type !== "toggle" ? buttoned : plain
                }
                Text {  // the note: one short line under the field (a hint, or a warning in the warning colour)
                    id: noteText
                    visible: row.noted
                    x: row.labelColumn; y: Theme.row - 2; width: Theme.fieldFor(row.width)
                    text: row.noted ? row.model.note.text : ""
                    color: row.noted && row.model.note.kind === "warning" ? Theme.warn : Theme.fg3
                    font.pixelSize: Theme.label; font.family: uiFont; wrapMode: Text.WordWrap
                }
                // A param driven by an expression or binding (model.expr = {text, note}): in place of the widget a note
                // and a clear button on the label line, the expression on its own full-width line under it.
                Text { visible: row.driven; anchors.right: clearMark.left; anchors.rightMargin: Theme.gap
                       anchors.verticalCenter: parent.verticalCenter; text: row.driven ? row.model.expr.note : ""
                       color: Theme.fg3; font.pixelSize: Theme.label; font.family: uiFont }
                Item {  // the clear button: a whole field-sized square left of the key-mark gutter, its click area = its box
                    id: clearMark; visible: row.driven
                    anchors.right: parent.right; anchors.rightMargin: row.gutter; anchors.verticalCenter: parent.verticalCenter
                    width: Theme.field; height: Theme.field
                    Text { anchors.centerIn: parent; text: "×"; font.pixelSize: Theme.heading
                           color: clearArea.containsMouse ? Theme.fg : Theme.fg3 }
                    MouseArea { id: clearArea; anchors.fill: parent; hoverEnabled: true
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
                TapHandler {  // right-click › Reset (left clicks and drags stay with the widgets)
                    acceptedButtons: Qt.RightButton; enabled: row.canReset
                    onTapped: (pt) => { resetMenu.active = true; resetMenu.item.openAt(pt.scenePosition.x, pt.scenePosition.y) }
                }
            }

            Item {  // the key mark: centred in the gutter at the row's right (a pair has one, on its first half's line)
                objectName: "grid:key"
                visible: row.keyMarks && !!row.model.anim && !row.second
                x: row.width - row.gutter + 2; y: cell.y + (cell.height - height) / 2
                width: row.gutter - 4; height: Theme.field
                KeyMark { anchors.centerIn: parent; filled: row.model.anim === "onkey"
                          color: row.model.anim === "still" ? (markArea.containsMouse ? Theme.fg2 : rowHover.hovered ? Theme.fg3 : Theme.fg4)
                               : markArea.containsMouse ? Theme.accentHover : Theme.accent }
                MouseArea { id: markArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: row.bridge.toggleAnimate(row.model.id) }      // a pair (X | Y): both halves, one change (bridge)
            }
            Loader {   // made at the first right-click only: a panel has many rows
                id: resetMenu; active: false
                sourceComponent: ActionMenu { entries: [{ value: "reset", label: "Reset" }]; onPicked: row.set(row.model.default) }
            }
            Loader {  // a choice's "Load …" entry (model.more): the file goes to bridge.loadChoice, which adds the option.
                id: moreDialog   // made at the first use only, like the Reset menu: a dialog per row made every panel slow to build
                active: false
                function open() { active = true; item.open() }
                sourceComponent: FileDialog {
                    title: row.model.more ? String(row.model.more).replace("…", "") : ""
                    nameFilters: (row.model.filters || []).concat(["All files (*)"])
                    onAccepted: row.loadChoice(decodeURIComponent(String(selectedFile).replace(/^file:\/\//, "")).replace(/^\/(?=[A-Za-z]:)/, ""))
                }
            }
            // The widgets, one per param type: made with the drawn row only (a kind's layout holds every param and
            // most rows are absent, so per-row Components on every absent row slowed each kind switch).
            // the widget by its type; with a button the same widget narrows to leave room for it, field and button share the column
            readonly property Component plain: row.model.control === "curve" ? curve
                                   : row.amount ? amountRow
                                   : row.model.control === "file" || row.model.control === "folder" ? path
                                   : row.noneable && (row.model.value === null || row.model.value === undefined) && !row.mixed ? noColour
                                   : ({ toggle: toggle, number: number, choice: choice, color: colour, paint: paintC, text: text, list: list })[row.model.type] || text
            Component { id: buttoned; Item {
                readonly property var input: inner.item ? inner.item.input : null      // focusWidget types here
                readonly property bool editable: inner.item ? !!inner.item.editable : false
                implicitHeight: inner.item ? inner.item.implicitHeight : Theme.field
                Loader { id: inner; anchors.left: parent.left; anchors.right: rowButton.left; anchors.rightMargin: Theme.grid
                         height: parent.height; sourceComponent: plain }
                RowButton { id: rowButton; objectName: "rowbutton:" + row.model.id; anchors.right: parent.right; height: parent.height
                            text: row.model.button ? row.model.button.label : ""; menu: row.model.button ? row.model.button.menu : []
                            onChosen: (v) => row.bridge.rowAction(v || row.model.button.id) }
            } }
            Component { id: toggle; Toggle { checked: !!row.model.value; onToggled: (v) => row.set(v) } }
            Component { id: amountRow; Item {   // an amount: the slider, then the value in its kind's words (typed there)
                readonly property var input: amountField.item ? amountField.item.input : null      // focusWidget types here
                readonly property bool editable: true
                Slider { anchors.left: parent.left; anchors.right: amountField.left; anchors.rightMargin: Theme.gap + 2
                         anchors.verticalCenter: parent.verticalCenter
                         value: row.model.value ?? 0; from: row.model.min ?? 0; to: row.model.max ?? 1
                         step: row.model.step ? row.model.step : 0.01; display: row.model.display || ""
                         defaultValue: row.model.default ?? null
                         origin: row.model.display === "pan" ? 0 : null      // pan fills from the centre
                         onEdited: (v) => row.set(v)
                         onScrubStarted: row.bridge.beginScrub(row.model.id)
                         onScrubbed: (v) => row.bridge.scrub(row.model.id, v)
                         onScrubEnded: row.bridge.endScrub() }
                Loader { id: amountField; anchors.right: parent.right; height: parent.height     // as wide as its words need ("Mixed")
                         width: Math.max(row.model.display === "db" ? Theme.amountField : Theme.amountFieldShort, item ? item.restNeeds : 0)
                         sourceComponent: number }
            } }
            Component { id: number; NumberField {
                value: row.model.value === null || row.model.value === undefined ? 0 : row.model.value
                from: row.model.min === null || row.model.min === undefined ? -1e9 : row.model.min
                to: row.model.max === null || row.model.max === undefined ? 1e9 : row.model.max
                step: row.model.step ? row.model.step : 1
                unit: row.model.mixed ? "" : row.model.unit || ""
                atRest: row.mixed
                words: row.model.words || []
                expressions: row.bridge.typesExpressions === true     // a bridge without the flag (a sub-panel) takes no typed =…
                display: row.model.display || ""
                defaultValue: row.model.default === undefined ? null : row.model.default   // double-click puts it back
                leading: [Text { visible: !!row.model.letter; text: row.model.letter || ""; color: Theme.fg3     // a pair's small letter
                                 font.family: uiFont; font.pixelSize: Theme.label }]
                onEdited: (v) => row.set(v)
                onTypedExpression: (t) => row.set(t)
                onScrubStarted: row.bridge.beginScrub(row.model.id)
                onScrubbed: (v) => row.bridge.scrub(row.model.id, v)
                onScrubEnded: row.bridge.endScrub()
                onTypingStarted: row.hold(true)
                onTypingEnded: row.hold(false) } }
            Component { id: choice; ChoiceField { options: row.model.options; current: row.model.value ?? ""; atRest: row.mixed
                                                  more: row.model.more || ""; onMoreChosen: moreDialog.open()
                                                  onPicked: (v) => row.set(v) } }
            Component { id: noColour; Text {    // a colour that may be none, while it is: its "+" sets one
                objectName: "noColour"
                text: "no colour  +"; color: noArea.containsMouse ? Theme.fg : Theme.fg3
                font.family: uiFont; font.pixelSize: Theme.body; verticalAlignment: Text.AlignVCenter
                MouseArea { id: noArea; anchors.fill: parent; anchors.margins: -4; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            onClicked: row.set(row.model.options.start) } } }
            Component { id: colour; ColorField { hex: row.model.value || "#000000"; atRest: row.mixed; scrubbed: true
                showHex: row.model.display !== "swatch"      // a param with display "swatch": no code beside it
                onEdited: (v) => row.set(v)
                onTypingStarted: row.hold(true)
                onTypingEnded: row.hold(false)
                onBegan: row.bridge.beginScrub(row.model.id)
                onLive: (v) => row.bridge.scrub(row.model.id, v)
                onEnded: row.bridge.endScrub() } }
            Component { id: paintC; PaintField {   // a fill; model.options may be {types, maxStops, stopOpacity}
                readonly property var o: row.model.options && !Array.isArray(row.model.options) ? row.model.options : ({})
                paint: row.model.value || ({ type: "none" }); atRest: row.mixed ? "Mixed" : ""; scrubbed: true
                types: o.types || ["none", "solid", "linear", "radial", "angular"]
                maxStops: o.maxStops || 8
                stopOpacity: o.stopOpacity !== false
                sources: o.sources || []; add: o.add || ""          // Painted: the paintings, and the app's New painting action
                paintIt: o.paintIt || ""; paintItNote: o.paintItNote || ""   // and its Paint it (the brush on the painting)
                rows: row.bridge.rows; rowsBridge: row.bridge; rowsHost: row.model.id     // the rows marked inside this one
                onAsked: (a) => row.bridge.rowAction(a)
                onEdited: (v) => row.set(v)
                onTypingStarted: row.hold(true)
                onTypingEnded: row.hold(false)
                onBegan: row.bridge.beginScrub(row.model.id)
                onLive: (v) => row.bridge.scrub(row.model.id, v)
                onEnded: row.bridge.endScrub() } }
            Component { id: list; ListField {
                values: row.model.value || []; choices: row.model.options || []
                minItems: row.model.minItems || 0; maxItems: row.model.maxItems === undefined ? null : row.model.maxItems
                onEdited: (v) => row.set(v) } }
            Component { id: curve; CurveField {   // a curve param's max = the top of its out range (above 1: a multiplier)
                value: row.model.value || ""; most: row.model.max ? row.model.max : 1; onEdited: (v) => row.set(v) } }
            Component { id: path; PathField {
                value: row.model.value || ""; folder: row.model.control === "folder"; nameFilters: row.model.filters || []
                atRest: row.mixed || ((row.model.words || []).find(w => w.value === row.model.value) || { label: "" }).label
                onEdited: (v) => row.set(v)
                onTypingStarted: row.hold(true)
                onTypingEnded: row.hold(false) } }
            Component { id: text; TextField { value: row.model.value || ""; atRest: row.mixed; onEdited: (v) => row.set(v)
                                                onTypingStarted: row.hold(true)
                                                onTypingEnded: row.hold(false) } }
        }
    }


    readonly property string mixed: live && model.mixed ? "Mixed" : ""       // a field's words at rest ("" = its value)
    function set(v) { bridge.setValue(model.id, v) }
    // A typed value lands on the item(s) it was typed for: the bridge holds them from the caret going in to its leaving
    // (a sub-panel's bridge, an effect's, has one item and no hold)
    function hold(on) { if (bridge.holdEdit) on ? bridge.holdEdit(model.id) : bridge.releaseEdit(model.id) }
    function flash() { if (parts) parts.flash() }
    function focusWidget() {
        const w = parts ? parts.widgetItem : null
        if (!w) return
        if (w.input && w.editable) { w.input.forceActiveFocus(); w.input.selectAll() } else w.forceActiveFocus()
    }
    function loadChoice(path) { row.bridge.loadChoice(row.model.id, path) }    // (a scripted step hands a file in: 2D `choicefile`)
}

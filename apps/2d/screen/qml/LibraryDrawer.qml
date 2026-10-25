import QtQuick
import QtQuick.Dialogs
import RostrumKit

// The Library drawer (UX_SPEC 3.27), beside the tool rail over the canvas's left edge (AppShell.leftOver: the rail
// stays put and the canvas keeps its size). Ctrl+L or the
// rail's Library button. Brand kit: the project's colours, text styles and logos (every document of the project sees
// them: screen2d/brand_view.py, rostrum2d/brand_kit.py); then this document's own text styles. Click an entry to put
// it on the selection (a colour on shapes, paths and texts; a style on texts) or, for a logo, onto the canvas.
// The + buttons appear only when they can act (a selection to take from; a project to keep the kit in).
Rectangle {
    id: drawer
    readonly property var lib: backend.library
    readonly property var paint: backend.library.paintings
    readonly property var shownKeys: lib.shown          // the rows the typed words leave: a keystroke flips rows on or off, never rebuilds them
    readonly property var counts: lib.counts
    function on(section, id) { return !lib.searching || shownKeys.indexOf(section + ":" + id) >= 0 }
    color: Theme.panel; radius: Theme.radiusPanel
    // Esc from anywhere (the window's one Esc, AppShell): first clears what was typed in the search, then closes
    EscCloses { when: drawer.visible; area: drawer; onAsked: drawer.lib.searching ? drawer.lib.setQuery("") : drawer.lib.setOpen(false) }
    onVisibleChanged: if (visible) Qt.callLater(drawer.takeKeys)    // the search has the keys as the drawer opens
    function takeKeys() { if (drawer.visible && search.visible) search.input.forceActiveFocus() }

    Text {
        id: head
        anchors { left: parent.left; leftMargin: Theme.pad; top: parent.top }
        height: Theme.header; verticalAlignment: Text.AlignVCenter
        text: "LIBRARY"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        font.weight: Font.DemiBold; font.letterSpacing: Theme.capsSpacing
    }
    IconButton { anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: head.verticalCenter }
                 glyph: "×"; kind: "ghost"; tip: "Close the library"; job: "library"; onClicked: drawer.lib.setOpen(false) }
    TextField {    // only once the Library holds more than 12 things: typing narrows every section by name, live; Enter uses the top one
        id: search
        objectName: "librarySearch"
        visible: drawer.lib.searchShown
        anchors { left: parent.left; right: parent.right; top: parent.top; leftMargin: Theme.pad; rightMargin: Theme.pad; topMargin: Theme.header }
        value: drawer.lib.query; placeholder: "Search the Library"
        onEntered: drawer.lib.useTop()
        onEscaped: drawer.lib.setQuery("")
        Connections { target: search.input; function onTextChanged() { if (search.input.activeFocus) drawer.lib.setQuery(search.input.text) } }
    }
    FileDialog {
        id: logoDialog
        title: "Choose a logo for the brand kit"
        nameFilters: ["Pictures (*.svg *.png *.jpg *.jpeg *.webp *.pdf *.psd)"]
        onAccepted: drawer.lib.addLogo(selectedFile.toString())
    }

    component Heading: Text {
        width: col.width; topPadding: Theme.gap
        color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label; font.weight: Font.DemiBold
    }
    component AddRow: Rectangle {   // "+ …" under a list: its + sits in the swatch column, its words in the names' column
        id: add
        property string text: ""
        property string help: ""
        signal clicked()
        width: col.width; height: Theme.row; radius: Theme.radiusCtl
        color: addArea.containsMouse ? Theme.hover : "transparent"
        Text { x: Theme.grid; width: 18; height: parent.height; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
               text: "+"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.heading }
        Text { x: Theme.grid + 18 + Theme.gap; height: parent.height; verticalAlignment: Text.AlignVCenter
               text: add.text; color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
        MouseArea { id: addArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: add.clicked() }
        HoverTip { text: add.text; help: add.help; hovered: addArea.containsMouse }
    }
    component AddPicked: AddRow { onClicked: drawer.lib.addFromSelection() }   // under its own section
    component Row2: Rectangle {     // one clickable entry: a name and a small line under it, × on hover
        id: entry
        property string title: ""
        property string sub: ""
        property color swatch: "transparent"
        property bool hasPicture: false      // a logo: a small picture of its file (url "" or unreadable: the "missing" mark)
        property url picture: ""
        signal picked()
        signal removed()
        property bool removable: true
        width: col.width; height: Math.max(entry.hasPicture ? 32 + 2 * Theme.grid : Theme.row, words.implicitHeight + 2 * Theme.grid); radius: Theme.radiusCtl
        color: area.containsMouse ? Theme.hover : "transparent"
        Rectangle { id: chip; visible: entry.swatch.a > 0; width: 18; height: 18; radius: 4; color: entry.swatch
                    border.color: Theme.line; anchors { left: parent.left; leftMargin: Theme.grid; verticalCenter: parent.verticalCenter } }
        Rectangle { id: pic; visible: entry.hasPicture; width: 32; height: 32; radius: 4; color: "transparent"; clip: true
                    border.color: Theme.line; anchors { left: parent.left; leftMargin: Theme.grid; verticalCenter: parent.verticalCenter }
                    readonly property bool ok: img.status === Image.Ready
                    Checker { anchors.fill: parent; anchors.margins: 1; radius: 3; cell: 4; light: "#7a7a7a"; dark: "#5a5a5a"; visible: pic.ok }
                    Image { id: img; anchors.fill: parent; anchors.margins: 2; source: entry.picture; fillMode: Image.PreserveAspectFit
                            smooth: true; cache: false; asynchronous: true; sourceSize.width: 64; sourceSize.height: 64 }
                    Text { visible: !pic.ok && img.status !== Image.Loading; anchors.centerIn: parent; text: "?"; color: Theme.danger
                           font.family: uiFont; font.pixelSize: Theme.heading; font.weight: Font.DemiBold } }
        Column {     // one line each; a long name ends in … and hover shows it whole
            id: words
            anchors { left: pic.visible ? pic.right : chip.visible ? chip.right : parent.left; leftMargin: Theme.gap; right: parent.right
                      rightMargin: 28; verticalCenter: parent.verticalCenter }
            Text { id: titleText; width: parent.width; text: entry.title; elide: Text.ElideRight; color: Theme.fg
                   font.family: uiFont; font.pixelSize: Theme.body }
            Text { id: subText; visible: !!entry.sub; width: parent.width; text: entry.sub; elide: Text.ElideRight; color: Theme.fg3
                   font.family: uiFont; font.pixelSize: Theme.label }
        }
        MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: entry.picked() }
        HoverTip { hovered: area.containsMouse && (titleText.truncated || subText.truncated)
                   text: entry.title + (entry.sub ? "
" + entry.sub : "") }
        IconButton { visible: entry.removable && (area.containsMouse || hovered); glyph: "✕"; kind: "ghost"
                     tip: "Take it out of the brand kit"
                     anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                     onClicked: entry.removed() }
    }

    Flickable {
        anchors { fill: parent; topMargin: Theme.header + (search.visible ? search.height + Theme.gap : 0); leftMargin: Theme.pad; rightMargin: Theme.pad; bottomMargin: Theme.pad }
        contentHeight: col.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: col
            width: parent.width; spacing: 2
            EmptyHint { visible: !drawer.lib.hasProject; width: col.width; topPadding: Theme.gap   // one line, no box
                        text: "A project's scenes share colours, text styles and logos here." }
            EmptyHint { objectName: "libraryNothing"; visible: drawer.lib.nothing; width: col.width; topPadding: Theme.gap
                        text: "Nothing called " + drawer.lib.query.trim() }
            // while words are typed only what they found shows: no "+" rows, and a section with nothing folds away
            readonly property bool find: drawer.lib.searching
            readonly property bool colourAdd: !find && drawer.lib.hasProject && drawer.lib.picked !== "" && drawer.lib.picked !== "texts"
            readonly property bool styleAdd: !find && drawer.lib.hasProject && drawer.lib.picked === "texts"
            Heading { visible: drawer.lib.hasProject && (drawer.counts.colors > 0 || col.colourAdd); text: "Colours" }   // an empty section is not shown: select a layer and its "This colour" is here
            Repeater { model: drawer.lib.colors
                       delegate: Row2 { required property var modelData; visible: drawer.on("colors", modelData.name); title: modelData.name; swatch: modelData.value
                                        sub: modelData.name.toUpperCase() !== modelData.value.toUpperCase() ? modelData.value.toUpperCase() : ""
                                        onPicked: drawer.lib.use("colors", modelData.name)
                                        onRemoved: drawer.lib.remove("colors", modelData.name) } }
            AddPicked { visible: col.colourAdd
                        text: "This colour"; help: "Keep the selected layer's colour in the project's brand kit." }
            Heading { visible: drawer.lib.hasProject && (drawer.counts.textStyles > 0 || col.styleAdd); text: "Text styles" }
            Repeater { model: drawer.lib.textStyles
                       delegate: Row2 { required property var modelData; visible: drawer.on("textStyles", modelData.name); title: modelData.name; swatch: modelData.color || "transparent"
                                        sub: (modelData.font || "") + (modelData.size ? " · " + modelData.size + " px" : "")
                                             + (modelData.weight ? " · " + modelData.weight : "")
                                        onPicked: drawer.lib.use("textStyles", modelData.name)
                                        onRemoved: drawer.lib.remove("textStyles", modelData.name) } }
            AddPicked { visible: col.styleAdd
                        text: "This text's style"; help: "Keep the selected text's style in the project's brand kit." }
            Heading { visible: drawer.lib.hasProject && (!col.find || drawer.counts.logos > 0); text: "Logos" }
            Repeater { model: drawer.lib.logos
                       delegate: Row2 { required property var modelData; visible: drawer.on("logos", modelData.name); title: modelData.name; hasPicture: true; picture: modelData.thumb
                                        sub: modelData.found ? "" : "File missing"
                                        onPicked: drawer.lib.placeLogo(modelData.name)
                                        onRemoved: drawer.lib.remove("logos", modelData.name) } }
            AddRow { visible: drawer.lib.hasProject && !col.find; text: "Logo…"
                     help: "Keep a logo file in the project's brand kit."
                     onClicked: logoDialog.open() }
            // the scene's own paintings (painting_library.py): shown with or without a project
            Heading { visible: drawer.paint.shown && (!col.find || drawer.counts.paintings > 0); text: "Paintings" }
            Repeater { model: drawer.lib.paintingRows
                       delegate: PaintingRow { required property var modelData; visible: drawer.on("paintings", modelData.id); p: modelData; width: col.width; canUse: drawer.paint.canUse
                                               onAsked: (what) => what === "use" ? drawer.paint.use(p.id) : what === "open" ? drawer.paint.open(p.id)
                                                        : what === "duplicate" ? drawer.paint.duplicate(p.id) : drawer.paint.remove(p.id)
                                               onRenamed: (name) => drawer.paint.rename(p.id, name) } }
            AddRow { visible: drawer.paint.shown && !col.find; objectName: "newPainting"; text: "New painting"
                     help: "A blank 512 × 512 painting that repeats seamlessly, opened to paint."
                     onClicked: drawer.paint.newPainting() }
            AddRow { visible: drawer.paint.makerName !== "" && !col.find; objectName: "paintingFromPicked"; text: "From " + drawer.paint.makerName + "'s paint"
                     help: "Make a painting from the paint on the picked layer: it becomes the layer's fill, ready to use on other layers."
                     onClicked: drawer.paint.fromPicked() }
            Heading { visible: drawer.counts.docStyles > 0; text: "This scene's text styles" }
            Repeater { model: drawer.lib.docStyles
                       delegate: Row2 { required property var modelData; visible: drawer.on("docStyles", modelData.id); title: modelData.name; swatch: modelData.color
                                        sub: modelData.font + " · " + modelData.size + " px · " + modelData.weight
                                        removable: false
                                        onPicked: if (drawer.lib.picked === "texts") drawer.lib.useDocStyle(modelData.id)
                                                  else backend.select(modelData.id) } }   // nothing to style: open it in the settings
        }
    }
}

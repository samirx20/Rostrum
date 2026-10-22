import QtQuick
import QtQuick.Dialogs
import RostrumKit

// The Library drawer (UX_SPEC 3.27), on the canvas's left; it pushes the canvas aside, never covers it. Ctrl+L or the
// tool strip's Library. Brand kit: the project's colours, text styles and logos (every document of the project sees
// them: screen2d/brand_view.py, rostrum2d/brand_kit.py); then this document's own text styles. Click an entry to put
// it on the selection (a colour on shapes, paths and texts; a style on texts) or, for a logo, onto the canvas.
// The + buttons appear only when they can act (a selection to take from; a project to keep the kit in).
Rectangle {
    id: drawer
    readonly property var lib: backend.library
    color: Theme.panel; radius: Theme.radiusPanel

    Text {
        id: head
        anchors { left: parent.left; leftMargin: Theme.pad; top: parent.top }
        height: Theme.header; verticalAlignment: Text.AlignVCenter
        text: "LIBRARY"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label
        font.weight: Font.DemiBold; font.letterSpacing: Theme.capsSpacing
    }
    IconButton { anchors { right: parent.right; rightMargin: Theme.grid; verticalCenter: head.verticalCenter }
                 glyph: "✕"; kind: "ghost"; tip: "Close the library"; onClicked: drawer.lib.setOpen(false) }
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
    component Row2: Rectangle {     // one clickable entry: a name and a small line under it, × on hover
        id: entry
        property string title: ""
        property string sub: ""
        property color swatch: "transparent"
        signal picked()
        signal removed()
        property bool removable: true
        width: col.width; height: Math.max(Theme.row, words.implicitHeight + 2 * Theme.grid); radius: Theme.radiusCtl
        color: area.containsMouse ? Theme.hover : "transparent"
        Rectangle { id: chip; visible: entry.swatch.a > 0; width: 18; height: 18; radius: 4; color: entry.swatch
                    border.color: Theme.line; anchors { left: parent.left; leftMargin: Theme.grid; verticalCenter: parent.verticalCenter } }
        Column {     // names wrap: a long brand name is read whole, never cut
            id: words
            anchors { left: chip.visible ? chip.right : parent.left; leftMargin: Theme.gap; right: parent.right
                      rightMargin: 28; verticalCenter: parent.verticalCenter }
            Text { width: parent.width; text: entry.title; wrapMode: Text.Wrap; color: Theme.fg
                   font.family: uiFont; font.pixelSize: Theme.body }
            Text { visible: !!entry.sub; width: parent.width; text: entry.sub; wrapMode: Text.WrapAnywhere; color: Theme.fg3
                   font.family: uiFont; font.pixelSize: Theme.label }
        }
        MouseArea { id: area; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: entry.picked() }
        IconButton { visible: entry.removable && (area.containsMouse || hovered); glyph: "✕"; kind: "ghost"
                     tip: "Take it out of the brand kit"
                     anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                     onClicked: entry.removed() }
    }

    Flickable {
        anchors { fill: parent; topMargin: Theme.header; leftMargin: Theme.pad; rightMargin: Theme.pad; bottomMargin: Theme.pad }
        contentHeight: col.height; clip: true; boundsBehavior: Flickable.StopAtBounds
        Column {
            id: col
            width: parent.width; spacing: 2
            Text { visible: !drawer.lib.hasProject; width: col.width; wrapMode: Text.Wrap; color: Theme.fg3
                   text: "The brand kit belongs to a project: save this scene in a project to keep colours, styles and logos for all its scenes."
                   font.family: uiFont; font.pixelSize: Theme.body }
            Heading { visible: drawer.lib.hasProject; text: "Brand kit · colours" }
            Repeater { model: drawer.lib.colors
                       delegate: Row2 { required property var modelData; title: modelData.name; swatch: modelData.value
                                        sub: modelData.name.toUpperCase() !== modelData.value.toUpperCase() ? modelData.value.toUpperCase() : ""
                                        onPicked: drawer.lib.use("colors", modelData.name)
                                        onRemoved: drawer.lib.remove("colors", modelData.name) } }
            Heading { visible: drawer.lib.hasProject; text: "Brand kit · text styles" }
            Repeater { model: drawer.lib.textStyles
                       delegate: Row2 { required property var modelData; title: modelData.name; swatch: modelData.color || "transparent"
                                        sub: (modelData.font || "") + (modelData.size ? " · " + modelData.size + " px" : "")
                                             + (modelData.weight ? " · " + modelData.weight : "")
                                        onPicked: drawer.lib.use("textStyles", modelData.name)
                                        onRemoved: drawer.lib.remove("textStyles", modelData.name) } }
            Heading { visible: drawer.lib.hasProject; text: "Brand kit · logos" }
            Repeater { model: drawer.lib.logos
                       delegate: Row2 { required property var modelData; title: modelData.name; sub: modelData.file
                                        onPicked: drawer.lib.placeLogo(modelData.name)
                                        onRemoved: drawer.lib.remove("logos", modelData.name) } }
            Row {
                visible: drawer.lib.hasProject; spacing: Theme.gap; topPadding: Theme.gap
                Button { visible: drawer.lib.picked !== ""; kind: "ghost"
                         text: drawer.lib.picked === "texts" ? "+ This text's style" : "+ This colour"
                         help: "Keep the selected text's style, or the selected layer's colour, in the project's brand kit."
                         onClicked: drawer.lib.addFromSelection() }
                Button { text: "+ Logo…"; kind: "ghost"; help: "Keep a logo file in the project's brand kit."
                         onClicked: logoDialog.open() }
            }
            Heading { visible: drawer.lib.docStyles.length > 0; text: "This scene · text styles" }
            Repeater { model: drawer.lib.docStyles
                       delegate: Row2 { required property var modelData; title: modelData.name; swatch: modelData.color
                                        sub: modelData.font + " · " + modelData.size + " px · " + modelData.weight
                                        removable: false
                                        onPicked: if (drawer.lib.picked === "texts") drawer.lib.useDocStyle(modelData.id)
                                                  else backend.select(modelData.id) } }   // nothing to style: open it in the settings
        }
    }
}

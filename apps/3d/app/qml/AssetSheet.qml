import QtQuick
import RostrumKit

// Import › Asset library: a sheet in the settings panel's place (like Lip sync), so the scene stays in view. The
// sources, each with its switch (off until the person turns it on) and a line saying what it offers; an off source
// shows nothing more. With one on: a search field and a grid of its models (thumbnails as the tiles show). Click a
// model: it downloads into the project (its tile fills) and lands on the surface in the middle of the view.
// Esc or × closes it (backend.assets: screen3d/assets_qt.py).
Panel {
    id: sheet
    objectName: "assetSheet"
    anchors.fill: parent
    readonly property var lib: backend.assets
    readonly property real availableWidth: width - 2 * bodyPad - Theme.gap      // room for the scroll bar at the right
    readonly property int columns: 2
    readonly property real tileWidth: Math.floor((availableWidth - (columns - 1) * Theme.gap) / columns)
    visible: sheet.lib.shown
    title: "Asset library"
    onVisibleChanged: if (visible) forceActiveFocus()
    Component.onCompleted: if (visible) forceActiveFocus()
    Keys.onEscapePressed: sheet.lib.close()
    headerRight: IconButton { objectName: "assetSheetClose"; glyph: "×"; kind: "ghost"; tip: "Close  Esc"; onClicked: sheet.lib.close() }
    component Words: Text { color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.body; elide: Text.ElideRight }

    SheetScroll {
        spacing: Theme.grid
        Repeater {              // the sources: name and switch, then what it offers and where
            model: sheet.lib.sources
            delegate: Column {
                id: src
                required property var modelData
                width: sheet.availableWidth
                SwitchRow {
                    width: parent.width
                    label: src.modelData.name
                    labelColumn: parent.width - 32
                    checked: src.modelData.on
                    switchName: "assetSource_" + src.modelData.id
                    onToggled: (v) => sheet.lib.setOn(src.modelData.id, v)
                }
                Words {
                    width: parent.width; color: Theme.fg3; font.pixelSize: Theme.label
                    text: src.modelData.what + " · " + src.modelData.site.replace(/^https?:\/\//, "")
                }
            }
        }
        Item { width: 1; height: Theme.grid; visible: sheet.lib.browsing !== "" }
        Segmented {             // two or more on: which one's models show
            objectName: "assetBrowse"
            visible: sheet.lib.onSources.length > 1
            options: sheet.lib.onSources; current: sheet.lib.browsing
            onPicked: (v) => sheet.lib.browse(v)
        }
        TextField {
            objectName: "assetSearch"
            visible: sheet.lib.browsing !== ""
            width: sheet.availableWidth
            value: sheet.lib.query
            placeholder: "Search models"
            onEdited: (t) => sheet.lib.search(t)
        }
        Words {
            visible: text !== ""; width: sheet.availableWidth; wrapMode: Text.WordWrap; elide: Text.ElideNone
            text: sheet.lib.busy ? "Searching…" : sheet.lib.line
            color: sheet.lib.busy ? Theme.fg3 : Theme.fg2
        }
        Flow {                  // the models: thumbnail and name; click to bring one in
            visible: sheet.lib.browsing !== ""
            width: sheet.availableWidth; spacing: Theme.gap
            Repeater {
                model: sheet.lib.browsing !== "" ? sheet.lib.models : []
                delegate: Item {
                    id: tile
                    required property var modelData
                    objectName: "assetTile_" + modelData.id
                    readonly property var getting: sheet.lib.getting[modelData.id]
                    readonly property bool loading: getting !== undefined
                    width: sheet.tileWidth; height: width + Theme.grid + name.height
                    Component.onCompleted: sheet.lib.wantThumb(modelData.id)
                    Rectangle {
                        id: frame
                        width: parent.width; height: width; radius: Theme.radiusCtl
                        color: Theme.sunken
                        border.width: 1; border.color: tileArea.containsMouse ? Theme.accent : Theme.border
                        Image {
                            anchors.fill: parent; anchors.margins: 1
                            source: sheet.lib.thumbs[tile.modelData.id] || ""
                            fillMode: Image.PreserveAspectFit; asynchronous: true; smooth: true
                        }
                        Rectangle {     // the download: a bar along the bottom of the picture
                            visible: tile.loading
                            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: Theme.grid }
                            height: 4; radius: 2; color: Theme.hover
                            Rectangle { width: parent.width * (tile.getting || 0); height: parent.height; radius: 2; color: Theme.accent }
                        }
                    }
                    Words {
                        id: name
                        y: frame.height + Theme.grid; width: parent.width
                        text: tile.modelData.name; color: Theme.fg
                        maximumLineCount: 2; wrapMode: Text.Wrap
                    }
                    MouseArea {
                        id: tileArea
                        anchors.fill: parent; hoverEnabled: true
                        cursorShape: tile.loading ? Qt.BusyCursor : Qt.PointingHandCursor
                        onClicked: sheet.lib.bringIn(tile.modelData.id)
                    }
                }
            }
        }
        Button {
            objectName: "assetMore"
            anchors.right: parent.right
            visible: sheet.lib.hasMore && !sheet.lib.busy
            text: "More"
            onClicked: sheet.lib.more()
        }
    }
}

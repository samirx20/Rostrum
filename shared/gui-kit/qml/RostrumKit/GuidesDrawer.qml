import QtQuick
import "."

// The guides drawer (INTERACTION.md 1.17): the how-to guides in a drawer on the left, beside the main view, so you
// follow along while you work (beside the tool rail; AppShell places it: pushing the view aside, or over its left edge in an app whose left column floats, `leftOver`). F1 or ? › Guides opens
// it. With no guide open it lists the app's guides; "Find in the guides" searches their titles and text. Links between
// guides open here (Back returns); a web link or any other file opens in the computer's own program. Pictures wider
// than the drawer are scaled to fit (guidePages.readAt). Esc or × closes it, and the keys go back to the work.
Panel {
    id: drawer
    objectName: "guidesDrawer"
    property var entries: []                  // the app's guides (AppShell.helpEntries: {value, label})
    property string url: ""                   // the guide shown ("" = the list)
    property string html: ""             // the guide as rich text (not `body`: that is Panel's content)
    property var back: []                     // the guides this one was reached from, newest last
    property string query: ""
    readonly property var found: guidePages.search(entries, query)
    readonly property bool listing: url === "" || query !== ""
    signal closed()
    title: "Guides"
    function show(u) { back = []; query = ""; find.input.text = ""; load(u) }
    function showList() { back = []; url = ""; html = "" }
    function search(q) { showList(); find.input.text = q; query = q.trim() }
    function load(u) { url = u; html = guidePages.readAt(u, Math.floor(page.width)); flick.contentY = 0; relay.restart() }   // again once the drawer has its width: pictures fit it
    function follow(link) {
        if (/^(https?|mailto):/i.test(link)) { Qt.openUrlExternally(link); return }
        if (link.charAt(0) === "#") return                       // a heading on this page
        const u = guidePages.resolve(url, link).split("#")[0]
        if (!/\.md$/i.test(u)) { Qt.openUrlExternally(u); return }
        back = back.concat([url]); load(u)
    }
    function goBack() {
        if (back.length === 0) { showList(); return }
        const b = back.slice(); const u = b.pop(); back = b; load(u)
    }
    headerRight: [
        Button { visible: drawer.url !== "" && !drawer.listing; text: "Back"; kind: "ghost"; onClicked: drawer.goBack()
                 help: drawer.back.length ? "Back to the guide you came from." : "Back to the list of guides." },
        IconButton { glyph: "×"; kind: "ghost"; tip: "Close the guides"; job: "guides"; onClicked: drawer.closed() }
    ]
    Keys.onEscapePressed: drawer.closed()

    FieldFrame {
        id: find
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: Theme.field
        editable: true
        placeholder: "Find in the guides"
        Connections { target: find.input; function onTextEdited() { drawer.query = find.input.text.trim() } }
        onEscaped: { find.input.text = ""; drawer.query = "" }
    }
    ListView {    // the guides, or what a search found
        id: list
        visible: drawer.listing
        anchors { left: parent.left; right: parent.right; top: find.bottom; bottom: parent.bottom; topMargin: Theme.gap }
        clip: true; boundsBehavior: Flickable.StopAtBounds
        model: drawer.found
        spacing: 0
        delegate: Rectangle {
            id: row
            required property var modelData
            width: list.width; height: words.height + 2 * Theme.gap; radius: Theme.radiusCtl
            color: rowArea.containsMouse ? Theme.hover : "transparent"
            Column {
                id: words
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter
                          leftMargin: Theme.grid; rightMargin: Theme.grid }
                Text { width: parent.width; text: row.modelData.label; elide: Text.ElideRight
                       color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
                Text { width: parent.width; visible: text !== ""; text: row.modelData.line; elide: Text.ElideRight
                       color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
            }
            Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: Theme.grid; rightMargin: Theme.grid }
                        height: 1; color: Theme.border }      // a line between the guides
            MouseArea { id: rowArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        onClicked: drawer.show(row.modelData.value) }
        }
        EmptyHint {
            visible: list.count === 0
            anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: Theme.groupGap }
            text: drawer.query ? "Nothing called “" + drawer.query + "”. Try a shorter word."
                               : "This app has no guides yet."
        }
    }
    Flickable {
        id: flick
        visible: !drawer.listing
        anchors { left: parent.left; right: parent.right; top: find.bottom; bottom: parent.bottom; topMargin: Theme.gap }
        contentWidth: width; contentHeight: page.height
        clip: true; boundsBehavior: Flickable.StopAtBounds
        onWidthChanged: if (drawer.url !== "" && width > 0) relay.restart()      // pictures fit the new width
        Timer { id: relay; interval: 120; onTriggered: drawer.html = guidePages.readAt(drawer.url, Math.floor(page.width)) }
        Text {
            id: page
            width: flick.width - Theme.grid
            textFormat: Text.RichText; wrapMode: Text.WrapAtWordBoundaryOrAnywhere  // the guide as rich text (guides.page_html): line spacing
            text: drawer.html; baseUrl: drawer.url          // on text only; pictures load from beside the guide
            color: Theme.fg; linkColor: Theme.accent
            font.family: uiFont; font.pixelSize: Theme.body + 1        // a page is read, not scanned
            onLinkActivated: (link) => drawer.follow(link)
            HoverHandler { cursorShape: page.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
        }
    }
    EdgeFade { flick: flick; visible: flick.visible; anchors.fill: flick }      // a half-scrolled line fades, never cut
    EdgeFade { flick: list; visible: list.visible; anchors.fill: list }
    VScrollBar { flick: flick; visible: flick.visible }
}

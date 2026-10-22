import QtQuick
import QtQuick.Controls as QQC
import "."

// Help → a guide, read inside the app (no outside program needed). `show(url)` opens a guide's .md file; a link to
// another guide opens in this same viewer (Back returns), a web link or any other file opens in the computer's own
// program. The Markdown is read by `guidePages` (rostrum_gui.guides.GuidePages). Esc or the × closes it.
QQC.Popup {
    id: dlg
    property string url: ""
    property string body: ""
    property var back: []                     // the guides this one was reached from, newest last
    function show(u) { back = []; load(u); open() }
    function load(u) { url = u; body = guidePages.read(u); flick.contentY = 0 }
    function follow(link) {
        if (/^(https?|mailto):/i.test(link)) { Qt.openUrlExternally(link); return }
        if (link.charAt(0) === "#") return                       // a heading on this page
        const u = guidePages.resolve(url, link).split("#")[0]
        if (!/\.md$/i.test(u)) { Qt.openUrlExternally(u); return }
        back = back.concat([url]); load(u)
    }
    function goBack() { const b = back.slice(); const u = b.pop(); back = b; load(u) }
    parent: QQC.Overlay.overlay
    x: Math.round((parent.width - width) / 2); y: Math.round((parent.height - height) / 2)
    width: Math.min(parent.width - 2 * Theme.groupGap * 2, 820); height: parent.height - 2 * Theme.groupGap * 2
    padding: 0
    objectName: "guideDialog"
    modal: true; focus: true
    QQC.Overlay.modal: Rectangle { color: Theme.scrim }
    background: Rectangle { color: Theme.panel; radius: Theme.radiusPanel; border.color: Theme.popupEdge }
    enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.fast } }
    exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.fast } }

    Row {
        anchors { right: parent.right; top: parent.top; margins: Theme.gap }
        spacing: Theme.grid
        Button { visible: dlg.back.length > 0; text: "Back"; kind: "ghost"; onClicked: dlg.goBack() }
        IconButton { glyph: "×"; kind: "ghost"; tip: "Close"; onClicked: dlg.close() }
    }
    Flickable {
        id: flick
        anchors { fill: parent; topMargin: Theme.groupGap * 2 + Theme.gap; bottomMargin: Theme.groupGap
                  leftMargin: Theme.groupGap * 2; rightMargin: Theme.groupGap * 2 }
        contentWidth: width; contentHeight: page.height
        clip: true; boundsBehavior: Flickable.StopAtBounds
        Text {
            id: page
            width: flick.width
            textFormat: Text.MarkdownText; wrapMode: Text.Wrap
            text: dlg.body; baseUrl: dlg.url             // pictures in a guide load from beside it
            color: Theme.fg; linkColor: Theme.accent; lineHeight: 1.25
            font.family: uiFont; font.pixelSize: Theme.title
            onLinkActivated: (link) => dlg.follow(link)
            HoverHandler { cursorShape: page.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
        }
    }
    VScrollBar { flick: flick }
}

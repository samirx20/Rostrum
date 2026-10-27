import QtQuick
import "."

// The start screen (INTERACTION.md 1.19 item 3, kit piece 13), one three-column grid: the ways in as tiles (New, the
// accent; Open…; the app's sample, opened as a copy), recent projects as pictures (a plain card with the name and date
// when there is none) and up to three guide cards; Continue the last project (at launch) or Back on the title's line.
// Shown when there is nothing to reopen, or from ≡ › Start screen… (then Back returns).
// Reads the app's `files` (rostrum_gui/project_files.py). Put it last in the window, filling it:
//     StartScreen { anchors.fill: parent; z: 100; onGuideAsked: (url) => shell.openGuide(url) }
// A file refused as damaged or newer, whose history can rebuild it, shows a banner on top: what is wrong, and "Open the
// last version that works" (files.openRescued(); the damaged file is kept beside, never overwritten).
// Nothing is greyed: what can't be used now is absent.
Rectangle {
    id: start
    property var source: typeof files !== "undefined" ? files : null
    property string appName: Window.window && Window.window.appName ? Window.window.appName : "Rostrum"
    signal guideAsked(string url)
    visible: !!source && source.startShown
    color: Theme.app
    focus: visible
    EscCloses { when: start.visible; covers: true; escCloses: !!start.source && start.source.hasProject; area: start
                onAsked: start.source.setStart(false) }   // over the work: its keys wait (OpenPopups.covered); Esc: back to the project
    MouseArea { anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.AllButtons }   // nothing under it is reached
    // It covers the merged top bar too: the window buttons stay, in the same place, and the strip's empty part is still
    // the window's drag room (the bar's zones tell Windows; nothing here sits in the top Theme.topBar px)
    WindowButtons { visible: windowChrome.merged; anchors { right: parent.right; top: parent.top } height: Theme.topBar; z: 5 }

    readonly property var rows: source ? source.recent : []
    readonly property bool launching: !!source && !source.hasProject && rows.length > 0      // "Continue" the last one
    readonly property var shownRows: launching ? rows.slice(1) : rows
    readonly property int margin: width >= 1600 ? 64 : 40
    // one grid of three columns for everything (the ways in, recent projects, guides): every row shares its edges
    readonly property int cardGap: Theme.groupGap
    readonly property int columns: 3
    readonly property int contentWidth: Math.min(width - 2 * margin, 960)
    readonly property int cardWidth: Math.floor((contentWidth - (columns - 1) * cardGap) / columns)
    readonly property int pictureHeight: Math.round(cardWidth * 9 / 16 * (height >= 900 ? 1 : 0.7))
    // a recent project with no picture (Sound's songs) is a plain card, name and date, as tall as those two lines: no
    // empty picture box, and more of them fit (up to four rows of three); with pictures, up to two rows
    readonly property bool pictures: shownRows.some(r => !!r.thumb)
    readonly property int cardHeight: pictures ? pictureHeight + 48 : 60
    // recent rows that fit under the top row and above the guides (at least one row)
    readonly property int recentLines: Math.max(1, Math.min(pictures ? 2 : 4, Math.floor((height - 2 * margin - 300) / (cardHeight + cardGap))))
    property string copyName: ""             // Duplicate just made this copy (its notice sits under the title)
    Connections { target: start.source; function onCopied(name) { start.copyName = name; copyTimer.restart() } }
    Timer { id: copyTimer; interval: 10000; onTriggered: start.copyName = "" }

    component Way: Rectangle {     // one way in, a tile on the grid: New (the accent), Open…, the sample
        id: way
        property string label
        property string hint                 // its key ("" keeps the line: the tiles share a baseline)
        property bool main: false
        readonly property bool hovered: wayHover.hovered
        signal picked()
        width: start.cardWidth; height: 112; radius: Theme.radiusPanel
        color: main ? (wayHover.hovered ? Theme.accentFillHover : Theme.accentFill) : (wayHover.hovered ? Theme.raised : Theme.panel)
        Column {
            anchors { left: parent.left; right: parent.right; margins: Theme.pad + 4; verticalCenter: parent.verticalCenter }
            spacing: Theme.grid
            Text { width: parent.width; text: way.label; elide: Text.ElideRight; color: way.main ? "white" : Theme.fg
                   font.family: uiFont; font.pixelSize: way.main ? 22 : Theme.heading; font.weight: Font.DemiBold }
            Text { width: parent.width; text: way.hint; elide: Text.ElideRight
                   color: way.main ? Qt.rgba(1, 1, 1, 0.96) : Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
        }
        HoverHandler { id: wayHover; cursorShape: Qt.PointingHandCursor }
        TapHandler { onTapped: way.picked() }
    }

    Column {
        id: page
        x: (start.width - start.contentWidth) / 2; y: Math.max(start.margin, Math.round((start.height - height) * 0.42))
        width: start.contentWidth
        spacing: Theme.groupGap + Theme.gap

        Item {      // the app's name; on the grid's right edge Back (a project open behind) or Continue (at launch)
            width: parent.width; height: Theme.button
            Text { anchors.verticalCenter: parent.verticalCenter; text: start.appName; color: Theme.fg
                   font.family: uiFont; font.pixelSize: Theme.heading; font.weight: Font.DemiBold }
            Button { visible: !!start.source && start.source.hasProject; anchors.right: parent.right
                     text: "Back to your " + (start.source ? start.source.noun : "project")
                     onClicked: start.source.setStart(false)
                     HoverTip { text: start.source ? "Back to " + start.source.name : ""; help: "Esc"; hovered: parent.hovered } }
            Button {
                id: cont
                visible: start.launching; anchors.right: parent.right
                kind: "primary"
                width: Math.min(implicitWidth, parent.width - 200)
                text: start.launching ? "Continue " + start.rows[0].name : ""
                onClicked: start.source.pickLater("recent:0")
                HoverTip { text: cont.text; help: start.launching ? start.rows[0].folder : ""; hovered: cont.hovered }
            }
        }

        Rectangle {     // after Duplicate: the window stays on the original; the copy is one click away
            visible: start.copyName !== ""
            width: parent.width; height: visible ? Theme.button + 2 * Theme.gap : 0
            radius: Theme.radiusPanel; color: Theme.raised; border.color: Theme.popupEdge
            Text { anchors { left: parent.left; leftMargin: Theme.pad; right: openCopy.left; rightMargin: Theme.gap
                             verticalCenter: parent.verticalCenter }
                   text: "Copy made: " + start.copyName + ". This window stays on the original."; elide: Text.ElideMiddle
                   color: Theme.fg; font.family: uiFont; font.pixelSize: Theme.body }
            Button { id: openCopy; anchors { right: parent.right; rightMargin: Theme.gap; verticalCenter: parent.verticalCenter }
                     text: "Open the copy"; kind: "primary"; onClicked: { start.copyName = ""; start.source.pickLater("copy") } }
        }

        Rectangle {     // a refused file the history can rebuild
            id: banner
            readonly property var r: start.source ? start.source.rescue : ({})
            visible: !!r.said
            width: parent.width; height: visible ? bannerBody.implicitHeight + 2 * Theme.pad : 0
            radius: Theme.radiusPanel; color: Theme.panel; border.color: Theme.warn
            Column {
                id: bannerBody
                x: Theme.pad; y: Theme.pad; width: parent.width - 2 * Theme.pad; spacing: Theme.gap
                Text { width: parent.width; text: banner.r.said || ""; wrapMode: Text.Wrap; color: Theme.fg
                       font.family: uiFont; font.pixelSize: Theme.body }
                Text { width: parent.width; text: (banner.r.words || "") + " The damaged file stays beside it, untouched."
                       wrapMode: Text.Wrap; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.label }
                Row {
                    spacing: Theme.gap
                    Button { text: "Open the last version that works"; kind: "primary"; onClicked: start.source.pickLater("rescue") }
                    Button { text: "Not now"; onClicked: start.source.dismissRescue() }
                }
            }
        }

        Row {       // the ways in: New (big, the accent), Open…, the sample
            spacing: start.cardGap
            Way { main: true; label: "+  New"; hint: start.source && start.source.keys.new ? start.source.keys.new : ""
                  onPicked: start.source.pickLater("new")
                  HoverTip { text: "New " + (start.source ? start.source.noun : ""); help: "Made at once in your projects folder, saved as you work"
                             hovered: parent.hovered } }
            Way { label: "Open…"; hint: start.source ? start.source.keys.open : ""; onPicked: start.source.pickLater("open")
                  HoverTip { text: "Open a project folder"; hovered: parent.hovered } }
            Way { visible: !!start.source && start.source.hasSample; label: "Open the sample"
                  onPicked: start.source.pickLater("sample")
                  HoverTip { text: "Open the sample"; help: "Your own copy: the original never changes"; hovered: parent.hovered } }
        }

        Column {    // recent projects
            visible: start.shownRows.length > 0
            width: parent.width; spacing: Theme.gap
            Text { text: "Recent"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.title }
            Flow {
                width: parent.width; spacing: start.cardGap
                Repeater {
                    model: start.shownRows.slice(0, start.columns * start.recentLines)
                    delegate: Rectangle {
                        id: card
                        objectName: "recentCard"
                        required property var modelData
                        required property int index
                        width: start.cardWidth; height: start.cardHeight; radius: Theme.radiusPanel
                        color: cardHover.hovered ? Theme.raised : Theme.panel
                        readonly property bool pictured: modelData.thumb !== ""     // else a plain card: name and date
                        Rectangle {
                            visible: card.pictured
                            x: Theme.grid; y: Theme.grid; width: parent.width - 2 * Theme.grid; height: start.pictureHeight - Theme.grid
                            radius: Theme.radiusCtl; color: Theme.sunken; clip: true
                            Image { anchors.fill: parent; source: card.modelData.thumb
                                    fillMode: Image.PreserveAspectCrop; asynchronous: true; cache: false }
                        }
                        Text { id: cardName; x: Theme.pad; y: card.pictured ? start.pictureHeight + 6 : (card.height - 36) / 2
                               width: parent.width - 2 * Theme.pad
                               text: card.modelData.name; elide: Text.ElideMiddle; color: Theme.fg
                               font.family: uiFont; font.pixelSize: Theme.body }
                        Text { x: Theme.pad; y: cardName.y + 20; width: parent.width - 2 * Theme.pad; text: card.modelData.when
                               elide: Text.ElideRight; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                        HoverHandler { id: cardHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: start.source.pickLater("recent:" + (start.launching ? card.index + 1 : card.index)) }
                        HoverTip { text: card.modelData.name; help: card.modelData.folder; hovered: cardHover.hovered }
                    }
                }
            }
        }

        Column {    // guides
            visible: !!start.source && start.source.guides.length > 0
            width: parent.width; spacing: Theme.gap
            Text { text: "Guides"; color: Theme.fg2; font.family: uiFont; font.pixelSize: Theme.title }
            Row {
                spacing: start.cardGap
                Repeater {
                    model: start.source ? start.source.guides : []
                    delegate: Rectangle {
                        id: guide
                        required property var modelData
                        width: start.cardWidth; height: 52; radius: Theme.radiusPanel
                        color: guideHover.hovered ? Theme.raised : Theme.panel
                        Text { id: guideName; anchors { left: parent.left; right: parent.right; margins: Theme.pad; verticalCenter: parent.verticalCenter }
                               text: guide.modelData.label; elide: Text.ElideRight; color: Theme.fg
                               font.family: uiFont; font.pixelSize: Theme.body }
                        HoverHandler { id: guideHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: start.openGuide(guide.modelData.value) }
                        HoverTip { text: guideName.truncated ? guide.modelData.label : ""; hovered: guideHover.hovered }
                    }
                }
            }
        }
    }

    function openGuide(url) {
        if (source.hasProject) source.setStart(false)
        guideAsked(url)
    }
}

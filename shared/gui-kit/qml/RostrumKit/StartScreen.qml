import QtQuick
import "."

// The start screen (INTERACTION.md 1.19 item 3, kit piece 13): New (big), Continue the last project, Open…, the app's
// sample (opened as a copy), recent projects as pictures (a plain card with the name and date when there is none) and
// up to three guide cards. Shown when there is nothing to reopen, or from ≡ › Start screen… (then Back returns).
// Reads the app's `files` (rostrum_gui/project_files.py). Put it last in the window, filling it:
//     StartScreen { anchors.fill: parent; z: 100; onGuideAsked: (url) => shell.openGuide(url) }
// Nothing is greyed: what can't be used now is absent.
Rectangle {
    id: start
    property var source: typeof files !== "undefined" ? files : null
    property string appName: Window.window && Window.window.appName ? Window.window.appName : "Rostrum"
    signal guideAsked(string url)
    visible: !!source && source.startShown
    color: Theme.app
    focus: visible
    Keys.onEscapePressed: if (source.hasProject) source.setStart(false)
    MouseArea { anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.AllButtons }   // nothing under it is reached

    readonly property var rows: source ? source.recent : []
    readonly property bool launching: !!source && !source.hasProject && rows.length > 0      // "Continue" the last one
    readonly property var shownRows: launching ? rows.slice(1) : rows
    readonly property int margin: width >= 1600 ? 64 : 40
    readonly property int contentWidth: Math.min(width - 2 * margin, 1120)
    readonly property int cardGap: Theme.groupGap
    readonly property int columns: Math.max(2, Math.floor((contentWidth + cardGap) / (208 + cardGap)))
    readonly property int cardWidth: Math.floor((contentWidth - (columns - 1) * cardGap) / columns)
    readonly property int pictureHeight: Math.round(cardWidth * 9 / 16 * (height >= 900 ? 1 : 0.7))
    readonly property int cardHeight: pictureHeight + 48
    // recent rows that fit under the top row and above the guides (at least one row, at most two)
    readonly property int recentLines: Math.max(1, Math.min(2, Math.floor((height - 2 * margin - 300) / (cardHeight + cardGap))))

    Column {
        id: page
        x: (start.width - start.contentWidth) / 2; y: Math.max(start.margin, Math.round((start.height - height) * 0.4))
        width: start.contentWidth
        spacing: Theme.groupGap + Theme.gap

        Item {      // the app's name, and Back when a project is open behind the start screen
            width: parent.width; height: Theme.button
            Text { anchors.verticalCenter: parent.verticalCenter; text: start.appName; color: Theme.fg
                   font.family: uiFont; font.pixelSize: Theme.heading; font.weight: Font.DemiBold }
            Button { visible: !!start.source && start.source.hasProject; anchors.right: parent.right
                     text: "Back to your " + (start.source ? start.source.noun : "project")
                     onClicked: start.source.setStart(false)
                     HoverTip { text: start.source ? "Back to " + start.source.name : ""; help: "Esc"; hovered: parent.hovered } }
        }

        Row {       // New (big), then the other ways in
            spacing: Theme.groupGap
            Rectangle {
                id: newTile
                width: Math.max(200, start.cardWidth); height: 112; radius: Theme.radiusPanel
                color: newHover.hovered ? Theme.accentHover : Theme.accent
                Column {
                    anchors { left: parent.left; leftMargin: Theme.pad + 4; verticalCenter: parent.verticalCenter }
                    spacing: Theme.grid
                    Text { text: "+  New"; color: "white"; font.family: uiFont; font.pixelSize: 22; font.weight: Font.DemiBold }
                    Text { text: start.source && start.source.keys.new ? start.source.keys.new : ""; color: Qt.rgba(1, 1, 1, 0.7)
                           font.family: uiFont; font.pixelSize: Theme.label; visible: text !== "" }
                }
                HoverHandler { id: newHover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: start.source.pick("new") }
                HoverTip { text: "New " + (start.source ? start.source.noun : ""); help: "Made at once in your projects folder, saved as you work"
                           hovered: newHover.hovered }
            }
            Column {
                spacing: Theme.gap
                anchors.verticalCenter: newTile.verticalCenter
                width: start.contentWidth - newTile.width - Theme.groupGap
                Button {
                    id: cont
                    visible: start.launching
                    kind: "primary"
                    width: Math.min(implicitWidth, parent.width)
                    text: start.launching ? "Continue " + start.rows[0].name : ""
                    onClicked: start.source.openRecent(0)
                    HoverTip { text: cont.text; help: start.launching ? start.rows[0].folder : ""; hovered: cont.hovered }
                }
                Row {
                    spacing: Theme.gap
                    Button { text: "Open…"; onClicked: start.source.pick("open")
                             HoverTip { text: "Open a project folder"; key: start.source ? start.source.keys.open : ""; hovered: parent.hovered } }
                    Button { visible: !!start.source && start.source.hasSample; text: "Open the sample"; onClicked: start.source.openSample()
                             HoverTip { text: "Open the sample"; help: "Your own copy: the original never changes"; hovered: parent.hovered } }
                }
            }
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
                               text: card.modelData.name; elide: Text.ElideRight; color: Theme.fg
                               font.family: uiFont; font.pixelSize: Theme.body }
                        Text { x: Theme.pad; y: cardName.y + 20; width: parent.width - 2 * Theme.pad; text: card.modelData.when
                               elide: Text.ElideRight; color: Theme.fg3; font.family: uiFont; font.pixelSize: Theme.label }
                        HoverHandler { id: cardHover; cursorShape: Qt.PointingHandCursor }
                        TapHandler { onTapped: start.source.openRecent(start.launching ? card.index + 1 : card.index) }
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

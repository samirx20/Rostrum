import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtMultimedia
import "."

// One window: top bar, project panel | viewer + timeline | inspector, and the Ctrl+K command bar on top.
// All state lives here; panels read it through `app` and change it through the functions below.
ApplicationWindow {
    id: app
    visible: true
    width: startSize[0]; height: startSize[1]
    minimumWidth: 1100; minimumHeight: 680
    title: "Rostrum — GUI proof"
    color: Theme.app
    font.family: uiFont
    font.pixelSize: Theme.body

    property string viewMode: startMode      // "viewport" | "video"
    property bool playing: true
    property int selectedIndex: 0
    property bool showFps: true
    property real duration: 20
    property real sceneTime: 0
    property real speed: 1.0
    readonly property real playhead: viewMode === "video" ? player.position / 1000 : sceneTime

    ListModel {
        id: items
        ListElement { name: "Launch film"; kind: "Edit"; glyph: "E"; length: "0:20"; size: "1920 × 1080"; rate: "60"; tint: "#c9ccd4" }
        ListElement { name: "Logo reveal"; kind: "Motion"; glyph: "M"; length: "0:06"; size: "1920 × 1080"; rate: "60"; tint: "#7fa8ff" }
        ListElement { name: "Hero product"; kind: "3D scene"; glyph: "3"; length: "0:12"; size: "3840 × 2160"; rate: "24"; tint: "#e0b48a" }
        ListElement { name: "Score"; kind: "Sound"; glyph: "S"; length: "0:20"; size: "48 kHz stereo"; rate: "—"; tint: "#9ad1b4" }
        ListElement { name: "Title comp"; kind: "Comp"; glyph: "C"; length: "0:04"; size: "1920 × 1080"; rate: "60"; tint: "#d9a3c7" }
        ListElement { name: "Product turntable"; kind: "3D scene"; glyph: "3"; length: "0:08"; size: "1920 × 1080"; rate: "30"; tint: "#b8bcc6" }
    }
    readonly property var model: items
    readonly property var current: items.get(selectedIndex)

    function seek(t) {
        t = Math.max(0, Math.min(duration, t))
        sceneTime = t
        player.position = t * 1000
    }
    function setMode(m) { var t = playhead; viewMode = m; seek(t) }
    function togglePlay() { playing = !playing }
    function select(i) { selectedIndex = (i + items.count) % items.count }
    function setTint(c) { items.setProperty(selectedIndex, "tint", c) }

    readonly property var commands: [
        { name: "Show viewport", hint: "View", run: function() { setMode("viewport") } },
        { name: "Show video", hint: "View", run: function() { setMode("video") } },
        { name: "Play / pause", hint: "Space", run: togglePlay },
        { name: "Go to start", hint: "Home", run: function() { seek(0) } },
        { name: "Show / hide frame rate", hint: "F", run: function() { showFps = !showFps } },
        { name: "Select next item", hint: "↓", run: function() { select(selectedIndex + 1) } },
        { name: "Select previous item", hint: "↑", run: function() { select(selectedIndex - 1) } },
        { name: "Reset turn speed", hint: "Viewport", run: function() { speed = 1.0 } }
    ]

    MediaPlayer {
        id: player
        source: videoUrl
        videoOutput: viewer.videoOutput
        loops: MediaPlayer.Infinite
        Component.onCompleted: { if (app.viewMode === "video" && app.playing) play(); else pause() }
    }
    onPlayingChanged: syncPlayer()
    onViewModeChanged: syncPlayer()
    function syncPlayer() { if (viewMode === "video" && playing) player.play(); else player.pause() }

    FrameAnimation {
        running: app.playing && app.viewMode === "viewport"
        onTriggered: app.sceneTime = (app.sceneTime + frameTime) % app.duration
    }

    Shortcut { sequence: "Ctrl+K"; onActivated: commandBar.open() }
    Shortcut { sequence: "Space"; enabled: !commandBar.opened; onActivated: app.togglePlay() }
    Shortcut { sequence: "Home"; enabled: !commandBar.opened; onActivated: app.seek(0) }
    Shortcut { sequence: "F"; enabled: !commandBar.opened; onActivated: app.showFps = !app.showFps }
    Shortcut { sequence: "Down"; enabled: !commandBar.opened; onActivated: app.select(app.selectedIndex + 1) }
    Shortcut { sequence: "Up"; enabled: !commandBar.opened; onActivated: app.select(app.selectedIndex - 1) }

    function shoot(path) {
        shell.grabToImage(function(result) {  // panels only: popups live in the overlay, outside shell
            var ok = result.saveToFile(path)
            console.log((ok ? "saved " : "FAILED to save ") + path)
            Qt.exit(ok ? 0 : 3)
        })
    }

    Rectangle { id: shell; anchors.fill: parent; color: Theme.app }  // what shoot() grabs (with its children)
    ColumnLayout {
        parent: shell
        anchors.fill: parent
        spacing: 0
        TopBar { app: app; onCommandClicked: commandBar.open(); Layout.fillWidth: true }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            Layout.leftMargin: Theme.gap; Layout.rightMargin: Theme.gap; Layout.bottomMargin: Theme.gap
            spacing: Theme.gap
            ProjectPanel { app: app; Layout.preferredWidth: 248; Layout.fillHeight: true }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true
                spacing: Theme.gap
                Viewer { id: viewer; app: app; Layout.fillWidth: true; Layout.fillHeight: true }
                Timeline { app: app; Layout.fillWidth: true; Layout.preferredHeight: 168 }
            }
            Inspector { app: app; Layout.preferredWidth: 280; Layout.fillHeight: true }
        }
    }

    CommandBar { id: commandBar; app: app }
    Timer { interval: 800; running: openCommandsAtStart; onTriggered: commandBar.open() }
}

pragma Singleton
import QtQuick

// Every look token of the kit, in one file: colours, type, spacing, sizes, radii, motion.
// Carried from the S1 proof (proofs/gui-qt/qml/Theme.qml): dark, Figma-simple, panels separated by
// background steps (not lines), one accent, a 4 px grid. Controls read only from here; nothing hard-codes a look.
QtObject {
    // colours: background steps, text, accent
    readonly property color app: "#141414"
    readonly property color panel: "#1c1c1c"
    readonly property color raised: "#262626"
    readonly property color hover: "#303030"
    readonly property color active: "#333333"
    readonly property color sunken: "#101010"       // viewer and timeline track wells
    readonly property color border: "#2e2e2e"
    readonly property color line: "#3a3a3a"         // field underline at rest
    readonly property color lineHover: "#5a5a5a"
    readonly property color fg: "#ececec"
    readonly property color fg2: "#a3a3a3"
    readonly property color fg3: "#8a8a8a"
    readonly property color fg4: "#5c5c5c"          // hints on dark wells
    readonly property color accent: "#4c8dff"
    readonly property color accentHover: "#6aa0ff"
    readonly property color accentSoft: Qt.rgba(76 / 255, 141 / 255, 1, 0.16)
    readonly property color danger: "#ff6b6b"
    readonly property color ok: "#4cc38a"
    readonly property color warn: "#f2b33d"
    readonly property color scrim: Qt.rgba(0, 0, 0, 0.4)
    readonly property color popupEdge: Qt.rgba(1, 1, 1, 0.08)

    // type (pixel sizes); font families come from Python (uiFont / monoFont), picked from what the system has
    readonly property int label: 11
    readonly property int body: 12
    readonly property int title: 13
    readonly property int heading: 16

    // spacing on a 4 px grid
    readonly property int grid: 4
    readonly property int gap: 8          // between panels, inside fields
    readonly property int pad: 12         // inside panels
    readonly property int groupGap: 16

    // sizes
    readonly property int topBar: 40
    readonly property int header: 32      // panel header
    readonly property int row: 28         // inspector row
    readonly property int rowDense: 24    // lists
    readonly property int field: 24       // every field box (number, text, choice, colour)
    readonly property int button: 28
    readonly property int labelColumn: 104  // inspector label column ("Shadow softness" fits)
    readonly property int sidePanel: 280
    readonly property int timeline: 184
    readonly property int popupRow: 26

    // radii
    readonly property int radiusCtl: 6
    readonly property int radiusPanel: 8

    // motion
    readonly property int fast: 120       // hover and colour changes
    readonly property int reveal: 160     // a control appearing or leaving (height + opacity)
    readonly property int revealEasing: Easing.OutCubic
    readonly property real scrubPixels: 4 // mouse pixels per step when dragging a number
}

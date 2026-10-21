pragma Singleton
import QtQuick

// The look, carried from the archive's tokens (experiment-final:src/app/ui/kit/tokens.ts): dark, Figma-simple,
// panels separated by background steps (not lines), one accent, a 4 px grid.
QtObject {
    readonly property color app: "#141414"
    readonly property color panel: "#1c1c1c"
    readonly property color raised: "#262626"
    readonly property color hover: "#2a2a2a"
    readonly property color active: "#313131"
    readonly property color border: "#2e2e2e"
    readonly property color fg: "#ececec"
    readonly property color fg2: "#a3a3a3"
    readonly property color fg3: "#929292"
    readonly property color accent: "#4c8dff"
    readonly property color accentSoft: Qt.rgba(76 / 255, 141 / 255, 1, 0.16)
    readonly property color ok: "#4cc38a"
    readonly property color warn: "#f2b33d"

    readonly property int body: 12
    readonly property int label: 11
    readonly property int title: 13

    readonly property int grid: 4
    readonly property int gap: 8          // between panels
    readonly property int pad: 12         // inside panels
    readonly property int row: 28         // inspector row
    readonly property int rowDense: 24    // lists
    readonly property int groupGap: 16
    readonly property int header: 32      // panel header
    readonly property int topBar: 40
    readonly property int radiusCtl: 6
    readonly property int radiusPanel: 8
    readonly property int fast: 120
}

#!/bin/sh
# Remake the kit screenshots. Run from the worktree root: sh shared/gui-kit/demo/make_shots.sh [out folder]
# Shell shots render offscreen with the Windows fonts; the controls sheet uses a real window (about a second)
# because hover needs a real pointer. Each run quits by itself; any failed step exits nonzero.
R="${1:-C:/Users/Sam/.rostrum/waves/results/stage2/gui-kit}"
P=".venv/Scripts/python.exe shared/gui-kit/demo/main.py"
fail=0
QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR="C:/Windows/Fonts" sh -c "
$P --step 'select cam_1' --shot '$R/shell-camera-dof-off.png' &&
$P --step 'select cam_1' --step 'set dof true' --step 'set bokeh Blades' --step 'scrub focal 52 60 85' --step 'more' --shot '$R/shell-camera-dof-on.png' &&
$P --step 'select title' --step 'set animateOn true' --step 'set direction Random' --shot '$R/shell-text-animate-on.png' &&
$P --step 'select cam_1' --step 'commands turn' --shot '$R/command-bar.png'" || fail=1
QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR="C:/Windows/Fonts" $P --step 'select key' --step 'set lightType Spot' --shot "$R/shell-light-spot.png" || fail=1
$P --sheet --shot "$R/controls-sheet.png" || fail=1
exit $fail

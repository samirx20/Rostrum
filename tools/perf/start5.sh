#!/bin/sh
# Five cold starts of each app (2D, Sound sample, Sound 16 tracks); prints each run's total, for medians.
cd "$(dirname "$0")/../.." || exit 1
PY=.venv/Scripts/python.exe
$PY tools/perf/measure_2d.py start-many 5 | tr -d '\n ' ; echo
for a in "--sample" ""; do
  for i in 1 2 3 4 5; do $PY tools/perf/measure_sound.py --start $a 2>/dev/null | grep "start total"; done
done

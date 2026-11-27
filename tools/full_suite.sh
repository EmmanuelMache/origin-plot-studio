#!/bin/bash
# full_suite.sh ROOT OUTDIR
# Runs every test file of the project in ROOT (use a CLEAN COPY of the tree, not the folder you edit in) and writes
# OUTDIR.txt with one line per file:  <name> exit=<code> <summary> pass=<n> fails=<n>   and a last line DONE.
# A release needs: every line exit=0 and fails=0. Then:  python3 tools/suite_counts.py ROOT OUTDIR.txt
# A test that stalls is stopped by its time limit and run once more on its own; the line then says so.
ROOT="$1"; OUT="$2"
if [ -z "$ROOT" ] || [ -z "$OUT" ]; then echo "usage: full_suite.sh ROOT OUTDIR" >&2; exit 2; fi
mkdir -p "$OUT"; : > "$OUT.txt"
cd "$ROOT" || exit 2
export QT_QPA_PLATFORM=offscreen MPLBACKEND=Agg OPS_NO_OPEN=1
python3 -m compileall -q origin_plot_app tools tests > "$OUT/compileall.out" 2>&1; echo "compileall exit=$?" >> "$OUT.txt"
for f in tests/test_*.py xrd_scan_generator/tests/test_engine.py; do
  n=$(basename "$f" .py); rm -f origin_plot_app/running.flag
  if [ "$n" = "test_xrd_generator" ]; then args="xrd_scan_generator/tests/fixtures/SAMPLE.xrdml"; else args=""; fi
  limit=2400; note=""
  if [ "$n" = "test_xrd_generator_actions" ]; then limit=420; fi      # known to stall now and then when run in a row
  timeout "$limit" python3 "$f" $args > "$OUT/$n.out" 2>&1; ex=$?
  if [ "$ex" -eq 124 ]; then
    cp "$OUT/$n.out" "$OUT/$n.stalled.out"; rm -f origin_plot_app/running.flag
    timeout 2400 python3 "$f" $args > "$OUT/$n.out" 2>&1; ex=$?; note="(run again after a stall) "
  fi
  mid=$(grep -E "[0-9]+ passed, [0-9]+ failed|^Ran [0-9]+ tests|^OK|^FAILED" "$OUT/$n.out" | tr '\n' ' ')
  p=$(grep -c "^PASS" "$OUT/$n.out"); fl=$(grep -c "^FAIL  " "$OUT/$n.out")
  echo "$n exit=$ex $note$mid pass=$p fails=$fl" >> "$OUT.txt"
done
echo "DONE" >> "$OUT.txt"

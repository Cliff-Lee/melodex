#!/usr/bin/env bash
# Native Qt shutdown crash capture for issue #265.
# No production modifications. Do not accept a passing pytest summary alone.
set -u -o pipefail
cd "$(dirname "$0")/.."
out="${1:-qt-native-backtrace}"
mkdir -p "$out"
tests=(
  "desktop/tests/test_playback_feature.py::test_flow_refinement_requests_new_queue_without_player_access"
  "desktop/tests/test_gui_redesign.py::test_navigation_shell_changes_before_slow_page_population"
  "desktop/tests/test_gui_redesign.py::test_heavy_pages_build_once_after_navigation_shell"
)
export QT_QPA_PLATFORM=offscreen
export PYTHONPATH=desktop
export PYTHONFAULTHANDLER=1
found=0
for attempt in $(seq 1 12); do
  log="$out/gdb-attempt-${attempt}.log"
  echo "Native Qt crash capture, independent attempt ${attempt}/12"
  gdb -nx -q -batch \
      -ex "set pagination off" \
      -ex "set confirm off" \
      -ex "run" \
      -ex "thread apply all bt 35" \
      --args python -m pytest -q --maxfail=1 "${tests[@]}" > "$log" 2>&1
  code=$?
  echo "gdb exit ${code}; matching diagnostics:"
  grep -E "QObject: shared QObject|Program received signal|Fatal Python error|passed in|exited normally" "$log" | tail -n 8 || :
  if grep -qE "Program received signal SIGSEGV|SIGSEGV, Segmentation fault" "$log"; then
    echo "Native SIGSEGV stack captured in $log"
    printf '{"native_sigsegv_captured":true,"attempt":%s}\n' "$attempt" > "$out/result.json"
    found=1
    break
  fi
done
if [[ "$found" != 1 ]]; then
  echo 'No native SIGSEGV in twelve traced executions. This is inconclusive, not a fix.'
  printf '{"native_sigsegv_captured":false,"attempt":12}\n' > "$out/result.json"
  exit 2
fi

#!/usr/bin/env bash
# P9 extension runs (subsets in config/extensions.yaml), tag "ext", order per D9.3.
#
#   bash scripts/run_ext.sh             # every extension
#   DRY=1 bash scripts/run_ext.sh       # dry runs only
#   bash scripts/run_ext.sh P INSTR     # selected: P, INSTR, CMP, R, E10
#
# Structure T on the same firms comes from the main run (identical requests are cache hits).
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/Scripts/python}
[ -x "$PY" ] || PY=python

E2=$($PY -c "import yaml;print(','.join(yaml.safe_load(open('config/extensions.yaml'))['e2_firms']))")
E8=$($PY -c "import yaml;print(','.join(yaml.safe_load(open('config/extensions.yaml'))['e8_firms']))")
REPS=10

run() {   # id, runner args
  local id=$1; shift
  echo "=== $id ==="
  $PY -m src.runner.run "$@" --reps $REPS --tag ext --dry-run
  [ -n "${DRY:-}" ] && return 0
  local try=1 rc=0
  while :; do
    rc=0; $PY -m src.runner.run "$@" --reps $REPS --tag ext || rc=$?
    [ $rc -eq 4 ] && [ $try -lt 6 ] || break
    echo "  $id: failed calls, retry $try in 120 s"; sleep 120; try=$((try + 1))
  done
  [ $rc -eq 0 ] || { echo "  $id: runner exit code $rc"; exit $rc; }
}

batches=("$@")
[ ${#batches[@]} -eq 0 ] && batches=(P INSTR CMP R E10)
for b in "${batches[@]}"; do
  case $b in
    P)     run EXT-P-E2 --experiment E2 --firms "$E2" --conditions C --agent P \
             --model primary --prompt-version v1.2
           run EXT-P-E8 --experiment E8 --firms "$E8" --agent P --model primary \
             --prompt-version v1.2 ;;
    INSTR) run EXT-INSTR --experiment E2 --firms "$E2" --conditions C --agent P \
             --model primary --prompt-version v1.2_instr ;;
    CMP)   run EXT-CMP --experiment E2 --firms "$E2" --conditions C,D --agent T \
             --model comparison --prompt-version v1.2 ;;
    R)     run EXT-R-E2 --experiment E2 --firms "$E2" --conditions C --agent R \
             --model primary --prompt-version v1.2
           run EXT-R-E8 --experiment E8 --firms "$E8" --agent R --model primary \
             --prompt-version v1.2 ;;
    E10)   run EXT-E10 --experiment E10 --firms "$E8" --agent T --model primary \
             --prompt-version v1.2 ;;
    *)     echo "unknown batch $b"; exit 1 ;;
  esac
done

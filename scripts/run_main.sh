#!/usr/bin/env bash
# P8 main run: the documented sequence of runner commands (P8 §5.1–5.2).
#
#   bash scripts/run_main.sh            # every batch, in order
#   DRY=1 bash scripts/run_main.sh      # dry runs only (job counts and cost estimates)
#   bash scripts/run_main.sh E2-M E2-S  # selected batches
#
# Each batch: dry run -> run -> monitor. The script stops when the frozen check fails or a
# monitor stop threshold is hit (exit code 3); re-running resumes from the cache.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-.venv/Scripts/python}
[ -x "$PY" ] || PY=python

COMMON="--agent T --model primary --prompt-version v1.2 --tag main"
SIZES=data/processed/size_decisions_main.parquet
ALL=(E6 E2-L E2-M E2-S SIZE E5 E3 E3-TIERS E7 E8 FIRM)

$PY scripts/check_frozen.py

run_batch() {
  local id=$1 args=$2
  echo "=== $id ==="
  $PY -m src.runner.run $args $COMMON --dry-run
  [ -n "${DRY:-}" ] && return 0
  $PY -m src.runner.run $args $COMMON
  $PY scripts/monitor.py --batch "$id"
}

batches=("$@")
[ ${#batches[@]} -eq 0 ] && batches=("${ALL[@]}")
for b in "${batches[@]}"; do
  case $b in
    E6)       run_batch E6 "--experiment E6" ;;
    E2-L|E2-M|E2-S) run_batch "$b" "--experiment E2 --groups ${b#E2-}" ;;
    SIZE)     [ -n "${DRY:-}" ] || $PY scripts/size_main.py ;;
    E5)       run_batch E5 "--experiment E5" ;;
    E3)       run_batch E3 "--experiment E3 --sizes $SIZES" ;;
    E3-TIERS) run_batch E3 "--experiment E3 --sizes $SIZES --tiers" ;;
    E7)       run_batch E7 "--experiment E7" ;;
    E8)       run_batch E8 "--experiment E8 --groups S" ;;
    FIRM)     [ -n "${DRY:-}" ] || $PY scripts/build_firm_level.py ;;
    *)        echo "unknown batch $b"; exit 1 ;;
  esac
done

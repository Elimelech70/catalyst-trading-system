#!/bin/bash
# Launcher for the cohort experiment. Runs:
#   1. data-readiness preflight
#   2. cohort assignment (15 cohorts)
#   3. the 15-cohort × 5-fold experiment (~7.5 hours on RTX 4050)
#   4. HTML comparison report
#
# Logs everything to logs/cohort_launch_<date>.log
# Designed to be scheduled via `sleep N && bash launch_cohort_experiment.sh`

set -e
cd /home/craig/catalyst/catalyst-neural

TS=$(date +%Y%m%d_%H%M%S)
LOG=logs/cohort_launch_${TS}.log

# Belt-and-suspenders: forward-returns + vol-history must be populated
echo "[$(date '+%H:%M:%S')] Preflight checks" | tee -a "$LOG"
PREFLIGHT_OK=$(venv/bin/python <<'PY' 2>&1
import sys; sys.path.insert(0, '.')
from storage.database import get_connection
conn = get_connection()
us_syms_with_fwd = conn.execute(
    "SELECT COUNT(DISTINCT symbol) AS n FROM forward_returns "
    "WHERE market='US' AND timeframe='5m'"
).fetchone()['n']
vol_dates = conn.execute(
    "SELECT COUNT(DISTINCT snapshot_date) AS n FROM realized_vol_history"
).fetchone()['n']
secs_with_vol = conn.execute(
    "SELECT COUNT(*) AS n FROM securities WHERE realized_vol_30d IS NOT NULL"
).fetchone()['n']
print(f"  US symbols with forward returns: {us_syms_with_fwd}")
print(f"  Vol history snapshot dates:      {vol_dates}")
print(f"  Securities with current vol:     {secs_with_vol}")
ok = us_syms_with_fwd >= 200 and vol_dates >= 30 and secs_with_vol >= 200
print("PREFLIGHT", "OK" if ok else "FAILED")
PY
)
echo "$PREFLIGHT_OK" | tee -a "$LOG"
if ! echo "$PREFLIGHT_OK" | grep -q "PREFLIGHT OK"; then
    echo "[$(date '+%H:%M:%S')] PREFLIGHT FAILED — aborting" | tee -a "$LOG"
    exit 1
fi

echo "" | tee -a "$LOG"
echo "[$(date '+%H:%M:%S')] Phase 1/3: Cohort assignment" | tee -a "$LOG"
venv/bin/python storage/cohort_assignment.py 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "[$(date '+%H:%M:%S')] Phase 2/3: Running 15-cohort × 5-fold experiment" | tee -a "$LOG"
venv/bin/python -u training/run_cohort_experiment.py 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "[$(date '+%H:%M:%S')] Phase 3/3: Generating comparison report" | tee -a "$LOG"
venv/bin/python training/cohort_report.py 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "[$(date '+%H:%M:%S')] All phases complete." | tee -a "$LOG"
echo "[$(date '+%H:%M:%S')] Report: Documentation/Reports/cohort_experiment_*.html" | tee -a "$LOG"

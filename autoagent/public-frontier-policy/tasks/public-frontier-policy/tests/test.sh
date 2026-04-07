#!/bin/bash
set -euo pipefail

cd /app
python agent.py --summary-json --cases-per-stratum 2 > /logs/verifier/summary.json
python /tests/score_task.py /logs/verifier/summary.json

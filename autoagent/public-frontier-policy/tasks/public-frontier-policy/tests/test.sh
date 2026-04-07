#!/bin/bash
set -euo pipefail

test -f /logs/verifier/summary.json
test -f /logs/verifier/reward.json
test -f /logs/verifier/reward.txt

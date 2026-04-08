# Public Frontier Policy

Improve the public recommendation policy for Optiqal.

Your editable surface is the file:

- `/app/agent.py`

This file contains a small `CANDIDATE_POLICY` object and a fixed adapter that scores it against the incumbent public frontier.

Goals:

1. keep the public frontier benchmark safe and plausible
2. preserve exercise-first recommendations for healthy public profiles
3. only surface conditional or Rx items when the qualifying signal is present
4. avoid unnecessary drift from the incumbent unless the benchmark result improves

Use these commands while iterating:

```bash
cd /app
python agent.py --summary-json
python agent.py --summary-json --cases-per-stratum 8 --seed-count 4
python agent.py --summary-json --emit-judge-packets /tmp/public-frontier-packets.json
```

Do not edit:

- `/tests`
- the benchmark harness internals in the fixed section of `/app/agent.py`

Focus on small, explicit policy changes.

If `PUBLIC_FRONTIER_JUDGE_VERDICTS` is present in the environment, the score
will use the hybrid judge-backed objective. Otherwise it uses hard rules only.

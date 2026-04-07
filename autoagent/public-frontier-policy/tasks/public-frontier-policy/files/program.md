# Public Frontier Policy

Only edit the `CANDIDATE_POLICY` object in `agent.py`.

Goal:

- maximize the public benchmark score
- keep healthy public profiles conservative
- only show conditional or Rx items when the qualifying signal exists

Useful commands:

```bash
cd /app
python agent.py --summary-json
python agent.py --summary-json --cases-per-stratum 8
python agent.py --summary-json --emit-judge-packets /tmp/public-frontier-packets.json
```

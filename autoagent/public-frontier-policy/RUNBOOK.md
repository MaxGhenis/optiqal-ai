# AutoAgent Runbook

This is the quickest path from the Optiqal repo to a runnable AutoAgent workspace for public frontier policy tuning.

## 1. Clone AutoAgent

```bash
git clone https://github.com/kevinrgu/autoagent.git /tmp/optiqal-autoagent
cd /tmp/optiqal-autoagent
```

## 2. Export the Optiqal sidecar into that workspace

```bash
cd /Users/maxghenis/optiqal-ai/autoagent/public-frontier-policy
python bootstrap_autoagent_workspace.py --target /tmp/optiqal-autoagent --include-root --force
```

On an existing AutoAgent clone, `--include-root` makes the Optiqal public-policy
root harness the active Harbor agent under test. Omit `--include-root` if you
only want to copy the task bundle without replacing the workspace root harness.
Use `--dry-run` first if you want to inspect the copy plan.

## 3. Install AutoAgent deps

```bash
cd /tmp/optiqal-autoagent
uv sync
docker build -f Dockerfile.base -t autoagent-base .
```

If Docker Desktop is installed on macOS, make sure its credential helper is on
your `PATH` before running Harbor:

```bash
export PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH
```

## 4. Make Optiqal importable to the root harness

Choose one:

```bash
export PYTHONPATH=/Users/maxghenis/optiqal-ai/python
```

or

```bash
python -m pip install -e /Users/maxghenis/optiqal-ai/python
```

The Harbor task environment already installs Optiqal from GitHub in its own Dockerfile. This step is for the exported root `agent.py`.

## 5. Smoke test the exported harness

```bash
cd /tmp/optiqal-autoagent
python agent.py --summary-json
python agent.py --summary-json --cases-per-stratum 8
```

## 6. Smoke test the Harbor task directly

```bash
cd /tmp/optiqal-autoagent
python agent.py --summary-json --emit-judge-packets /tmp/public-frontier-packets.json
```

Optional local verifier-style smoke:

```bash
PYTHONPATH=/Users/maxghenis/optiqal-ai/python \
python tasks/public-frontier-policy/files/agent.py --summary-json > /tmp/public-frontier-task-summary.json

HARBOR_VERIFIER_LOG_DIR=/tmp/harbor-verifier \
python tasks/public-frontier-policy/tests/score_task.py /tmp/public-frontier-task-summary.json
```

## 7. Run one Harbor benchmark pass

Optional preflight:

```bash
cd /Users/maxghenis/optiqal-ai/autoagent/public-frontier-policy
export PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH
python check_autoagent_workspace.py --workspace /tmp/optiqal-autoagent
```

Then run Harbor:

```bash
cd /tmp/optiqal-autoagent
export PATH=/Applications/Docker.app/Contents/Resources/bin:$PATH
rm -rf jobs && mkdir -p jobs
uv run harbor run \
  -p tasks/public-frontier-policy \
  --agent-import-path agent:AutoAgent \
  -o jobs \
  --job-name latest
```

## 8. Kick off the AutoAgent loop

Prompt the coding agent in the exported AutoAgent workspace with:

```text
Read program.md and let's kick off a new experiment!
```

## Interpretation

- `reward.txt` or `reward.json` near `1.0` means the candidate policy is preserving the public canaries well
- a lower score means the policy edits broke hard public-safety or plausibility checks
- emitted judge packets are for secondary review only; the hard score remains primary

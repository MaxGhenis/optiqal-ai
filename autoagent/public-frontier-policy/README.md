# AutoAgent Public Frontier Policy Harness

This is a narrow sidecar harness for optimizing Optiqal's public recommendation policy.

It is intentionally separate from the core Optiqal model. The editable surface is a single file:

- [`agent.py`](./agent.py)

That file contains:

- a small `CANDIDATE_POLICY` object
- a fixed adapter that writes the policy to a temporary JSON file
- a bridge into [`run_public_frontier_candidate.py`](../../python/scripts/run_public_frontier_candidate.py)

## Why this exists

The main model has too much surface area for safe hill-climbing.

This harness is designed so an optimizer can only change:

- lane overrides
- condition thresholds
- item-level public policy metadata
- explicit exclusions

It cannot directly rewrite:

- intervention evidence
- mortality/QALY math
- personalized protocol logic

## Basic usage

From this directory:

```bash
python agent.py --summary-json
python agent.py --summary-json --cases-per-stratum 8
python agent.py --emit-policy /tmp/candidate-policy.json
```

To generate pairwise judge packets:

```bash
python agent.py --summary-json --emit-judge-packets /tmp/public-frontier-packets.json
```

## Relationship to AutoAgent

This is not a full Harbor task repo. It is a single-file harness seed that mirrors the AutoAgent pattern:

- one editable harness file
- one score command
- a human-authored [`program.md`](./program.md)

If you want to use the official [`kevinrgu/autoagent`](https://github.com/kevinrgu/autoagent) loop, this directory is the intended harness content to transplant into a benchmark-specific AutoAgent workspace.

To export this harness into an AutoAgent-style workspace root:

```bash
python bootstrap_autoagent_workspace.py --target /path/to/autoagent-workspace
```

By default, the bootstrap preserves an existing AutoAgent root `agent.py` and
`program.md` and only overlays the task bundle. Use `--include-root` if you
want the Optiqal public-policy root harness to become the workspace’s active
Harbor agent under test. Use `--dry-run` to inspect the copy plan and `--force`
to overwrite existing files.

For the exact bootstrap and first-run sequence, see:

- [`RUNBOOK.md`](./RUNBOOK.md)

There is also a Harbor-style task bundle here:

- [`tasks/public-frontier-policy`](./tasks/public-frontier-policy)

That task bundle includes:

- task-local `files/agent.py`
- `instruction.md`
- `task.toml`
- an environment Dockerfile
- verifier scripts that score the candidate policy from `agent.py --summary-json`

"""Invariants of the hybrid public-frontier score and the optimizer reward.

The hybrid score feeds the AutoAgent reward when judge verdicts are present, so
its ordering is what the optimizer climbs. These tests pin the documented
priority: a hard-rule failure never outranks a perfect hard score, fixing a
failure never lowers the score, and the judge only moves a perfect hard score.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from optiqal.public_frontier_benchmark import compute_hybrid_public_frontier_score

REPO_ROOT = Path(__file__).resolve().parents[2]
SIDECAR_ROOT = REPO_ROOT / "autoagent" / "public-frontier-policy"
ROOT_AGENT = SIDECAR_ROOT / "agent.py"
SCORE_TASK = (
    SIDECAR_ROOT / "tasks" / "public-frontier-policy" / "tests" / "score_task.py"
)

UNIT = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)
HARD_FAILURE = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, exclude_max=True
)
# Mixes exact 1.0 into generated hard scores so the step to a perfect hard
# score is exercised, not only the interior.
HARD = st.one_of(st.just(1.0), UNIT)
WEIGHT_BELOW_ONE = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, exclude_max=True
)
ANY_FINITE_WEIGHT = st.floats(allow_nan=False, allow_infinity=False)
PROPERTY_SETTINGS = settings(max_examples=400, deadline=None)


def hybrid(hard: float, judge: float | None, weight: float = 0.2) -> float:
    return compute_hybrid_public_frontier_score(
        hard_score=hard, judge_score=judge, judge_weight=weight
    )


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _harness_summary(hard: float, judge: float, weight: float = 0.2) -> dict:
    """Summary shaped like the harness output in judge-backed mode."""
    return {
        "comparison": {
            "candidate_score": hard,
            "incumbent_score": 0.9,
            "score_delta": hard - 0.9,
            "changed_case_count": 1,
        },
        "judge_score": judge,
        "hybrid_score": hybrid(hard, judge, weight),
    }


# ---------------------------------------------------------------------------
# Regressions from the 2026-09-25 invariants audit
# ---------------------------------------------------------------------------


def test_fixing_the_last_hard_failure_raises_the_hybrid_score() -> None:
    # Audit's minimized input: before the fix, hard .9 scored .9 and the
    # repaired hard 1.0 scored .8 at judge 0 and the default weight .2.
    assert hybrid(0.9, 0.0) == pytest.approx(0.72)
    assert hybrid(1.0, 0.0) == pytest.approx(0.8)
    assert hybrid(0.9, 0.0) < hybrid(1.0, 0.0)


@pytest.mark.parametrize(
    ("hard", "judge", "expected_before_repair"),
    [
        # One failure in the 114 canonical checks (verifier's input).
        (113 / 114, 0.0, 0.8 * 113 / 114),
        (0.99, 0.4, 0.792),
    ],
)
def test_one_near_perfect_failure_ranks_below_its_repair(
    hard: float, judge: float, expected_before_repair: float
) -> None:
    before = hybrid(hard, judge)
    after = hybrid(1.0, judge)
    assert before == pytest.approx(expected_before_repair)
    assert after == pytest.approx(0.8 + 0.2 * judge)
    assert before < after


def test_exhaustive_grid_orders_hard_scores_before_judge_scores() -> None:
    hards = [i / 10 for i in range(11)]
    judges = (0.0, 0.25, 0.5, 0.75, 1.0)
    weights = (0.0, 0.1, 0.2, 0.5, 0.9, 1.0)
    for weight in weights:
        for judge in judges:
            scores = [hybrid(hard, judge, weight) for hard in hards]
            assert all(0.0 <= score <= 1.0 for score in scores)
            assert scores == sorted(scores), (weight, judge, scores)
        perfect = [hybrid(1.0, judge, weight) for judge in judges]
        assert perfect == sorted(perfect), (weight, perfect)
        failing = [
            hybrid(hard, judge, weight) for hard in hards[:-1] for judge in judges
        ]
        if weight < 1.0:
            assert max(failing) < min(perfect), (weight, failing, perfect)
        else:
            assert max(failing) <= min(perfect), (weight, failing, perfect)


# ---------------------------------------------------------------------------
# Properties for every input
# ---------------------------------------------------------------------------


@PROPERTY_SETTINGS
@given(hard=HARD, judge=st.one_of(st.none(), UNIT), weight=ANY_FINITE_WEIGHT)
def test_hybrid_score_is_bounded(hard, judge, weight) -> None:
    score = hybrid(hard, judge, weight)
    assert math.isfinite(score)
    assert 0.0 <= score <= 1.0


@PROPERTY_SETTINGS
@given(
    failing=HARD_FAILURE,
    failing_judge=UNIT,
    perfect_judge=UNIT,
    weight=WEIGHT_BELOW_ONE,
)
def test_any_hard_failure_ranks_strictly_below_any_perfect_hard_score(
    failing, failing_judge, perfect_judge, weight
) -> None:
    assert hybrid(failing, failing_judge, weight) < hybrid(1.0, perfect_judge, weight)


@PROPERTY_SETTINGS
@given(failing=HARD_FAILURE, failing_judge=UNIT, perfect_judge=UNIT)
def test_full_judge_weight_never_lets_a_failure_outrank_a_perfect_score(
    failing, failing_judge, perfect_judge
) -> None:
    assert hybrid(failing, failing_judge, 1.0) == 0.0
    assert hybrid(1.0, perfect_judge, 1.0) == perfect_judge
    assert hybrid(failing, failing_judge, 1.0) <= hybrid(1.0, perfect_judge, 1.0)


@PROPERTY_SETTINGS
@given(pair=st.tuples(HARD, HARD), judge=UNIT, weight=ANY_FINITE_WEIGHT)
def test_hybrid_score_is_non_decreasing_in_hard_score(pair, judge, weight) -> None:
    lower, higher = sorted(pair)
    assert hybrid(lower, judge, weight) <= hybrid(higher, judge, weight)


@PROPERTY_SETTINGS
@given(pair=st.tuples(UNIT, UNIT), weight=ANY_FINITE_WEIGHT)
def test_perfect_hard_score_is_non_decreasing_in_judge_score(pair, weight) -> None:
    lower, higher = sorted(pair)
    assert hybrid(1.0, lower, weight) <= hybrid(1.0, higher, weight)


@PROPERTY_SETTINGS
@given(hard=HARD_FAILURE, judges=st.tuples(UNIT, UNIT), weight=ANY_FINITE_WEIGHT)
def test_judge_is_ignored_while_a_hard_rule_fails(hard, judges, weight) -> None:
    assert hybrid(hard, judges[0], weight) == hybrid(hard, judges[1], weight)


@PROPERTY_SETTINGS
@given(hard=HARD, weight=ANY_FINITE_WEIGHT)
def test_hard_only_mode_returns_the_hard_score(hard, weight) -> None:
    assert hybrid(hard, None, weight) == hard


@PROPERTY_SETTINGS
@given(
    hard=HARD,
    judge=UNIT,
    weight=st.floats(max_value=0.0, allow_nan=False, allow_infinity=False),
)
def test_zero_judge_weight_returns_the_hard_score(hard, judge, weight) -> None:
    # Weights at or below zero clamp to zero.
    assert hybrid(hard, judge, weight) == hard


@PROPERTY_SETTINGS
@given(hard=HARD, judge=UNIT, weight=WEIGHT_BELOW_ONE)
def test_hybrid_score_matches_the_closed_form(hard, judge, weight) -> None:
    # Independent statement of the documented rule.
    expected = (1 - weight) * hard if hard < 1 else (1 - weight) + weight * judge
    assert hybrid(hard, judge, weight) == pytest.approx(expected, abs=1e-15)


@pytest.mark.parametrize(
    ("hard", "judge", "weight"),
    [
        (math.nan, 0.5, 0.2),
        (-0.01, 0.5, 0.2),
        (1.01, 0.5, 0.2),
        (math.inf, 0.5, 0.2),
        (1.0, math.nan, 0.2),
        (1.0, -0.01, 0.2),
        (1.0, 1.01, 0.2),
        (1.0, 0.5, math.nan),
        (1.0, 0.5, math.inf),
    ],
)
def test_invalid_scores_are_rejected(hard, judge, weight) -> None:
    with pytest.raises(ValueError):
        hybrid(hard, judge, weight)


# ---------------------------------------------------------------------------
# The optimizer reward built from the hybrid score
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def root_agent():
    return _load_module("optiqal_test_root_frontier_agent", ROOT_AGENT)


def test_root_agent_reward_rises_when_the_last_hard_failure_is_fixed(
    root_agent,
) -> None:
    weight = root_agent.DEFAULT_JUDGE_WEIGHT
    before, _ = root_agent.compute_reward(_harness_summary(0.9, 0.0, weight))
    after, diagnostics = root_agent.compute_reward(_harness_summary(1.0, 0.0, weight))
    assert before == pytest.approx(0.72)
    assert after == pytest.approx(0.8)
    assert before < after
    assert diagnostics["score_mode"] == "hybrid"


@settings(max_examples=200, deadline=None)
@given(pair=st.tuples(HARD, HARD), judge=UNIT)
def test_root_agent_reward_is_non_decreasing_in_hard_score(
    root_agent, pair, judge
) -> None:
    lower, higher = sorted(pair)
    weight = root_agent.DEFAULT_JUDGE_WEIGHT
    low_reward, _ = root_agent.compute_reward(_harness_summary(lower, judge, weight))
    high_reward, _ = root_agent.compute_reward(_harness_summary(higher, judge, weight))
    assert low_reward <= high_reward
    if lower < 1.0 and higher == 1.0:
        assert low_reward < high_reward


def test_harbor_score_task_reward_rises_when_the_last_hard_failure_is_fixed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    score_task = _load_module("optiqal_test_frontier_score_task", SCORE_TASK)
    rewards = []
    for hard in (0.9, 1.0):
        summary_path = tmp_path / f"summary-{hard}.json"
        summary_path.write_text(json.dumps(_harness_summary(hard, 0.0)))
        logs_dir = tmp_path / f"logs-{hard}"
        monkeypatch.setenv("HARBOR_VERIFIER_LOG_DIR", str(logs_dir))
        monkeypatch.setattr(sys, "argv", ["score_task.py", str(summary_path)])
        score_task.main()
        rewards.append(float((logs_dir / "reward.txt").read_text()))
    assert rewards[0] == pytest.approx(0.72)
    assert rewards[1] == pytest.approx(0.8)
    assert rewards[0] < rewards[1]

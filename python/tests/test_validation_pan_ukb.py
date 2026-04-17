from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import textwrap

import pandas as pd
import pytest

from optiqal.validation.pan_ukb import (
    _weighted_median_bootstrap_se,
    build_pan_ukb_paths,
    generate_wget_script,
    get_default_pan_ukb_data_dir,
    harmonize_data,
    main,
    run_mr,
)


def test_default_pan_ukb_data_dir_uses_cache_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPTIQAL_PAN_UKB_DATA_DIR", raising=False)
    monkeypatch.delenv("OPTIQAL_VALIDATION_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    assert get_default_pan_ukb_data_dir() == (
        tmp_path / "cache" / "optiqal" / "validation" / "pan-ukb"
    )


def test_exact_pan_ukb_env_override_wins(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPTIQAL_VALIDATION_DATA_DIR", str(tmp_path / "validation-root"))
    monkeypatch.setenv("OPTIQAL_PAN_UKB_DATA_DIR", str(tmp_path / "explicit-pan-ukb"))

    paths = build_pan_ukb_paths()

    assert paths.root == tmp_path / "explicit-pan-ukb"
    assert paths.sumstats_dir == tmp_path / "explicit-pan-ukb" / "sumstats"
    assert paths.results_dir == tmp_path / "explicit-pan-ukb" / "results"


def test_validation_root_env_appends_pan_ukb(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPTIQAL_PAN_UKB_DATA_DIR", raising=False)
    monkeypatch.setenv("OPTIQAL_VALIDATION_DATA_DIR", str(tmp_path / "validation-root"))

    paths = build_pan_ukb_paths()

    assert paths.root == tmp_path / "validation-root" / "pan-ukb"


def test_generate_wget_script_targets_sumstats_dir(tmp_path: Path) -> None:
    paths = build_pan_ukb_paths(tmp_path / "custom-pan-ukb")

    script = generate_wget_script(paths, ["bmi", "t2dm"])

    assert f'OUTPUT_DIR="{paths.sumstats_dir}"' in script
    assert "$OUTPUT_DIR/bmi.tsv.bgz" in script
    assert "$OUTPUT_DIR/t2dm.tsv.bgz" in script
    assert "$OUTPUT_DIR/mi.tsv.bgz" not in script


def test_cli_describe_mentions_default_data_dir(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    monkeypatch.delenv("OPTIQAL_PAN_UKB_DATA_DIR", raising=False)
    monkeypatch.delenv("OPTIQAL_VALIDATION_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))

    exit_code = main(["describe"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "optiqal-pan-ukb download" in output
    assert str(tmp_path / "cache" / "optiqal" / "validation" / "pan-ukb") in output


def test_harmonize_data_recovers_flipped_outcome_alleles() -> None:
    instruments = pd.DataFrame(
        [
            {
                "chr": 1,
                "pos": 100,
                "ref": "A",
                "alt": "G",
                "SNP": "1:100:A:G",
                "beta_EUR": 0.2,
                "se_EUR": 0.04,
            },
            {
                "chr": 1,
                "pos": 200,
                "ref": "C",
                "alt": "T",
                "SNP": "1:200:C:T",
                "beta_EUR": 0.3,
                "se_EUR": 0.05,
            },
        ]
    )
    outcome = pd.DataFrame(
        [
            {
                "chr": 1,
                "pos": 100,
                "ref": "A",
                "alt": "G",
                "beta_EUR": 0.1,
                "se_EUR": 0.02,
                "neglog10_pval_EUR": 6.0,
                "af_EUR": 0.2,
            },
            {
                "chr": 1,
                "pos": 200,
                "ref": "T",
                "alt": "C",
                "beta_EUR": 0.15,
                "se_EUR": 0.03,
                "neglog10_pval_EUR": 5.0,
                "af_EUR": 0.7,
            },
        ]
    )

    harmonized = harmonize_data(instruments, outcome)

    assert list(harmonized["SNP"]) == ["1:100:A:G", "1:200:C:T"]
    flipped = harmonized.loc[harmonized["SNP"] == "1:200:C:T"].iloc[0]
    assert flipped["beta_out"] == -0.15
    assert flipped["af_out"] == pytest.approx(0.3)


def test_run_mr_inflates_uncertainty_when_exposure_se_increases() -> None:
    low_uncertainty = pd.DataFrame(
        {
            "beta_EUR": [0.20, 0.24, 0.28, 0.32],
            "se_EUR": [0.005, 0.005, 0.005, 0.005],
            "beta_out": [0.10, 0.13, 0.135, 0.175],
            "se_out": [0.02, 0.018, 0.021, 0.019],
        }
    )
    high_uncertainty = low_uncertainty.copy()
    high_uncertainty["se_EUR"] = [0.05, 0.05, 0.05, 0.05]

    low_results = run_mr(low_uncertainty).set_index("method")
    high_results = run_mr(high_uncertainty).set_index("method")

    assert high_results.loc["IVW", "se"] > low_results.loc["IVW", "se"]
    assert high_results.loc["MR-Egger", "se"] > low_results.loc["MR-Egger", "se"]
    assert (
        high_results.loc["Weighted Median", "se"]
        > low_results.loc["Weighted Median", "se"]
    )


def test_harmonize_data_drops_palindromic_by_default() -> None:
    instruments = pd.DataFrame(
        [
            {
                "chr": 1,
                "pos": 100,
                "ref": "A",
                "alt": "G",
                "SNP": "1:100:A:G",
                "beta_EUR": 0.2,
                "se_EUR": 0.04,
            },
            {
                "chr": 2,
                "pos": 300,
                "ref": "A",
                "alt": "T",
                "SNP": "2:300:A:T",
                "beta_EUR": 0.15,
                "se_EUR": 0.03,
            },
            {
                "chr": 3,
                "pos": 500,
                "ref": "C",
                "alt": "G",
                "SNP": "3:500:C:G",
                "beta_EUR": 0.1,
                "se_EUR": 0.02,
            },
        ]
    )
    outcome = pd.DataFrame(
        [
            {
                "chr": 1, "pos": 100, "ref": "A", "alt": "G",
                "beta_EUR": 0.05, "se_EUR": 0.01,
                "neglog10_pval_EUR": 5.0, "af_EUR": 0.2,
            },
            {
                "chr": 2, "pos": 300, "ref": "A", "alt": "T",
                "beta_EUR": 0.04, "se_EUR": 0.01,
                "neglog10_pval_EUR": 4.0, "af_EUR": 0.3,
            },
            {
                "chr": 3, "pos": 500, "ref": "C", "alt": "G",
                "beta_EUR": 0.03, "se_EUR": 0.01,
                "neglog10_pval_EUR": 3.0, "af_EUR": 0.4,
            },
        ]
    )

    dropped = harmonize_data(instruments, outcome)
    assert list(dropped["SNP"]) == ["1:100:A:G"]

    kept = harmonize_data(instruments, outcome, drop_palindromic=False)
    assert set(kept["SNP"]) == {"1:100:A:G", "2:300:A:T", "3:500:C:G"}


def test_weighted_median_bootstrap_se_is_deterministic_with_seed() -> None:
    import numpy as np

    rng_kwargs = dict(
        beta_exp=np.array([0.20, 0.24, 0.28, 0.32, 0.30]),
        se_exp=np.array([0.01, 0.012, 0.009, 0.011, 0.010]),
        beta_out=np.array([0.10, 0.13, 0.135, 0.175, 0.15]),
        se_out=np.array([0.02, 0.018, 0.021, 0.019, 0.020]),
        weights=np.array([2500.0, 3086.0, 2268.0, 2770.0, 2500.0]),
        n_boot=200,
    )

    first = _weighted_median_bootstrap_se(**rng_kwargs, seed=42)
    second = _weighted_median_bootstrap_se(**rng_kwargs, seed=42)
    third = _weighted_median_bootstrap_se(**rng_kwargs, seed=17)

    assert first == second
    assert first != third
    assert first > 0


def test_download_wrapper_help_runs_without_scientific_stack_imports() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "download-pan-ukb.py"

    assert os.access(script_path, os.X_OK)

    driver = textwrap.dedent(
        f"""
        import builtins
        import runpy
        import sys

        script_path = {str(script_path)!r}
        blocked = {{"numpy", "pandas", "scipy"}}
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name.split(".")[0] in blocked:
                raise ModuleNotFoundError(name)
            return real_import(name, globals, locals, fromlist, level)

        builtins.__import__ = fake_import
        sys.argv = [script_path, "--help"]
        runpy.run_path(script_path, run_name="__main__")
        """
    )

    result = subprocess.run(
        [sys.executable, "-c", driver],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "DOWNLOAD METHODS" in result.stdout

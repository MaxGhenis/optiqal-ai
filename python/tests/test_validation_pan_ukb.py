from __future__ import annotations

from pathlib import Path

from optiqal.validation.pan_ukb import (
    build_pan_ukb_paths,
    generate_wget_script,
    get_default_pan_ukb_data_dir,
    main,
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

"""Unit tests for extract_tot_metrics.py."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "extract_tot_metrics.py"
FIXTURE = Path(__file__).parent / "fixtures" / "sample_tot_regress.dat"


def run_extract(dump_path: Path) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(dump_path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def test_extracts_tr_scalars():
    data = run_extract(FIXTURE)
    assert data["NT"] == 10
    assert data["NRMAX"] == 2
    assert data["NSMAX"] == 2
    assert data["scalars"]["T"] == 2.0
    assert data["scalars"]["WPT"] == 41.13
    assert data["scalars"]["Q0"] == 0.579
    assert "AJRFT" in data["scalars"]
    assert data["scalars"]["AJRFT"] == 0.0


def test_extracts_module_presence():
    data = run_extract(FIXTURE)
    assert data["modules"]["TR_PRESENT"] == 1
    assert data["modules"]["TI_PRESENT"] == 0
    assert data["modules"]["FP_PRESENT"] == 0
    assert data["modules"]["WR_PRESENT"] == 0


def test_extracts_profile():
    data = run_extract(FIXTURE)
    prof = data["profile"]
    assert len(prof) == 2
    assert prof[0]["NR"] == 1
    assert len(prof[0]["RN"]) == 2
    assert prof[0]["AJ"] == 15.451


def test_handles_tr_absent(tmp_path):
    dump = tmp_path / "no_tr.dat"
    dump.write_text(
        "# TASK/TOT regression dump (format v1)\n"
        "TR_PRESENT=0\n"
        "TI_PRESENT=0\n"
        "FP_PRESENT=0\n"
        "WR_PRESENT=0\n"
    )
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(dump)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(result.stdout)
    assert data["modules"]["TR_PRESENT"] == 0
    assert data["scalars"] == {}
    assert data["profile"] == []
    # NT/NRMAX/NSMAX may be missing — extract should not crash
    assert data["NRMAX"] == 0

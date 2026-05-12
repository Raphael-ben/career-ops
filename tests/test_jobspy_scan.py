"""Tests for jobspy_scan.py — interface and output schema only (no real HTTP calls)."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = str(Path(__file__).parent.parent / "jobspy_scan.py")


def test_dry_run_exits_zero():
    result = subprocess.run(
        [sys.executable, SCRIPT, "--dry-run"],
        capture_output=True, text=True
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"


def test_dry_run_outputs_valid_json():
    result = subprocess.run(
        [sys.executable, SCRIPT, "--dry-run"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    assert isinstance(data, list)


def test_dry_run_job_schema():
    result = subprocess.run(
        [sys.executable, SCRIPT, "--dry-run"],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout)
    assert len(data) >= 1
    job = data[0]
    for field in ("title", "company", "url", "source", "location", "date_posted"):
        assert field in job, f"missing field: {field}"


def test_missing_config_exits_nonzero():
    result = subprocess.run(
        [sys.executable, SCRIPT, "--config", "nonexistent.yml"],
        capture_output=True, text=True
    )
    assert result.returncode != 0


def test_help_flag():
    result = subprocess.run(
        [sys.executable, SCRIPT, "--help"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "dry-run" in result.stdout

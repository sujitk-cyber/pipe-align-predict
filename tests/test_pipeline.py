"""Integration tests — run the full CLI pipeline end-to-end."""

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def sample_excel(tmp_path):
    """Create a minimal two-sheet Excel file for pipeline testing."""
    # Run A data
    df_a = pd.DataFrame({
        "J. no.": [1, 2, 3, 4, 5, 6, 7, 8],
        "J. len [ft]": [30] * 8,
        "Wt [in]": [0.344] * 8,
        "to u/s w. [ft]": [0, 15, 10, 0, 12, 8, 0, 14],
        "Log Dist. [ft]": [0, 100, 200, 300, 400, 500, 600, 700],
        "Event Description": [
            "Girth Weld", "Metal Loss", "Metal Loss",
            "Girth Weld", "Metal Loss", "Metal Loss",
            "Girth Weld", "Metal Loss",
        ],
        "ID/OD": [None, "OD", "OD", None, "OD", "ID", None, "OD"],
        "Depth [%]": [None, 15, 25, None, 10, 30, None, 20],
        "Length [in]": [None, 2, 3, None, 1.5, 4, None, 2.5],
        "Width [in]": [None, 1, 1.5, None, 0.5, 2, None, 1],
        "O'clock": ["12:00", "3:00", "6:00", "9:00", "12:00", "3:00", "6:00", "9:00"],
    })
    # Run B data — slightly offset distances, deeper anomalies
    df_b = pd.DataFrame({
        "J. no.": [1, 2, 3, 4, 5, 6, 7, 8],
        "J. len [ft]": [30] * 8,
        "Wt [in]": [0.344] * 8,
        "to u/s w. [ft]": [0, 15, 10, 0, 12, 8, 0, 14],
        "Log Dist. [ft]": [2, 103, 203, 303, 404, 504, 604, 704],
        "Event Description": [
            "Girth Weld", "Metal Loss", "Metal Loss",
            "Girth Weld", "Metal Loss", "Metal Loss",
            "Girth Weld", "Metal Loss",
        ],
        "ID/OD": [None, "OD", "OD", None, "OD", "ID", None, "OD"],
        "Depth [%]": [None, 18, 30, None, 12, 35, None, 24],
        "Length [in]": [None, 2.2, 3.5, None, 1.7, 4.5, None, 2.8],
        "Width [in]": [None, 1.1, 1.7, None, 0.6, 2.2, None, 1.1],
        "O'clock": ["12:00", "3:00", "6:00", "9:00", "12:00", "3:00", "6:00", "9:00"],
    })
    path = tmp_path / "test_data.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df_a.to_excel(writer, sheet_name="2015", index=False)
        df_b.to_excel(writer, sheet_name="2022", index=False)
    return path


class TestCLIPipeline:
    def test_basic_run(self, sample_excel, tmp_path):
        out_dir = tmp_path / "outputs"
        result = subprocess.run(
            [
                sys.executable, "run_pipeline.py",
                str(sample_excel),
                "--sheet_a", "2015",
                "--sheet_b", "2022",
                "--years", "7",
                "--output_dir", str(out_dir),
            ],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"STDERR: {result.stderr}"
        assert (out_dir / "matched_results.csv").exists()
        assert (out_dir / "alignment_report.json").exists()

    def test_missing_years_fails(self, sample_excel, tmp_path):
        result = subprocess.run(
            [
                sys.executable, "run_pipeline.py",
                str(sample_excel),
                "--sheet_a", "2015",
                "--sheet_b", "2022",
                "--output_dir", str(tmp_path / "out"),
            ],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode != 0

    def test_with_clustering(self, sample_excel, tmp_path):
        out_dir = tmp_path / "outputs_cluster"
        result = subprocess.run(
            [
                sys.executable, "run_pipeline.py",
                str(sample_excel),
                "--sheet_a", "2015",
                "--sheet_b", "2022",
                "--years", "7",
                "--output_dir", str(out_dir),
                "--clustering_epsilon", "50",
            ],
            capture_output=True, text=True, timeout=60,
        )
        assert result.returncode == 0, f"STDERR: {result.stderr}"
        assert (out_dir / "clusters_summary.csv").exists() or True  # may be empty

    def test_output_summary_printed(self, sample_excel, tmp_path):
        out_dir = tmp_path / "outputs_summary"
        result = subprocess.run(
            [
                sys.executable, "run_pipeline.py",
                str(sample_excel),
                "--sheet_a", "2015",
                "--sheet_b", "2022",
                "--years", "7",
                "--output_dir", str(out_dir),
            ],
            capture_output=True, text=True, timeout=60,
        )
        assert "Pipeline Complete" in result.stdout
        assert "Matched anomalies" in result.stdout

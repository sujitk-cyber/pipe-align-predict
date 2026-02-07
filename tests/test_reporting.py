"""Tests for src/reporting.py — CSV/JSON output generation."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.reporting import (
    write_matched_csv,
    write_missing_csv,
    write_new_csv,
    write_summary_csv,
    write_dig_list_csv,
    build_alignment_report,
    write_alignment_report,
    write_all_outputs,
)


@pytest.fixture
def growth_df(matched_df):
    """matched_df with growth columns added."""
    from src.growth import run_growth_analysis
    gdf, _ = run_growth_analysis(matched_df, years_between=7.0)
    return gdf


@pytest.fixture
def summary_df(matched_df):
    from src.growth import run_growth_analysis
    _, sdf = run_growth_analysis(matched_df, years_between=7.0)
    return sdf


class TestWriteCSVs:
    def test_matched(self, growth_df, tmp_path):
        p = tmp_path / "matched.csv"
        write_matched_csv(growth_df, p)
        assert p.exists()
        df = pd.read_csv(p)
        assert len(df) == len(growth_df)

    def test_missing(self, tmp_path):
        df = pd.DataFrame({"feature_id": ["x"], "distance": [100.0], "status": ["MISSING"]})
        p = tmp_path / "missing.csv"
        write_missing_csv(df, p)
        assert p.exists()

    def test_new(self, tmp_path):
        df = pd.DataFrame({"feature_id": ["y"], "distance": [200.0], "status": ["NEW"]})
        p = tmp_path / "new.csv"
        write_new_csv(df, p)
        assert p.exists()

    def test_summary(self, summary_df, tmp_path):
        p = tmp_path / "summary.csv"
        write_summary_csv(summary_df, p)
        assert p.exists()

    def test_dig_list(self, growth_df, tmp_path):
        p = tmp_path / "dig.csv"
        write_dig_list_csv(growth_df, p, top_n=3)
        assert p.exists()
        dig = pd.read_csv(p)
        assert len(dig) <= 3
        assert "rank" in dig.columns

    def test_empty_skips(self, tmp_path):
        p = tmp_path / "empty.csv"
        write_matched_csv(pd.DataFrame(), p)
        assert not p.exists()


class TestAlignmentReport:
    def test_build_report(self, growth_df, summary_df):
        cp = pd.DataFrame({"distance_a": [100.0], "distance_b": [102.0], "residual_ft": [0.01]})
        segments = [{"seg_id": 0, "scale": 1.0, "shift": -2.0}]
        report = build_alignment_report(
            matched_cp=cp, residuals=cp, segments=segments,
            run_id_a="A", run_id_b="B", years_between=7.0,
            growth_df=growth_df, missing_df=pd.DataFrame(),
            new_df=pd.DataFrame(), summary_df=summary_df,
        )
        assert report["pipeline_run"]["run_a"] == "A"
        assert report["matching"]["total_matched"] == len(growth_df)
        assert len(report["top_10_severity"]) <= 10

    def test_write_json(self, tmp_path):
        report = {"test": True, "value": 42}
        p = tmp_path / "report.json"
        write_alignment_report(report, p)
        assert p.exists()
        data = json.loads(p.read_text())
        assert data["test"] is True


class TestWriteAllOutputs:
    def test_creates_all_files(self, growth_df, summary_df, tmp_path):
        cp = pd.DataFrame({"distance_a": [100.0], "distance_b": [102.0], "residual_ft": [0.01]})
        segments = [{"seg_id": 0, "scale": 1.0, "shift": -2.0}]
        write_all_outputs(
            growth_df=growth_df, missing_df=pd.DataFrame(),
            new_df=pd.DataFrame(), summary_df=summary_df,
            matched_cp=cp, residuals=cp, segments=segments,
            run_id_a="A", run_id_b="B", years_between=7.0,
            output_dir=tmp_path,
        )
        assert (tmp_path / "matched_results.csv").exists()
        assert (tmp_path / "alignment_report.json").exists()
        assert (tmp_path / "dig_list.csv").exists()

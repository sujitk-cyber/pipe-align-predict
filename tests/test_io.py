"""Tests for src/io.py — file reading, column mapping, canonical schema."""

import numpy as np
import pandas as pd
import pytest

from src.io import (
    _normalise_col_name,
    _score_mapping,
    auto_detect_mapping,
    read_file,
    build_canonical,
    validate_canonical,
    CANONICAL_COLS,
)


class TestNormaliseColName:
    def test_basic(self):
        assert _normalise_col_name("Log Dist. [ft]") == "log_dist._[ft]"

    def test_newlines(self):
        assert _normalise_col_name("Metal Loss Depth\n[%]") == "metal_loss_depth_[%]"

    def test_multi_spaces(self):
        assert _normalise_col_name("  some   col  ") == "some_col"


class TestScoreMapping:
    def test_full_match(self):
        cols = ["log_dist._[ft]", "o'clock", "event_description"]
        cfg = {"distance": ["log_dist._[ft]"], "clock": ["o'clock"], "type": ["event_description"]}
        assert _score_mapping(cols, cfg) == 3

    def test_partial_match(self):
        cols = ["log_dist._[ft]"]
        cfg = {"distance": ["log_dist._[ft]"], "clock": ["missing_col"]}
        assert _score_mapping(cols, cfg) == 1


class TestAutoDetectMapping:
    def test_2015_baker(self):
        df = pd.DataFrame(columns=[
            "J. no.", "J. len [ft]", "Wt [in]", "to u/s w. [ft]",
            "to d/s w. [ft]", "Log Dist. [ft]", "Event Description",
            "ID/OD", "Depth [%]", "Length [in]", "Width [in]", "O'clock",
        ])
        cfg_name, resolved = auto_detect_mapping(df)
        assert cfg_name == "2015_baker"
        assert "distance" in resolved


class TestReadFile:
    def test_csv(self, sample_csv):
        df = read_file(str(sample_csv))
        assert len(df) == 5
        assert "J. no." in df.columns


class TestBuildCanonical:
    def test_produces_canonical_cols(self, sample_csv):
        raw = pd.read_csv(sample_csv)
        mapping = {
            "feature_id": "J. no.",
            "distance": "Log Dist. [ft]",
            "joint_number": "J. no.",
            "clock_position_raw": "O'clock",
            "feature_type_raw": "Event Description",
            "orientation": "ID/OD",
            "depth_percent": "Depth [%]",
            "length": "Length [in]",
            "width": "Width [in]",
            "wall_thickness": "Wt [in]",
        }
        canon = build_canonical(raw, "test_run", mapping)
        for col in CANONICAL_COLS:
            assert col in canon.columns

    def test_synthetic_ids_when_no_mapping(self):
        raw = pd.DataFrame({"dist": [10, 20], "event": ["Weld", "Loss"]})
        mapping = {"distance": "dist", "feature_type_raw": "event"}
        canon = build_canonical(raw, "r1", mapping)
        assert canon["feature_id"].tolist() == ["r1_0", "r1_1"]


class TestValidateCanonical:
    def test_drops_nan_distance(self):
        df = pd.DataFrame({
            "distance": [100.0, np.nan, 300.0],
            "depth_percent": [10.0, 20.0, 30.0],
        })
        result = validate_canonical(df, "test")
        assert len(result) == 2

    def test_drops_negative_depth(self):
        df = pd.DataFrame({
            "distance": [100.0, 200.0],
            "depth_percent": [10.0, -5.0],
        })
        result = validate_canonical(df, "test")
        assert len(result) == 1

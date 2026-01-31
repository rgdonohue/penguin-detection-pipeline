#!/usr/bin/env python3
"""
Tests for confidence scoring in run_lidar_hag.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_ROOT = Path(__file__).resolve().parents[1]
for p in [str(_ROOT / "src"), str(_ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from scripts.run_lidar_hag import compute_confidence_scores


class TestConfidenceScores:
    """Test confidence scoring function."""

    def test_scores_in_range(self):
        """All scores should be in [0, 1]."""
        dets = [
            {"hag_mean": 0.35, "area_m2": 0.10, "circularity": 0.8, "solidity": 0.9},
            {"hag_mean": 0.20, "area_m2": 0.05, "circularity": 0.3, "solidity": 0.7},
            {"hag_mean": 0.55, "area_m2": 0.25, "circularity": 0.5, "solidity": 0.6},
        ]
        compute_confidence_scores(dets)
        for d in dets:
            assert "confidence" in d
            assert 0.0 <= d["confidence"] <= 1.0, f"Score {d['confidence']} out of range"

    def test_ideal_detection_high_score(self):
        """Detection at center values should have high confidence."""
        dets = [{"hag_mean": 0.35, "area_m2": 0.10, "circularity": 0.9, "solidity": 0.95}]
        compute_confidence_scores(dets)
        assert dets[0]["confidence"] > 0.7

    def test_extreme_hag_low_score(self):
        """Detection far from HAG center should have lower confidence."""
        ideal = [{"hag_mean": 0.35, "area_m2": 0.10, "circularity": 0.8, "solidity": 0.9}]
        extreme = [{"hag_mean": 0.60, "area_m2": 0.10, "circularity": 0.8, "solidity": 0.9}]
        compute_confidence_scores(ideal)
        compute_confidence_scores(extreme)
        assert ideal[0]["confidence"] > extreme[0]["confidence"]

    def test_empty_list(self):
        """Empty detection list should not crash."""
        dets = []
        compute_confidence_scores(dets)
        assert dets == []

    def test_missing_fields(self):
        """Detection with missing fields should still get a score."""
        dets = [{"hag_mean": 0.35}]
        compute_confidence_scores(dets)
        assert "confidence" in dets[0]
        assert 0.0 <= dets[0]["confidence"] <= 1.0

    def test_component_scores_present(self):
        """Individual component scores should be added to detection dict."""
        dets = [{"hag_mean": 0.35, "area_m2": 0.10, "circularity": 0.8, "solidity": 0.9}]
        compute_confidence_scores(dets)
        assert "confidence_hag" in dets[0]
        assert "confidence_area" in dets[0]
        assert "confidence_shape" in dets[0]

    def test_modifies_in_place(self):
        """Scores should be added to existing dicts, not new ones."""
        d = {"hag_mean": 0.35, "area_m2": 0.10, "circularity": 0.8, "solidity": 0.9, "id": "test:001"}
        dets = [d]
        compute_confidence_scores(dets)
        assert dets[0] is d
        assert dets[0]["id"] == "test:001"
        assert "confidence" in dets[0]

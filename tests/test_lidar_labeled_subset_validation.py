from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import validate_lidar_labeled_subset as vls  # noqa: E402


def test_match_one_to_one_prevents_double_matching():
    detections = [
        vls.XYPoint(0.0, 0.0, "d0"),
        vls.XYPoint(0.4, 0.0, "d1"),
    ]
    labels = [
        vls.XYPoint(0.05, 0.0, "l0", "Penguin in Burrow"),
        vls.XYPoint(0.35, 0.0, "l1", "Penguin in Burrow"),
    ]

    matches = vls._match_one_to_one(detections, labels, radius_m=0.5)
    assert len(matches) == 2
    matched_detection_idxs = {m[1] for m in matches}
    assert matched_detection_idxs == {0, 1}


def test_metrics_are_computed_from_matches():
    detections = [
        vls.XYPoint(0.0, 0.0, "d0"),
        vls.XYPoint(2.0, 0.0, "d1"),
        vls.XYPoint(4.0, 0.0, "d2"),
    ]
    labels = [
        vls.XYPoint(0.1, 0.0, "l0", "Penguin in Burrow"),
        vls.XYPoint(2.1, 0.0, "l1", "Penguin in Burrow"),
        vls.XYPoint(9.0, 0.0, "l2", "Penguin in Burrow"),
    ]

    matches = vls._match_one_to_one(detections, labels, radius_m=0.25)
    metrics = vls._metrics_from_matches(
        detections=detections,
        labels=labels,
        matches=matches,
        radius_m=0.25,
    )
    assert metrics["tp"] == 2
    assert metrics["fp"] == 1
    assert metrics["fn"] == 1
    assert metrics["precision"] == pytest.approx(2 / 3)
    assert metrics["recall"] == pytest.approx(2 / 3)
    assert metrics["f1"] == pytest.approx(2 / 3)


def test_penguin_filter_excludes_non_penguin_labels():
    labels = [
        vls.XYPoint(0.0, 0.0, "a", "Penguin in Burrow"),
        vls.XYPoint(1.0, 1.0, "b", "Empty Burrow"),
        vls.XYPoint(2.0, 2.0, "c", ""),
    ]
    filtered = vls._filter_penguin_labels(labels, include_non_penguin=False)
    assert [pt.point_id for pt in filtered] == ["a"]


def test_metrics_summary_table_has_expected_columns():
    rows = [
        {
            "radius_m": 1.0,
            "tp": 2,
            "fp": 1,
            "fn": 3,
            "precision": 0.66,
            "recall": 0.4,
            "f1": 0.5,
        }
    ]
    table = vls._metrics_summary_table(rows)
    assert table == [
        {
            "radius_m": 1.0,
            "tp": 2,
            "fp": 1,
            "fn": 3,
            "precision": 0.66,
            "recall": 0.4,
            "f1": 0.5,
        }
    ]


def test_radius_sensitivity_note_reports_f1_range():
    rows = [
        {"radius_m": 1.0, "f1": 0.40},
        {"radius_m": 2.0, "f1": 0.65},
        {"radius_m": 3.0, "f1": 0.50},
    ]
    note = vls._radius_sensitivity_note(rows)
    assert "F1 ranges from 0.400 to 0.650" in note

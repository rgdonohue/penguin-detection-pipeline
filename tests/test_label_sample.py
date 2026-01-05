from pipelines.label_sample import select_label_sample


def test_select_label_sample_is_deterministic() -> None:
    dets = [
        {"id": "a", "x": 0.0, "y": 0.0, "hag_max": 0.1, "area_m2": 0.05},
        {"id": "b", "x": 1.0, "y": 1.0, "hag_max": 0.2, "area_m2": 0.06},
        {"id": "c", "x": 2.0, "y": 2.0, "hag_max": 0.3, "area_m2": 0.07},
        {"id": "d", "x": 3.0, "y": 3.0, "hag_max": 0.4, "area_m2": 0.08},
        {"id": "e", "x": 4.0, "y": 4.0, "hag_max": 0.5, "area_m2": 0.09},
        {"id": "f", "x": 5.0, "y": 5.0, "hag_max": 0.6, "area_m2": 0.10},
        {"id": "g", "x": 6.0, "y": 6.0, "hag_max": 0.7, "area_m2": 0.11},
        {"id": "h", "x": 7.0, "y": 7.0, "hag_max": 0.8, "area_m2": 0.12},
    ]

    s1 = select_label_sample(dets, n_total=5, seed="123")
    s2 = select_label_sample(dets, n_total=5, seed="123")
    assert [d["id"] for d in s1] == [d["id"] for d in s2]


def test_select_label_sample_respects_n_total() -> None:
    dets = [{"id": f"d{i}", "x": float(i), "y": float(i), "hag_max": float(i), "area_m2": 1.0} for i in range(50)]
    s = select_label_sample(dets, n_total=12, seed="0")
    assert len(s) == 12


def test_select_label_sample_backfills_sparse_strata() -> None:
    # Force a situation where some strata are tiny by creating an extreme outlier.
    dets = []
    for i in range(30):
        dets.append({"id": f"n{i}", "x": float(i), "y": float(i), "hag_max": 1.0, "area_m2": 1.0})
    dets.append({"id": "outlier", "x": 999.0, "y": 999.0, "hag_max": 999.0, "area_m2": 999.0})

    s = select_label_sample(dets, n_total=20, seed="0")
    assert len(s) == 20
    assert all(d.get("stratum") for d in s)



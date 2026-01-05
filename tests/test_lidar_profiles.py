from pipelines.lidar_profiles import OFFICIAL_DETERMINISTIC, as_policy_dict


def test_official_profile_is_deterministic() -> None:
    assert OFFICIAL_DETERMINISTIC.top_method == "max"


def test_policy_dict_shape() -> None:
    p = as_policy_dict()
    assert "lidar" in p
    assert p["lidar"]["official_top_method"] == "max"
    assert p["lidar"]["p95_is_experimental"] is True



import sys

from pipelines.golden import GoldenParams, run


def test_golden_harness_invokes_pytest(monkeypatch, tmp_path):
    calls = []

    def fake_run(cmd, check):
        calls.append((cmd, check))

    monkeypatch.setattr("pipelines.golden.subprocess.run", fake_run, raising=True)
    run(GoldenParams(intake_root=tmp_path, processed_root=tmp_path, qc_root=tmp_path))

    assert calls
    cmd, check = calls[0]
    assert check is True
    assert cmd[:3] == [sys.executable, "-m", "pytest"]

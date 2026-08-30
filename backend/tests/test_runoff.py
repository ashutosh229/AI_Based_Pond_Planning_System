import pytest
from app.core.runoff import RunoffCalculator


def test_annual_runoff_matches_worked_example():
    volume = RunoffCalculator.annual_runoff_volume_m3(50_000, 1.2, 0.3)
    assert volume == pytest.approx(18_000.0)


def test_compute_end_to_end():
    result = RunoffCalculator.compute(50_000, 1.2, 0.3, 0.2)
    assert result.annual_runoff_volume_m3 == pytest.approx(18_000.0)
    assert result.design_storage_volume_m3 == pytest.approx(3_600.0)


def test_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        RunoffCalculator.annual_runoff_volume_m3(0, 1.2, 0.3)
    with pytest.raises(ValueError):
        RunoffCalculator.annual_runoff_volume_m3(50_000, 1.2, 1.5)

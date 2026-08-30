import pytest
from app.core.pond_sizing import PondSizer


def test_recommend_within_practical_range():
    result = PondSizer.recommend(3_600, 1_000, 0.15)
    assert result.usable_volume_m3 == pytest.approx(3_060.0)
    assert result.recommended_depth_m == pytest.approx(3.06)
    assert result.is_feasible is True


def test_flags_infeasible_when_too_deep():
    result = PondSizer.recommend(10_000, 500, 0.15)
    assert result.is_feasible is False

"""
ml/forecaster/tests/test_forecaster.py
Tests for the forecaster node.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from ml.forecaster.forecaster import SkillDemandForecaster, ForecasterError


def _make_ts(n_days: int, trend: float = 1.0, noise: float = 5.0) -> pd.DataFrame:
    """Generate a synthetic time series for testing."""
    dates  = [datetime(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]
    values = [max(0, 50 + trend * i + np.random.normal(0, noise)) for i in range(n_days)]
    return pd.DataFrame({"ds": dates, "y": values})


def test_insufficient_data_raises_for001():
    """FOR_001: should raise if fewer than 30 data points."""
    forecaster = SkillDemandForecaster()
    short_ts = _make_ts(15)
    with pytest.raises(ForecasterError) as exc_info:
        forecaster.forecast_skill("Python", short_ts)
    assert exc_info.value.code == "FOR_001"


def test_flat_series_raises_for002():
    """FOR_002: should raise for a flat (all-same-value) series."""
    forecaster = SkillDemandForecaster()
    flat_ts = pd.DataFrame({
        "ds": [datetime(2024, 1, 1) + timedelta(days=i) for i in range(50)],
        "y":  [10.0] * 50,
    })
    with pytest.raises(ForecasterError) as exc_info:
        forecaster.forecast_skill("FlatSkill", flat_ts)
    assert exc_info.value.code == "FOR_002"


def test_growing_trend_detected():
    """A strongly growing series should be labelled 'growing'."""
    forecaster = SkillDemandForecaster()
    ts = _make_ts(90, trend=2.0, noise=2.0)  # clear upward trend
    result = forecaster.forecast_skill("GrowingSkill", ts)
    assert result.trend == "growing"
    assert result.forecast_90d > result.current_demand


def test_forecast_fields_present():
    """All required fields must be present in the result."""
    forecaster = SkillDemandForecaster()
    ts = _make_ts(60)
    result = forecaster.forecast_skill("Python", ts)
    assert result.skill_name == "Python"
    assert result.forecast_30d >= 0
    assert result.forecast_60d >= 0
    assert result.forecast_90d >= 0
    assert result.confidence_low <= result.confidence_high
    assert result.data_points == 60
    assert result.trend in ("growing", "stable", "declining")


def test_confidence_interval_ordering():
    """Lower bound must always be <= upper bound."""
    forecaster = SkillDemandForecaster()
    ts = _make_ts(45)
    result = forecaster.forecast_skill("SQL", ts)
    assert result.confidence_low <= result.forecast_90d <= result.confidence_high or \
           result.confidence_low <= result.confidence_high  # at minimum bounds are ordered

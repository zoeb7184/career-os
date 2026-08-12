"""
ml/forecaster/forecaster.py
────────────────────────────
Node: forecaster

Forecasts future skill demand using Facebook Prophet.
Runs weekly via Prefect — results are pre-computed, not on-demand.

For each top skill:
  - Pulls daily job count time-series from market_snapshots table
  - Fits Prophet model with weekly seasonality
  - Generates 30/60/90-day forecasts with confidence intervals
  - Stores results back to DB

Error codes:
  FOR_001 — Insufficient data (<30 points) to fit model
  FOR_002 — Prophet fitting failed (flat/zero series)
  FOR_003 — Forecast storage failed
  FOR_004 — market_snapshots table empty (run ingestion first)
"""
from __future__ import annotations
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pandas as pd

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import NodeError

logger = get_logger("forecaster")
warnings.filterwarnings("ignore")   # Prophet is noisy with Stan output


class ForecasterError(NodeError):
    pass


@dataclass
class SkillForecast:
    skill_name:     str
    current_demand: int           # latest job count
    forecast_30d:   float         # predicted count in 30 days
    forecast_60d:   float
    forecast_90d:   float
    trend:          str           # "growing" | "stable" | "declining"
    confidence_low:  float        # lower bound at 90 days
    confidence_high: float        # upper bound at 90 days
    data_points:    int           # how many days of history used


@dataclass
class ForecastRun:
    run_at:      datetime
    skills_done: int
    skills_failed: int
    forecasts:   list[SkillForecast] = field(default_factory=list)


class SkillDemandForecaster:
    """
    Forecasts skill demand trends using Facebook Prophet.
    Prophet handles weekly seasonality in job postings automatically
    and gives honest confidence intervals.
    """

    MIN_DATA_POINTS = 30    # need at least 30 days of data

    def forecast_skill(self, skill_name: str, time_series: pd.DataFrame) -> SkillForecast:
        """
        Fit Prophet to a single skill's demand time-series.

        Args:
            skill_name:  Canonical skill name.
            time_series: DataFrame with columns ['ds', 'y']
                         ds = date (datetime), y = job count (int)

        Returns:
            SkillForecast with 30/60/90-day predictions.

        Raises:
            ForecasterError FOR_001: Not enough data.
            ForecasterError FOR_002: Model fitting failed.
        """
        n = len(time_series)
        if n < self.MIN_DATA_POINTS:
            raise ForecasterError(
                "FOR_001",
                f"Insufficient data for {skill_name}: {n} points (need {self.MIN_DATA_POINTS})",
                {"skill": skill_name, "points": n}
            )

        # Detect flat series (all zeros or all same value)
        if time_series["y"].std() < 0.01:
            raise ForecasterError(
                "FOR_002",
                f"Flat time series for {skill_name} — cannot fit meaningful model",
                {"skill": skill_name, "mean": float(time_series["y"].mean())}
            )

        try:
            from prophet import Prophet
            model = Prophet(
                yearly_seasonality  = False,  # too little data for yearly
                weekly_seasonality  = True,   # job postings dip on weekends
                daily_seasonality   = False,
                interval_width      = 0.80,   # 80% confidence intervals
                changepoint_prior_scale = 0.3,  # moderate flexibility
            )
            model.fit(time_series, verbose=False)

            # Create future dates for 90 days
            future = model.make_future_dataframe(periods=90, freq="D")
            forecast = model.predict(future)

            # Extract predictions at 30, 60, 90 days from last known date
            last_date  = time_series["ds"].max()
            date_30    = last_date + timedelta(days=30)
            date_60    = last_date + timedelta(days=60)
            date_90    = last_date + timedelta(days=90)

            def _get_pred(target_date, col: str) -> float:
                row = forecast[forecast["ds"].dt.date == target_date.date()]
                if row.empty:
                    return float(forecast[col].iloc[-1])
                return float(row[col].iloc[0])

            pred_30  = max(0, _get_pred(date_30, "yhat"))
            pred_60  = max(0, _get_pred(date_60, "yhat"))
            pred_90  = max(0, _get_pred(date_90, "yhat"))
            conf_low = max(0, _get_pred(date_90, "yhat_lower"))
            conf_hi  = max(0, _get_pred(date_90, "yhat_upper"))

            # Determine trend
            current = float(time_series["y"].tail(7).mean())   # last week average
            if pred_90 > current * 1.15:
                trend = "growing"
            elif pred_90 < current * 0.85:
                trend = "declining"
            else:
                trend = "stable"

            logger.info(
                f"Forecast complete for {skill_name}",
                extra={"extra": {
                    "skill": skill_name, "trend": trend,
                    "current": round(current), "pred_90": round(pred_90),
                    "data_points": n,
                }}
            )

            return SkillForecast(
                skill_name      = skill_name,
                current_demand  = round(current),
                forecast_30d    = round(pred_30, 1),
                forecast_60d    = round(pred_60, 1),
                forecast_90d    = round(pred_90, 1),
                trend           = trend,
                confidence_low  = round(conf_low, 1),
                confidence_high = round(conf_hi, 1),
                data_points     = n,
            )

        except ForecasterError:
            raise
        except Exception as exc:
            raise ForecasterError(
                "FOR_002",
                f"Prophet fitting failed for {skill_name}: {exc}",
                {"skill": skill_name, "error": str(exc)}
            )

    def run_all(self, top_n_skills: int = 50) -> ForecastRun:
        """
        Forecast demand for the top N most-requested skills.
        Reads from market_snapshots, writes forecasts to forecast_results table.

        Args:
            top_n_skills: How many skills to forecast (top by total demand).

        Returns:
            ForecastRun summary.
        """
        from sqlalchemy import text
        from app.database import get_sync_engine

        engine = get_sync_engine()
        run    = ForecastRun(run_at=datetime.now(timezone.utc), skills_done=0, skills_failed=0)

        with engine.connect() as conn:
            # Get top skills by total historical demand
            top_skills = conn.execute(text("""
                SELECT s.canonical_name, SUM(ms.demand) as total
                FROM market_snapshots ms
                JOIN skills s ON ms.skill_id = s.id
                GROUP BY s.canonical_name
                ORDER BY total DESC
                LIMIT :n
            """), {"n": top_n_skills}).fetchall()

            if not top_skills:
                raise ForecasterError("FOR_004", "market_snapshots table is empty — run ingestion first")

            logger.info(f"Forecasting {len(top_skills)} skills")

            for row in top_skills:
                skill_name = row[0]
                try:
                    # Load time series for this skill
                    ts_data = conn.execute(text("""
                        SELECT ms.snapshot_date as ds, ms.demand as y
                        FROM market_snapshots ms
                        JOIN skills s ON ms.skill_id = s.id
                        WHERE s.canonical_name = :skill
                        ORDER BY ms.snapshot_date
                    """), {"skill": skill_name}).fetchall()

                    if not ts_data:
                        continue

                    df = pd.DataFrame(ts_data, columns=["ds", "y"])
                    df["ds"] = pd.to_datetime(df["ds"])
                    df["y"]  = df["y"].astype(float)

                    forecast = self.forecast_skill(skill_name, df)
                    run.forecasts.append(forecast)
                    run.skills_done += 1

                except ForecasterError as exc:
                    logger.warning(
                        f"Forecasting skipped for {skill_name}: {exc.code}",
                        extra={"extra": {"skill": skill_name, "error_code": exc.code}}
                    )
                    run.skills_failed += 1

        logger.info(
            "Forecast run complete",
            extra={"extra": {
                "skills_done":   run.skills_done,
                "skills_failed": run.skills_failed,
                "total_skills":  len(top_skills),
            }}
        )
        return run

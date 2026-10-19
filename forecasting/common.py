"""Shared data loading, feature construction, splits and metrics for the
7-day emergency department (ED) attendance forecasting experiment.

Forecast setup
--------------
At a forecast origin day t we know every value up to and including t and
predict the daily ED attendances of days t+1 ... t+7 (horizon h = 1..7).

Every feature for a row (hospital, t, h) only uses data observed on or
before t. Targets and lag features are expressed relative to the
hospital's 28-day mean level ending at t, so hospitals of very different
size (AH ~67/day vs CGH ~380/day) share one model, and slow trends
(e.g. Woodlands Health ramping up after opening) are absorbed by the level.
"""

from __future__ import annotations

from pathlib import Path

import holidays
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_CSV = ROOT / "data" / "hospital_metrics.csv"
RESULTS = Path(__file__).resolve().parent / "results"
FIGURES = Path(__file__).resolve().parent / "figures"

HORIZONS = range(1, 8)
LEVEL_WINDOW = 28
SEED = 42

# Training targets end here; test origins start here so that every
# training target is already observed at every test forecast origin.
TRAIN_END = pd.Timestamp("2025-12-31")
TEST_ORIGIN_START = TRAIN_END

# Expanding-window validation folds used for tuning (target periods inside training).
CV_FOLDS = [
    (pd.Timestamp("2025-07-01"), pd.Timestamp("2025-08-31")),
    (pd.Timestamp("2025-09-01"), pd.Timestamp("2025-10-31")),
    (pd.Timestamp("2025-11-01"), pd.Timestamp("2025-12-31")),
]


def load_wide() -> pd.DataFrame:
    """Daily ED attendances, one column per hospital, on a complete calendar."""
    d = pd.read_csv(DATA_CSV, parse_dates=["date"])
    wide = d.pivot(index="date", columns="hospital_code", values="ed_attendances")
    full = pd.date_range(wide.index.min(), wide.index.max(), freq="D")
    return wide.reindex(full).astype(float)


def sg_holidays(dates: pd.DatetimeIndex) -> pd.Series:
    years = sorted(set(dates.year) | {dates.year.max() + 1})
    hol = holidays.Singapore(years=years)
    return pd.Series([d.date() in hol for d in dates], index=dates)


def calendar_frame(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Calendar facts about a day itself (known in advance, so no leakage)."""
    pad = pd.date_range(dates.min() - pd.Timedelta(days=1), dates.max() + pd.Timedelta(days=1))
    hol = sg_holidays(pad)
    cal = pd.DataFrame(index=dates)
    cal["dow"] = dates.dayofweek
    cal["is_holiday"] = hol.reindex(dates).to_numpy().astype(int)
    cal["after_holiday"] = hol.shift(1).reindex(dates).fillna(False).to_numpy().astype(int)
    cal["before_holiday"] = hol.shift(-1).reindex(dates).fillna(False).to_numpy().astype(int)
    doy = dates.dayofyear.to_numpy()
    cal["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
    cal["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)
    return cal


def build_rows(wide: pd.DataFrame) -> pd.DataFrame:
    """One row per (hospital, origin t, horizon h) with tabular features.

    Columns ending in `_r` are ratios to `level` (28-day mean ending at t).
    NaN features (e.g. the week of 2026-08-02 missing for every hospital)
    are left as NaN here; each model decides how to handle them.
    """
    cal = calendar_frame(wide.index)
    frames = []
    for hosp in wide.columns:
        y = wide[hosp]
        level = y.rolling(LEVEL_WINDOW, min_periods=21).mean()
        last7 = y.rolling(7, min_periods=5).mean()
        for h in HORIZONS:
            f = pd.DataFrame(index=wide.index)  # index = origin t
            f["hospital"] = hosp
            f["origin"] = wide.index
            f["h"] = h
            f["target_date"] = wide.index + pd.Timedelta(days=h)
            f["level"] = level
            f["y"] = y.shift(-h)  # value on day t+h
            # Same weekday as the target day, 1..4 weeks before it: y[t+h-7k], all <= t.
            for k in range(1, 5):
                f[f"same_dow_{k}w_r"] = y.shift(7 * k - h) / level
            f["last_day_r"] = y / level
            f["prev_day_r"] = y.shift(1) / level
            f["last7_r"] = last7 / level
            tc = cal.reindex(f["target_date"])
            for col in ["is_holiday", "after_holiday", "before_holiday", "doy_sin", "doy_cos"]:
                f[col] = tc[col].to_numpy()
            f["dow"] = tc["dow"].to_numpy()
            frames.append(f)
    rows = pd.concat(frames, ignore_index=True)
    rows["target_r"] = rows["y"] / rows["level"]
    rows = rows[rows["level"].notna() & rows["target_date"].le(wide.index.max())]
    return rows.reset_index(drop=True)


DOW_COLS = [f"dow_{i}" for i in range(7)]


def tabular_matrix(rows: pd.DataFrame, hospitals: list[str]) -> pd.DataFrame:
    """Numeric design matrix: ratio features, calendar, horizon, one-hot weekday/hospital."""
    X = rows[[
        "h", "same_dow_1w_r", "same_dow_2w_r", "same_dow_3w_r", "same_dow_4w_r",
        "last_day_r", "prev_day_r", "last7_r",
        "is_holiday", "after_holiday", "before_holiday", "doy_sin", "doy_cos",
    ]].copy()
    for i in range(7):
        X[f"dow_{i}"] = (rows["dow"] == i).astype(int)
    for hosp in hospitals:
        X[f"hosp_{hosp}"] = (rows["hospital"] == hosp).astype(int)
    return X


def split_masks(rows: pd.DataFrame, fit_end: pd.Timestamp, eval_start: pd.Timestamp,
                eval_end: pd.Timestamp | None = None):
    """Training rows: target observed by fit_end. Evaluation rows: origin >= fit_end
    and target in [eval_start, eval_end]. Rows with a missing target are dropped."""
    has_y = rows["y"].notna()
    train = has_y & rows["target_date"].le(fit_end)
    ev = has_y & rows["origin"].ge(fit_end) & rows["target_date"].ge(eval_start)
    if eval_end is not None:
        ev &= rows["target_date"].le(eval_end)
    return train, ev


def test_masks(rows: pd.DataFrame):
    return split_masks(rows, TRAIN_END, TRAIN_END + pd.Timedelta(days=1))


def cv_masks(rows: pd.DataFrame):
    for start, end in CV_FOLDS:
        yield split_masks(rows, start - pd.Timedelta(days=1), start, end)


def metrics(y_true, y_pred) -> dict:
    y_true = np.asarray(y_true, float)
    y_pred = np.asarray(y_pred, float)
    err = y_pred - y_true
    return {
        "MAE": float(np.mean(np.abs(err))),
        "RMSE": float(np.sqrt(np.mean(err ** 2))),
        "MAPE_%": float(np.mean(np.abs(err) / y_true) * 100),
        "n": int(len(y_true)),
    }


def save_predictions(name: str, rows: pd.DataFrame, pred_counts) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = rows[["hospital", "origin", "h", "target_date", "y"]].copy()
    out["pred"] = np.asarray(pred_counts, float)
    out["model"] = name
    path = RESULTS / f"pred_{name}.csv"
    out.to_csv(path, index=False)
    return path

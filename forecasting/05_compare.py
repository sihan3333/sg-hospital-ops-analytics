"""Step 5 - compare all models on the identical 2026 test rows.

* overall MAE / RMSE / MAPE, by horizon and by hospital
* paired block bootstrap of MAE differences (resampling whole forecast-origin
  weeks, because errors on neighbouring days are correlated)
* forecast-vs-actual plot for one hospital
"""

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from common import FIGURES, RESULTS, SEED, metrics

sns.set_theme(style="whitegrid")
MODELS = ["seasonal_naive", "seasonal_mean4", "ridge", "random_forest", "xgboost", "lstm"]
LABELS = {"seasonal_naive": "Seasonal naive", "seasonal_mean4": "4-week weekday mean", "ridge": "Ridge",
          "random_forest": "Random forest", "xgboost": "XGBoost", "lstm": "LSTM"}

pred = pd.concat([pd.read_csv(RESULTS / f"pred_{m}.csv", parse_dates=["origin", "target_date"]) for m in MODELS])
wide = pred.pivot_table(index=["hospital", "origin", "h"], columns="model", values="pred")
truth = pred.drop_duplicates(["hospital", "origin", "h"]).set_index(["hospital", "origin", "h"])["y"]
assert wide.notna().all().all(), "every model must predict every test row"
wide["y"] = truth

overall = {m: metrics(wide["y"], wide[m]) for m in MODELS}
by_h = pd.DataFrame({m: wide.groupby(level="h").apply(lambda g: np.mean(np.abs(g[m] - g["y"]))) for m in MODELS})
by_hosp = pd.DataFrame({m: wide.groupby(level="hospital").apply(lambda g: np.mean(np.abs(g[m] - g["y"]))) for m in MODELS})
by_hosp_mape = pd.DataFrame({m: wide.groupby(level="hospital").apply(lambda g: np.mean(np.abs(g[m] - g["y"]) / g["y"]) * 100) for m in MODELS})

# --- Paired block bootstrap over forecast-origin weeks ---
rng = np.random.default_rng(SEED)
origin = wide.index.get_level_values("origin")
week = ((origin - origin.min()).days // 7).to_numpy()
abs_err = {m: np.abs(wide[m] - wide["y"]).to_numpy() for m in MODELS}
weeks = np.unique(week)
groups = [np.where(week == w)[0] for w in weeks]


def boot_diff(a, b, n=2000):
    d = abs_err[a] - abs_err[b]
    sums = np.array([d[g].sum() for g in groups])
    counts = np.array([len(g) for g in groups])
    draws = rng.integers(0, len(groups), size=(n, len(groups)))
    stats = sums[draws].sum(axis=1) / counts[draws].sum(axis=1)
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return {"mae_diff": float(d.mean()), "ci95": [float(lo), float(hi)]}


comparisons = {f"{a} - {b}": boot_diff(a, b) for a, b in [
    ("xgboost", "seasonal_mean4"), ("lstm", "seasonal_mean4"), ("lstm", "xgboost"),
    ("xgboost", "ridge"), ("random_forest", "xgboost"), ("seasonal_mean4", "seasonal_naive"),
]}

# --- Figures ---
fig, ax = plt.subplots(figsize=(8, 4.5))
for m in MODELS:
    ax.plot(by_h.index, by_h[m], marker="o", label=LABELS[m])
ax.set(title="Test MAE by forecast horizon (2026)", xlabel="Days ahead (h)", ylabel="MAE (attendances/day)")
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(FIGURES / "06_mae_by_horizon.png", dpi=150)
plt.close(fig)

h1 = pred[(pred["hospital"] == "CGH") & (pred["h"] == 1)].pivot(index="target_date", columns="model", values="pred")
actual = pred[(pred["hospital"] == "CGH") & (pred["h"] == 1)].drop_duplicates("target_date").set_index("target_date")["y"]
fig, ax = plt.subplots(figsize=(11, 4.5))
window = pd.date_range("2026-04-01", "2026-06-09")
h1, actual = h1.reindex(window), actual.reindex(window)
ax.plot(actual.index, actual, color="black", linewidth=1.2, label="Actual")
for m, c in [("seasonal_mean4", "#999999"), ("xgboost", "#dd8452"), ("lstm", "#4c72b0")]:
    ax.plot(h1.index, h1[m], linewidth=1, label=LABELS[m], color=c)
ax.set(title="CGH: next-day forecasts vs actual, 1 Apr - 9 Jun 2026 (test period)", xlabel="", ylabel="Attendances")
ax.legend(fontsize=8, ncol=4)
fig.tight_layout()
fig.savefig(FIGURES / "07_cgh_forecast_vs_actual.png", dpi=150)
plt.close(fig)

report = {"overall": overall, "mae_by_horizon": by_h.round(2).to_dict(), "mae_by_hospital": by_hosp.round(2).to_dict(),
          "mape_by_hospital": by_hosp_mape.round(2).to_dict(), "bootstrap_mae_differences": comparisons,
          "n_test_rows": int(len(wide)), "n_origin_weeks": int(len(weeks))}
(RESULTS / "metrics_05_comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

table = pd.DataFrame(overall).T[["MAE", "RMSE", "MAPE_%"]].round(2)
table.index = [LABELS[m] for m in table.index]
(RESULTS / "summary_table.md").write_text(table.to_markdown(), encoding="utf-8")
print(table.to_string())
print("\nMAE by hospital:\n", by_hosp.round(1).to_string())
print("\nMAE by horizon:\n", by_h.round(2).to_string())
print("\nBootstrap MAE differences (negative = first model better):")
for k, v in comparisons.items():
    print(f"  {k:32s} {v['mae_diff']:+.2f}  95% CI [{v['ci95'][0]:+.2f}, {v['ci95'][1]:+.2f}]")

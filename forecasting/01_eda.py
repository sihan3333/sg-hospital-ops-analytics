"""Step 1 - exploratory data analysis of daily ED attendances.

Outputs figures to forecasting/figures and a JSON summary to forecasting/results.
"""

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from statsmodels.tsa.stattools import acf

from common import FIGURES, RESULTS, calendar_frame, load_wide

sns.set_theme(style="whitegrid")
FIGURES.mkdir(parents=True, exist_ok=True)
RESULTS.mkdir(parents=True, exist_ok=True)

wide = load_wide()
summary = {
    "date_range": [str(wide.index.min().date()), str(wide.index.max().date())],
    "n_days": len(wide),
    "missing_days_per_hospital": wide.isna().sum().astype(int).to_dict(),
    "first_valid_date": {h: str(wide[h].first_valid_index().date()) for h in wide},
    "mean_per_day": wide.mean().round(1).to_dict(),
}

# 1. Weekly-averaged series: level differences, trend and the WH / KTPH shift.
fig, ax = plt.subplots(figsize=(11, 5))
wide.resample("W").mean().plot(ax=ax, linewidth=1.2)
ax.axvline(pd.Timestamp("2024-06-23"), color="grey", linestyle="--", linewidth=1)
ax.text(pd.Timestamp("2024-07-01"), ax.get_ylim()[1] * 0.97, "WH ED opens", fontsize=9, color="grey", va="top")
ax.set(title="Weekly mean daily ED attendances by hospital", xlabel="", ylabel="Attendances per day")
ax.legend(ncol=9, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False)
fig.tight_layout()
fig.savefig(FIGURES / "01_weekly_series.png", dpi=150)
plt.close(fig)

# 2. Day-of-week pattern relative to each hospital's own mean.
cal = calendar_frame(wide.index)
rel = wide / wide.mean()
rel["dow"] = cal["dow"]
rel_long = rel.melt(id_vars="dow", var_name="hospital", value_name="ratio").dropna()
fig, ax = plt.subplots(figsize=(8, 4.5))
sns.boxplot(data=rel_long, x="dow", y="ratio", ax=ax, color="#8fb8de", fliersize=1.5)
ax.set_xticks(range(7), ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
ax.set(title="Daily attendances relative to hospital mean, by weekday", xlabel="", ylabel="Ratio to hospital mean")
fig.tight_layout()
fig.savefig(FIGURES / "02_weekday_pattern.png", dpi=150)
plt.close(fig)
summary["weekday_ratio_median"] = rel_long.groupby("dow")["ratio"].median().round(3).to_dict()

# 3. Public holidays and the day after.
rel["is_holiday"] = cal["is_holiday"]
rel["after_holiday"] = cal["after_holiday"]
hosp_cols = [c for c in wide.columns]
day_type = pd.Series("normal", index=rel.index)
day_type[rel["after_holiday"] == 1] = "day after holiday"
day_type[rel["is_holiday"] == 1] = "holiday"
summary["holiday_effect_mean_ratio"] = (
    rel[hosp_cols].mean(axis=1).groupby(day_type).mean().round(3).to_dict()
)

# 4. Autocorrelation: how strongly today relates to 1..28 days ago (CGH as example).
cgh = wide["CGH"].interpolate(limit_area="inside").dropna()
ac = acf(cgh, nlags=28)
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(range(len(ac)), ac, color="#4c72b0")
ax.set(title="Autocorrelation of CGH daily attendances", xlabel="Lag (days)", ylabel="ACF")
fig.tight_layout()
fig.savefig(FIGURES / "03_acf_cgh.png", dpi=150)
plt.close(fig)
summary["acf_cgh"] = {f"lag{k}": round(float(ac[k]), 3) for k in (1, 6, 7, 14, 21, 28)}

# 5. Quarterly means: shows the KTPH drop after WH opened.
summary["quarterly_mean"] = {
    str(k.date()): v for k, v in wide.resample("QE").mean().round(1).T.to_dict().items()
}

(RESULTS / "eda_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({k: summary[k] for k in ["weekday_ratio_median", "holiday_effect_mean_ratio", "acf_cgh"]}, indent=2))

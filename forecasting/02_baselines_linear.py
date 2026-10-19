"""Step 2 - baselines and a regularised linear regression.

Baselines need no training:
  * seasonal_naive : same weekday last week, y[d-7]
  * seasonal_mean4 : mean of the same weekday over the last 4 weeks
Ridge regression predicts the ratio target from the tabular features;
its penalty alpha is chosen by expanding-window time-series CV.
"""

import json

import numpy as np
from sklearn.linear_model import Ridge

from common import RESULTS, build_rows, cv_masks, load_wide, metrics, save_predictions, tabular_matrix, test_masks

wide = load_wide()
rows = build_rows(wide)
hospitals = list(wide.columns)
X = tabular_matrix(rows, hospitals).fillna(1.0)  # missing ratio -> "at the usual level"
y_r = rows["target_r"]
train, test = test_masks(rows)
te = rows[test]
report = {}

# --- Baselines (computed in counts; fall back to the 28-day level if a lag is missing) ---
naive = (rows["same_dow_1w_r"] * rows["level"]).fillna(rows["level"])
mean4 = (rows[[f"same_dow_{k}w_r" for k in range(1, 5)]].mean(axis=1) * rows["level"]).fillna(rows["level"])
for name, pred in [("seasonal_naive", naive), ("seasonal_mean4", mean4)]:
    save_predictions(name, te, pred[test])
    report[name] = metrics(te["y"], pred[test])

# --- Ridge: choose alpha by time-series CV on the training period ---
alphas = [0.01, 0.1, 1, 10, 100]
cv_mae = {}
for a in alphas:
    fold_mae = []
    for tr, va in cv_masks(rows):
        m = Ridge(alpha=a).fit(X[tr], y_r[tr])
        pred = m.predict(X[va]) * rows.loc[va, "level"]
        fold_mae.append(metrics(rows.loc[va, "y"], pred)["MAE"])
    cv_mae[a] = float(np.mean(fold_mae))
best = min(cv_mae, key=cv_mae.get)
model = Ridge(alpha=best).fit(X[train], y_r[train])
pred = model.predict(X[test]) * te["level"]
save_predictions("ridge", te, pred)
report["ridge"] = metrics(te["y"], pred) | {"alpha": best, "cv_mae_by_alpha": cv_mae}

(RESULTS / "metrics_02_baselines_linear.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
for k, v in report.items():
    print(f"{k:16s} MAE {v['MAE']:.2f}  RMSE {v['RMSE']:.2f}  MAPE {v['MAPE_%']:.2f}%  n={v['n']}")
print("ridge CV MAE by alpha:", {a: round(m, 2) for a, m in cv_mae.items()})

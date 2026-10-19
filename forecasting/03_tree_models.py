"""Step 3 - random forest and XGBoost on the same tabular features as ridge.

Hyper-parameters are chosen by the same expanding-window time-series CV,
then each model is refit on the full training period and evaluated once
on the 2026 test origins. SHAP values explain the XGBoost test predictions.
"""

import itertools
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shap
from sklearn.ensemble import RandomForestRegressor
from xgboost import XGBRegressor

from common import (FIGURES, RESULTS, SEED, build_rows, cv_masks, load_wide, metrics,
                    save_predictions, tabular_matrix, test_masks)

wide = load_wide()
rows = build_rows(wide)
hospitals = list(wide.columns)
X = tabular_matrix(rows, hospitals).fillna(1.0)
y_r = rows["target_r"]
train, test = test_masks(rows)
te = rows[test]


def tune(make_model, grid):
    results = []
    for params in grid:
        fold_mae = []
        for tr, va in cv_masks(rows):
            m = make_model(**params).fit(X[tr], y_r[tr])
            pred = m.predict(X[va]) * rows.loc[va, "level"]
            fold_mae.append(metrics(rows.loc[va, "y"], pred)["MAE"])
        results.append({"params": params, "cv_mae": float(np.mean(fold_mae))})
        print(f"  {params} -> CV MAE {np.mean(fold_mae):.2f}")
    best = min(results, key=lambda r: r["cv_mae"])
    return best, results


def grid(**space):
    keys = list(space)
    return [dict(zip(keys, vals)) for vals in itertools.product(*space.values())]


report = {}

print("Random forest")
rf_make = lambda **p: RandomForestRegressor(n_estimators=300, random_state=SEED, n_jobs=-1, **p)
rf_best, rf_all = tune(rf_make, grid(max_depth=[8, None], min_samples_leaf=[5, 20], max_features=[0.5, 1.0]))
rf = rf_make(**rf_best["params"]).fit(X[train], y_r[train])
pred = rf.predict(X[test]) * te["level"]
save_predictions("random_forest", te, pred)
report["random_forest"] = metrics(te["y"], pred) | {"best": rf_best, "search": rf_all}

print("XGBoost")
xgb_make = lambda **p: XGBRegressor(subsample=0.8, colsample_bytree=0.8, random_state=SEED, n_jobs=4, **p)
xgb_best, xgb_all = tune(xgb_make, grid(max_depth=[3, 5], learning_rate=[0.03, 0.1], n_estimators=[300, 800]))
xgb = xgb_make(**xgb_best["params"]).fit(X[train], y_r[train])
pred = xgb.predict(X[test]) * te["level"]
save_predictions("xgboost", te, pred)
report["xgboost"] = metrics(te["y"], pred) | {"best": xgb_best, "search": xgb_all}

# SHAP: which features push the predicted ratio up or down (association, not causation).
explainer = shap.TreeExplainer(xgb)
sv = explainer(X[test])
FIGURES.mkdir(parents=True, exist_ok=True)
plt.figure()
shap.plots.beeswarm(sv, max_display=15, show=False)
plt.title("XGBoost SHAP values on 2026 test rows (target = ratio to 28-day level)")
plt.tight_layout()
plt.savefig(FIGURES / "05_xgb_shap_beeswarm.png", dpi=150, bbox_inches="tight")
plt.close()
mean_abs = dict(sorted(zip(X.columns, np.abs(sv.values).mean(axis=0).round(4).tolist()), key=lambda kv: -kv[1]))
report["xgboost"]["mean_abs_shap"] = mean_abs

(RESULTS / "metrics_03_tree_models.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
for k in ["random_forest", "xgboost"]:
    v = report[k]
    print(f"{k:14s} MAE {v['MAE']:.2f}  RMSE {v['RMSE']:.2f}  MAPE {v['MAPE_%']:.2f}%  best {v['best']['params']}")
print("Top SHAP features:", list(mean_abs.items())[:8])

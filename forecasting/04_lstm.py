"""Step 4 - an LSTM sequence model in PyTorch.

Input for one sample (hospital, origin t):
  * the last 28 days t-27..t: attendance ratio to the 28-day level, a missing
    flag, weekday one-hot and holiday flag  -> sequence of shape (28, 10)
  * calendar facts of the 7 target days (known in advance)  -> 7 x 12
  * a learned embedding of the hospital
Output: the 7 ratios for days t+1..t+7 in one shot (multi-output).

Tuning / early stopping uses the last CV fold (Nov-Dec 2025). The model is
then refit on the full training period for the chosen number of epochs.
Five random seeds are trained; their average is the reported prediction.
"""

import json

import numpy as np
import pandas as pd
import torch
from torch import nn

from common import (LEVEL_WINDOW, RESULTS, TRAIN_END, build_rows, calendar_frame, load_wide,
                    metrics, save_predictions, test_masks)

torch.set_num_threads(4)
SEQ = 28
SEEDS = [0, 1, 2, 3, 4]
VAL_START, VAL_END = pd.Timestamp("2025-11-01"), TRAIN_END

wide = load_wide()
hospitals = list(wide.columns)
dates = wide.index
cal = calendar_frame(dates.append(pd.date_range(dates.max() + pd.Timedelta(days=1), periods=7)))
dow_oh = np.eye(7)[cal["dow"].to_numpy()]
fut_cal = np.column_stack([dow_oh, cal[["is_holiday", "after_holiday", "before_holiday", "doy_sin", "doy_cos"]].to_numpy()])
past_cal = np.column_stack([dow_oh, cal[["is_holiday"]].to_numpy()])

samples = []  # (hospital index, origin position)
seq_x, fut_x, hosp_x, target, level_v, origin_v = [], [], [], [], [], []
for hi, h in enumerate(hospitals):
    y = wide[h].to_numpy()
    level = pd.Series(y).rolling(LEVEL_WINDOW, min_periods=21).mean().to_numpy()
    for t in range(SEQ - 1, len(dates)):
        if np.isnan(level[t]):
            continue
        window = y[t - SEQ + 1:t + 1] / level[t]
        miss = np.isnan(window)
        seq = np.column_stack([np.where(miss, 1.0, window), miss.astype(float), past_cal[t - SEQ + 1:t + 1]])
        tgt = np.full(7, np.nan)
        n_future = min(7, len(dates) - 1 - t)
        tgt[:n_future] = y[t + 1:t + 1 + n_future] / level[t]
        seq_x.append(seq)
        fut_x.append(fut_cal[t + 1:t + 8].reshape(-1))
        hosp_x.append(hi)
        target.append(tgt)
        level_v.append(level[t])
        origin_v.append(dates[t])

seq_x = torch.tensor(np.array(seq_x), dtype=torch.float32)
fut_x = torch.tensor(np.array(fut_x), dtype=torch.float32)
hosp_x = torch.tensor(hosp_x)
target = torch.tensor(np.array(target), dtype=torch.float32)
level_v = np.array(level_v)
origin_v = pd.DatetimeIndex(origin_v)
last_target_date = origin_v + pd.Timedelta(days=7)


class Forecaster(nn.Module):
    def __init__(self, hidden: int, n_hosp: int, fut_dim: int):
        super().__init__()
        self.lstm = nn.LSTM(seq_x.shape[2], hidden, batch_first=True)
        self.emb = nn.Embedding(n_hosp, 4)
        self.head = nn.Sequential(
            nn.Linear(hidden + fut_dim + 4, 64), nn.ReLU(), nn.Dropout(0.2), nn.Linear(64, 7))

    def forward(self, seq, fut, hosp):
        _, (h_n, _) = self.lstm(seq)
        return self.head(torch.cat([h_n[-1], fut, self.emb(hosp)], dim=1))


def masked_mse(pred, tgt):
    mask = ~torch.isnan(tgt)
    return ((pred - torch.nan_to_num(tgt)) ** 2)[mask].mean()


def train_model(idx_train, hidden, epochs, seed, idx_val=None, patience=20):
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = Forecaster(hidden, len(hospitals), fut_x.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    best = (np.inf, 0, None)
    bad = 0
    for ep in range(1, epochs + 1):
        model.train()
        perm = idx_train[torch.randperm(len(idx_train))]
        for b in range(0, len(perm), 64):
            i = perm[b:b + 64]
            opt.zero_grad()
            loss = masked_mse(model(seq_x[i], fut_x[i], hosp_x[i]), target[i])
            loss.backward()
            opt.step()
        if idx_val is not None:
            mae = val_mae(model, idx_val)
            if mae < best[0]:
                best, bad = (mae, ep, None), 0
            else:
                bad += 1
                if bad >= patience:
                    break
    return model, best


def predict(model, idx):
    model.eval()
    with torch.no_grad():
        return model(seq_x[idx], fut_x[idx], hosp_x[idx]).numpy()


def val_mae(model, idx):
    pred = predict(model, idx) * level_v[idx.numpy(), None]
    tgt = target[idx].numpy() * level_v[idx.numpy(), None]
    # Only targets that fall inside the validation window count.
    days = origin_v[idx.numpy()].to_numpy()[:, None] + np.arange(1, 8) * np.timedelta64(1, "D")
    ok = ~np.isnan(tgt) & (days >= np.datetime64(VAL_START)) & (days <= np.datetime64(VAL_END))
    return float(np.abs(pred - tgt)[ok].mean())


# --- Tuning on the last CV fold: hidden size and number of epochs (early stopping) ---
fit_idx = torch.tensor(np.where(last_target_date <= VAL_START - pd.Timedelta(days=1))[0])
val_idx = torch.tensor(np.where((origin_v >= VAL_START - pd.Timedelta(days=1)) & (origin_v < VAL_END))[0])
tuning = {}
for hidden in [32, 64]:
    runs = [train_model(fit_idx, hidden, 200, s, val_idx)[1] for s in SEEDS[:3]]
    tuning[hidden] = {"val_mae": float(np.mean([r[0] for r in runs])), "best_epoch": int(np.median([r[1] for r in runs]))}
    print(f"hidden={hidden}: val MAE {tuning[hidden]['val_mae']:.2f}, best epoch {tuning[hidden]['best_epoch']}")
hidden = min(tuning, key=lambda k: tuning[k]["val_mae"])
epochs = tuning[hidden]["best_epoch"]

# --- Final fit on all training origins whose 7 targets are all <= TRAIN_END ---
train_idx = torch.tensor(np.where(last_target_date <= TRAIN_END)[0])
test_origin_idx = np.where(origin_v >= TRAIN_END)[0]
seed_preds = []
for s in SEEDS:
    model, _ = train_model(train_idx, hidden, epochs, s)
    seed_preds.append(predict(model, torch.tensor(test_origin_idx)))
    print(f"seed {s} trained")

# Map multi-output predictions back to the shared (hospital, origin, h) test rows.
rows = build_rows(wide)
_, test = test_masks(rows)
te = rows[test]
lookup = {(hospitals[hosp_x[i].item()], origin_v[i]): k for k, i in enumerate(test_origin_idx)}
k_idx = np.array([lookup[(r.hospital, r.origin)] for r in te.itertuples()])
h_idx = te["h"].to_numpy() - 1
lev = level_v[test_origin_idx][k_idx]
per_seed = [metrics(te["y"], p[k_idx, h_idx] * lev)["MAE"] for p in seed_preds]
ensemble = np.mean(seed_preds, axis=0)[k_idx, h_idx] * lev
save_predictions("lstm", te, ensemble)
report = {"lstm": metrics(te["y"], ensemble) | {
    "hidden": hidden, "epochs": epochs, "tuning": tuning,
    "per_seed_MAE": per_seed, "per_seed_MAE_mean": float(np.mean(per_seed)), "per_seed_MAE_sd": float(np.std(per_seed, ddof=1)),
}}
(RESULTS / "metrics_04_lstm.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
v = report["lstm"]
print(f"lstm (5-seed mean) MAE {v['MAE']:.2f}  RMSE {v['RMSE']:.2f}  MAPE {v['MAPE_%']:.2f}%  "
      f"single seeds {v['per_seed_MAE_mean']:.2f} +/- {v['per_seed_MAE_sd']:.2f}")

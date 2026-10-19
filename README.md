# 新加坡医院运营公开数据分析（Singapore Hospital Operations Analytics）

这是基于新加坡卫生部公开历史数据的个人分析项目，用于监测院级指标、定位值得复核的时段，并说明下一步应补充什么证据。它没有医院内部运营权限、策略采纳记录或实施效果数据。

## 扩展：未来 7 天急诊就诊量预测（`forecasting/`）

用同一份数据（9 家医院 × 2024-01 至 2026-09 每日急诊量）预测未来 1–7 天每家医院的急诊人数，对比 6 种方法。所有特征只使用预测起点当天及以前的数据；训练集为 2024–2025 年，2026 年作为测试集只评估一次；参数通过扩展窗口时间序列交叉验证选择。

| 模型 | MAE（人/天） | RMSE | MAPE |
|---|---|---|---|
| 季节性朴素（上周同一天） | 24.05 | 31.44 | 8.82% |
| 4 周同星期均值 | 18.92 | 25.08 | 6.91% |
| Ridge 回归 | 16.61 | 21.61 | 6.12% |
| 随机森林 | 16.40 | 21.36 | 6.08% |
| XGBoost | 16.47 | 21.30 | 6.06% |
| LSTM（PyTorch，5 个种子平均） | 16.04 | 20.73 | 5.87% |

- 机器学习模型相比 4 周同星期均值 MAE 降低约 13%–15%（按周区组 bootstrap，95% CI 不含 0）。
- Ridge、随机森林、XGBoost、LSTM 之间差异不显著（例如 LSTM − XGBoost：−0.43，95% CI [−1.04, +0.14]）。
- SHAP 显示星期一、公众假期及假期次日是最主要的影响因素。

详细方法、结果解释与局限见 [forecasting/讲解笔记.md](forecasting/讲解笔记.md)。

## 先看结果

双击 [index.html](index.html) 即可使用本地看板。无需启动服务器，页面加载本地数据，不发送外部请求。请保留整个仓库文件夹，不要只复制单个 HTML 文件。

然后阅读 [简短报告](简短报告.md)。想亲手核对一个数值时，完成 [亲手练习](亲手练习.md) 与 [练习.sql](练习.sql)，运行 `python run_exercise.py`；练习使用 SQLite 语法，运行器仅依赖 Python 标准库。

## 从原始数据重建

原始 Excel 在 [raw_data](raw_data)，官方来源、下载日期和文件校验见该目录的 [下载来源.md](raw_data/下载来源.md)。这是已保存的历史快照，重建不会自动下载最新数据，也不会改动原始文件。

安装 Python 后，在本 README 所在目录打开终端，依次运行：

```powershell
python -m pip install -r requirements.txt
python build_data.py
```

脚本从原始工作簿重新生成 `data/dashboard-data.js`、`data/dashboard-data.json`、`data/hospital_metrics.csv`、`data/hospital_metrics.sqlite` 和核查记录 `data/build-audit.json`，供看板、复核与练习使用。页面通过本地 JS 数据文件读取结果，不依赖 `file://` 下可能受限的网络式读取。重建会更新生成文件；如修改了数据处理逻辑，应重新检查报告中的固定案例数值。


## 底表与指标口径

SQLite 表名为 `hospital_metrics`，沿用此前处理脚本的字段：

| 字段 | 含义 |
|---|---|
| `date`、`hospital_code` | 官方所属日期与原医院编码，共同组成唯一键 |
| `ed_attendances` | 当日急诊就诊次数；不能等同于决定收治住院人数 |
| `bor_ratio` | 午夜床位占用比例，0.95 显示为 95%；不是全天各病区可接收床位 |
| `admission_wait_p50_hours` | 当日入院等待第 50 百分位数，单位小时 |
| `availability` | 三项指标的数值可得状态 |
| `ed_source`、`bor_source`、`wait_source` | 对应原工作表及单元格位置 |

三项数据按日期和医院编码一对一外连接，缺失保留为空，不以 0 填补。合表包含 8,874 条医院日期记录，8,637 条三项完整。同日匹配不代表同一批患者，也不保证三个指标的观察时间完全一致。

看板中的多日等待均值是每日 P50 的简单平均，不是合并所有患者后的平均数或中位数。AH 的公开数据对应 Urgent Care；跨急诊医院比较需保留这一范围差异，缺失数据不能视为没有等待。院级相关和历史趋势不证明因果。

## 这个版本做到哪里

当前完成的是公开数据整理、指标展示、CGH 历史异常复核及下一步数据核查建议。尚未验证缺人或其他具体原因，不能从现有指标计算招聘人数。没有业务使用与实施记录时，策略采纳率、执行率和真实等待改善均不可报告；后续自然回落不属于本项目效果。

## 仓库结构

| 位置 | 内容 |
|---|---|
| `index.html`、`app.js`、`logic.js`、`styles.css` | 本地看板 |
| `build_data.py` | 从原始 Excel 重建底表（CSV / JSON / SQLite） |
| `raw_data/` | MOH 官方原始 Excel 快照与下载记录 |
| `docs/` | CGH 异常时段复核的分析记录与图表 |
| `analysis_scripts/` | 产出 `docs/` 的历史分析脚本，按原工作区目录结构编写，仅供追溯，不保证在本仓库直接运行 |
| `练习.sql`、`run_exercise.py` | SQL 练习 |
| `forecasting/` | 急诊量预测：特征、5 个建模脚本、结果与图表 |

数据来源：Ministry of Health, Singapore 公开统计，版权归原发布方；本仓库仅用于个人学习与分析展示。

本次验证范围见 [验证记录](验证记录.md)。安装 Node.js 后，可运行 `node verify_dashboard.cjs` 复核六组业务计算及缺失处理案例。看板的 CSV 导出内容已校验；内置浏览器未确认实际下载落盘，如无法保存，可在 Edge 或 Chrome 中打开本地看板，或直接使用 `data/hospital_metrics.csv` 完整整理表。

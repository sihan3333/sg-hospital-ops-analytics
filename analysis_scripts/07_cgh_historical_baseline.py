"""Describe CGH's target week against prior complete, non-overlapping weeks."""
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '处理脚本'
OUT = ROOT / 'outputs/01a0bcf0-303c-7d21-9f82-aafceef76c21'
WORK = SCRIPTS / '.work_baseline'
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SCRIPTS / '.plot_packages'))
os.environ['MPLCONFIGDIR'] = str(WORK / 'matplotlib_cache')

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager

payload = json.loads((SCRIPTS / '.work_join/hospital_metrics.json').read_text(encoding='utf-8'))
source_audit = payload['datasets']['wait']['audit']
source = ROOT / '原始数据/2026-09-20' / source_audit['file']
assert sha256(source.read_bytes()).hexdigest() == source_audit['sha256']
data = pd.DataFrame(payload['joined']['rows'], columns=payload['joined']['fields'])
data['date'] = pd.to_datetime(data['date'])
data = data.loc[data.hospital_code.eq('CGH')].set_index('date').sort_index()
assert not data.index.duplicated().any()
target_start = pd.Timestamp('2024-05-02')

def window(start):
    end = start + pd.Timedelta(days=6)
    rows = data.loc[start:end]
    assert rows.index.equals(pd.date_range(start, end, name='date'))
    assert rows.admission_wait_p50_hours.notna().all()
    return {'start': start.strftime('%Y-%m-%d'), 'end': end.strftime('%Y-%m-%d'),
            'n_days': len(rows), 'mean_daily_p50_hours': float(rows.admission_wait_p50_hours.mean()),
            'daily_values': [float(v) for v in rows.admission_wait_p50_hours],
            'source_cells': list(rows.wait_source)}

prior12 = [window(target_start - pd.Timedelta(days=7 * weeks)) for weeks in range(12, 0, -1)]
target = window(target_start)
baseline = prior12[-8:]
weekly_changes = [b['mean_daily_p50_hours'] - a['mean_daily_p50_hours']
                  for a, b in zip(baseline[:-1], baseline[1:])]
target_change = target['mean_daily_p50_hours'] - baseline[-1]['mean_daily_p50_hours']
summaries = []
for weeks in [4, 8, 12]:
    group = prior12[-weeks:]
    levels = [row['mean_daily_p50_hours'] for row in group]
    average = sum(levels) / len(levels)
    summaries.append({'weeks': weeks, 'start': group[0]['start'], 'end': group[-1]['end'],
                      'n_days': sum(row['n_days'] for row in group),
                      'baseline_mean': average, 'weekly_min': min(levels), 'weekly_max': max(levels),
                      'target_minus_baseline_mean': target['mean_daily_p50_hours'] - average,
                      'target_to_baseline_mean_ratio': target['mean_daily_p50_hours'] / average})
main = summaries[1]
audit = {'hospital': 'CGH', 'source_sha256': source_audit['sha256'], 'prior12': prior12, 'target': target,
         'baselines': summaries, 'target_week_on_week_change': target_change,
         'prior8_adjacent_changes': weekly_changes, 'prior8_max_adjacent_increase': max(weekly_changes),
         'selection_note': '目标周来自事后探索；本步为历史描述，不是实时检测回测。'}
(WORK / 'cgh_baseline_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')

font_path = 'C:/Windows/Fonts/msyh.ttc'
fontManager.addfont(font_path)
plt.rcParams['font.family'] = FontProperties(fname=font_path).get_name()
plt.rcParams['axes.unicode_minus'] = False
fig, ax = plt.subplots(figsize=(10.5, 6.6), dpi=160)
fig.patch.set_facecolor('#ffffff')
rows = baseline + [target]
labels = [f"{row['start'][5:].replace('-', '/')} - {row['end'][5:].replace('-', '/')}" for row in rows]
labels[-1] += ' 目标周'
levels = [row['mean_daily_p50_hours'] for row in rows]
ax.barh(range(len(rows)), levels, color=['#7898b6'] * 8 + ['#d06c35'], height=0.62)
ax.set_yticks(range(len(rows)), labels, fontsize=10)
ax.invert_yaxis()
ax.set_xlim(0, 25)
ax.set_xticks([0, 5, 10, 15, 20, 25])
ax.set_xlabel('每日入院等待中位数的七日均值（小时）', fontsize=11, labelpad=12)
ax.set_axisbelow(True)
ax.grid(axis='x', color='#e7ebef', linewidth=0.8)
for side in ['top', 'right', 'left']:
    ax.spines[side].set_visible(False)
ax.spines['bottom'].set_color('#c6cdd4')
ax.tick_params(axis='both', length=0, pad=8, colors='#36434f')
ax.axvline(main['baseline_mean'], color='#274e6a', linestyle='--', linewidth=1.3)
ax.text(main['baseline_mean'], 1.035, f"历史8周均值 {main['baseline_mean']:.2f}",
        transform=ax.get_xaxis_transform(), ha='center', color='#274e6a', fontsize=10)
for i, value in enumerate(levels):
    ax.text(value + 0.2, i, f'{value:.2f}', va='center', fontsize=10,
            fontweight='bold' if i == 8 else 'normal', color='#a54c20' if i == 8 else '#36434f')
ax.get_yticklabels()[-1].set_fontweight('bold')
fig.text(0.04, 0.945, 'CGH：目标周与此前 8 周的等待水平', fontsize=19, fontweight='bold', color='#223440')
fig.text(0.04, 0.89, '2024年，每周均为周四至周三；9个窗口各有完整7天数据。', fontsize=10.5, color='#5a6772')
fig.text(0.04, 0.035, '数据：MOH 每日等待 P50。虚线为历史参照均值，不是告警阈值或临床标准。', fontsize=9, color='#5a6772')
fig.subplots_adjust(left=0.22, right=0.96, top=0.80, bottom=0.16)
plot_path = OUT / 'CGH_20240502至0508_八周历史基线.png'
fig.savefig(plot_path, facecolor='white')
plt.close(fig)

week_table = '\n'.join(f"| {row['start']} 至 {row['end']} | {row['mean_daily_p50_hours']:.2f} | {row['n_days']} |" for row in rows)
sensitivity = '\n'.join(f"| {row['weeks']}周 | {row['start']} 至 {row['end']} | {row['baseline_mean']:.2f} | {row['weekly_min']:.2f}—{row['weekly_max']:.2f} | {row['target_to_baseline_mean_ratio']:.2f}倍 |" for row in summaries)
report = f'''# CGH 目标周与历史基线

目标：把 2024-05-02 至 05-08 的等待水平及周间增幅，放回 CGH 自己此前的历史中比较。所有周统计都是“每日入院等待中位数的七日简单平均”，单位小时。

## 基线怎样选

主基线为目标周之前连续8个完整周，2024-03-07 至 05-01，共56个日值。每周周四至周三，与目标窗口星期构成一致且互不重叠。另检查4周、12周，以观察选择不同历史长度时结果是否改变。8周是本次探索的分析选择，不是 MOH 标准、临床阈值或经回测选出的最佳长度。

基线不包含目标周或目标周之后的数据。它描述最近一段历史，不等同于正常、安全或理想水平。即使使用不重叠周，相邻周仍可能相关；56天和8个周统计也不等于患者样本数。

## 每周数值

| 窗口 | 每日P50的七日均值（小时） | 有效日数 |
|---|---:|---:|
{week_table}

![八周基线对照](CGH_20240502至0508_八周历史基线.png)

## 两种比较回答两个问题

1. **水平是否高于近期参照？** 8周均值为 {main['baseline_mean']:.2f} 小时，8个周值范围为 {main['weekly_min']:.2f}—{main['weekly_max']:.2f} 小时。目标周 {target['mean_daily_p50_hours']:.2f} 小时，比基线均值高 {main['target_minus_baseline_mean']:.2f} 小时，是其 {main['target_to_baseline_mean_ratio']:.2f} 倍，也高于这8个历史周的最高值。基线均值是8个周均值再平均，因各周都有7天，它也等于56个日P50的简单平均；不是56天全部患者的平均等待。
2. **与前周相比的增加幅度是否突出？** 目标周较前周增加 {target_change:.2f} 小时；基线8周内部共有7次相邻周变化，其中最大上升为 {max(weekly_changes):.2f} 小时。目标增幅大于这7次变化中的最大上升，但7次变化不足以估计可靠的异常概率。

上述结果支持“相对所选近期历史，目标周等待偏高且增幅突出”，不支持“已达到统计显著异常”或“已证明缺人”。超过有限历史最大值，也不能直接称为95%/99%置信或确定告警。

## 改变历史长度后的检查

| 基线长度 | 覆盖日期 | 基线均值（小时） | 各周值最小—最大（小时） | 目标/基线均值 |
|---|---|---:|---:|---:|
{sensitivity}

目标高于三个基线各自的最高周值，但4周参照均值高于8周和12周参照。这说明“偏高”的方向在这些选择下保持一致，具体倍数则依赖参照。没有由此宣称任意基线下都成立。未调整节假日、病例结构、季节性、人员或流程变化。

## 来源与复核

使用已核验底表的 CGH 等待字段，并核对原件 `{source.name}` 哈希、日期唯一性、每周完整日历及非空值。逐日原值和原单元格位置、12周统计及比较结果保存在 `处理脚本/.work_baseline/cgh_baseline_audit.json`，脚本为 `处理脚本/07_cgh_historical_baseline.py`。原件未修改。

目标周是从更长历史中事后选出的高点；尽管此次基线仅使用目标周之前的记录，本步仍是事后描述性分析，不是模拟成功提前预警。未来若制定告警规则，应另用此前数据设定规则并在未用于选例的后续时段验证误报、漏报和提前量。
'''
(OUT / 'CGH_20240502至0508_历史基线说明.md').write_text(report, encoding='utf-8')
print(json.dumps({'target_mean': target['mean_daily_p50_hours'], 'target_change': target_change,
                  'prior8_max_increase': max(weekly_changes), 'baselines': summaries}, ensure_ascii=True, indent=2))

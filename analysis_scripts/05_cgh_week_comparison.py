"""比较 CGH 两个相邻完整七日窗口；统计量分别按其含义汇总。"""
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/01a0bcf0-303c-7d21-9f82-aafceef76c21'
WORK = ROOT / '处理脚本/.work_comparison'
payload = json.loads((ROOT / '处理脚本/.work_join/hospital_metrics.json').read_text(encoding='utf-8'))
for item in payload['datasets'].values():
    source = ROOT / '原始数据/2026-09-20' / item['audit']['file']
    assert sha256(source.read_bytes()).hexdigest() == item['audit']['sha256']

data = pd.DataFrame(payload['joined']['rows'], columns=payload['joined']['fields'])
data['date'] = pd.to_datetime(data['date'])
data = data.loc[data.hospital_code.eq('CGH')].set_index('date').sort_index()
metrics = ['ed_attendances', 'bor_ratio', 'admission_wait_p50_hours']
windows = [('2024-04-25', '2024-05-01'), ('2024-05-02', '2024-05-08')]
groups, stats = [], []
for start, end in windows:
    group = data.loc[start:end].copy()
    assert group.index.equals(pd.date_range(start, end, name='date'))
    assert len(group) == 7 and not group[metrics].isna().any().any()
    assert not group.index.duplicated().any()
    groups.append(group)
    stats.append({'start': start, 'end': end, 'observed_days': len(group),
                  'ed_total': int(group.ed_attendances.sum()),
                  'mean_daily_bor_ratio': float(group.bor_ratio.mean()),
                  'mean_daily_wait_p50_hours': float(group.admission_wait_p50_hours.mean())})

before, after = stats
changes = {
    'ed_total_difference': after['ed_total'] - before['ed_total'],
    'ed_total_relative_change_pct': (after['ed_total'] / before['ed_total'] - 1) * 100,
    'mean_daily_bor_difference_pp': (after['mean_daily_bor_ratio'] - before['mean_daily_bor_ratio']) * 100,
    'mean_daily_wait_p50_difference_hours': after['mean_daily_wait_p50_hours'] - before['mean_daily_wait_p50_hours'],
    'mean_daily_wait_p50_relative_change_pct': (after['mean_daily_wait_p50_hours'] / before['mean_daily_wait_p50_hours'] - 1) * 100,
}
paired = groups[1][metrics].reset_index(drop=True) - groups[0][metrics].reset_index(drop=True)
same_weekday_higher = {metric: int(paired[metric].gt(0).sum()) for metric in metrics}
within_week = groups[1].admission_wait_p50_hours.diff().dropna()
audit = {'hospital': 'CGH', 'windows': stats, 'changes': changes,
         'higher_than_seven_days_earlier': same_weekday_higher,
         'within_target_week_p50_changes': {'up': int(within_week.gt(0).sum()), 'down': int(within_week.lt(0).sum())},
         'selection': '目标窗口来自前一步的事后探索，不是预注册检验或告警回测。'}
WORK.mkdir(parents=True, exist_ok=True)
(WORK / 'comparison_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')

daily = pd.concat(groups)
detail = '\n'.join(f'| {day:%Y-%m-%d} | {int(row.ed_attendances)} | {row.bor_ratio:.2%} | {row.admission_wait_p50_hours:.2f} |' for day, row in daily.iterrows())
source_rows = '\n'.join(f'| {day:%Y-%m-%d} | {row.ed_source} | {row.bor_source} | {row.wait_source} |' for day, row in daily.iterrows())
text = f'''# CGH 等待偏高阶段：首次三指标对照

问题：2024-05-02 至 05-08 的等待中位数持续偏高时，急诊就诊量和床位占用率是否也发生变化？参照窗口为此前完整七天 2024-04-25 至 05-01。

## 汇总结果

| 指标 | 04-25 至 05-01 | 05-02 至 05-08 | 变化 |
|---|---:|---:|---:|
| 急诊就诊总量（次） | {before['ed_total']:,} | {after['ed_total']:,} | +{changes['ed_total_difference']} 次（+{changes['ed_total_relative_change_pct']:.1f}%） |
| 每日午夜 BOR 的简单均值 | {before['mean_daily_bor_ratio']:.2%} | {after['mean_daily_bor_ratio']:.2%} | +{changes['mean_daily_bor_difference_pp']:.2f} 个百分点 |
| 每日等待 P50 的简单均值（小时） | {before['mean_daily_wait_p50_hours']:.2f} | {after['mean_daily_wait_p50_hours']:.2f} | +{changes['mean_daily_wait_p50_difference_hours']:.2f} 小时（+{changes['mean_daily_wait_p50_relative_change_pct']:.1f}%） |

每个窗口三项指标各有 7 个日值，没有缺失。汇总和变化均用未四舍五入的源值计算。

## 方法与指标解释

- 两段均为连续七天，各含星期一至星期日各一次，有助于避免比较窗口中星期构成不同。相邻窗口仍可能受到节假日、病例构成、资源或流程变化影响。
- 急诊量按七天求和，单位为就诊次数，不是去重患者数或住院人数。
- BOR 是七次午夜比例的简单平均，不是全天平均、实时床位余量或用床日分子分母重算的总体占用率。其床位分母详细范围仍待 MOH 核实。
- 等待指标是七个日中位数的平均，不是全部患者的平均等待或总体中位数。
- 百分点表示两个百分比直接相减：约 90.96% − 89.42% = 1.54 个百分点；这与相对增长百分比不同。

## 当前观察与后续核查

急诊总量小幅增加、午夜 BOR 日均值上升、等待 P50 日均值上升，三者同时出现。目标周七个日 P50 都高于七天前的同星期值；但目标周内相邻日有 4 次下降、2 次上升，不能说每天都比前一天高。

这次对照不能证明 BOR 上升导致了等待上升，也不能排除急诊需求的影响。总就诊量无法反映住院比例、小时内高峰或所需床位类型。后续可继续查看更长的同星期历史基线和指标的日度变化、滞后关联；小时内高峰、住院比例及流程或资源变化需要额外资料，当前未取得相应院内数据。

该窗口是从前一步趋势中事后选出的案例，仅用于描述性探索。尚未做正式异常检验、模型回测、因果识别或业务策略效果评估。

## 每日数值

| 日期 | 急诊就诊量（次） | 午夜 BOR | 等待 P50（小时） |
|---|---:|---:|---:|
{detail}

## 原始单元格位置

对应本项目 2026-09-20 下载的急诊量、BOR 和等待三个 week36Y2026 原件。原始文件均未改动。

| 日期 | 急诊量原件 | BOR 原件 | 等待原件 |
|---|---|---|---|
{source_rows}

已由独立复核从三份原始 Excel 重算并确认两组数值与汇总一致。
'''
OUT.mkdir(parents=True, exist_ok=True)
report = OUT / 'CGH_20240502至0508_三指标对照.md'
report.write_text(text, encoding='utf-8')
print(json.dumps(audit, ensure_ascii=True, indent=2))

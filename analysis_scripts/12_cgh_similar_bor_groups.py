"""Describe ED and weekday differences within a selected CGH BOR band."""
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '处理脚本'
OUT = ROOT / 'outputs/01a0bcf0-303c-7d21-9f82-aafceef76c21'
WORK = SCRIPTS / '.work_association'
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(SCRIPTS / '.plot_packages'))
os.environ['MPLCONFIGDIR'] = str(WORK / 'matplotlib_cache')

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties, fontManager

source_audit = json.loads((WORK / 'cgh_daily_association_audit.json').read_text(encoding='utf-8'))
for source in source_audit['sources'].values():
    path = ROOT / '原始数据/2026-09-20' / source['file']
    assert sha256(path.read_bytes()).hexdigest() == source['sha256']
data = pd.DataFrame(source_audit['daily'])
data['date'] = pd.to_datetime(data['date'])
assert not data.date.duplicated().any()
data = data.loc[data.date.dt.year.eq(2024)].sort_values('date').copy()
assert list(data.date) == list(pd.date_range('2024-01-01', '2024-12-31'))
assert data[['ed_attendances', 'bor_ratio', 'admission_wait_p50_hours']].notna().all().all()
data['weekday'] = data.date.dt.dayofweek
weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


def summarize(frame):
    if frame.empty:
        return {'n_days': 0, 'ed_min': None, 'ed_max': None, 'ed_mean': None,
                'bor_mean_pct': None, 'wait_daily_p50_mean_hours': None,
                'weekend_days': 0, 'weekend_share': None}
    return {
        'n_days': len(frame), 'ed_min': float(frame.ed_attendances.min()),
        'ed_max': float(frame.ed_attendances.max()), 'ed_mean': float(frame.ed_attendances.mean()),
        'bor_mean_pct': float(frame.bor_ratio.mean() * 100),
        'wait_daily_p50_mean_hours': float(frame.admission_wait_p50_hours.mean()),
        'weekend_days': int(frame.weekday.ge(5).sum()), 'weekend_share': float(frame.weekday.ge(5).mean()),
    }


def band_analysis(lower, upper):
    frame = data.loc[data.bor_ratio.ge(lower) & data.bor_ratio.lt(upper)].copy()
    median = float(frame.ed_attendances.median())
    frame['ed_group'] = frame.ed_attendances.gt(median).map({False: 'low', True: 'high'})
    groups = {name: summarize(frame.loc[frame.ed_group.eq(name)]) for name in ['low', 'high']}
    by_weekday = [{
        'weekday': weekday, 'label': weekdays[weekday], **summarize(frame.loc[frame.weekday.eq(weekday)]),
    } for weekday in range(7)]
    cross = [{
        'weekday': weekday, 'label': weekdays[weekday], 'ed_group': name,
        **summarize(frame.loc[frame.weekday.eq(weekday) & frame.ed_group.eq(name)]),
    } for weekday in range(7) for name in ['low', 'high']]
    assert sum(group['n_days'] for group in groups.values()) == len(frame)
    assert sum(group['n_days'] for group in by_weekday) == len(frame)
    assert sum(group['n_days'] for group in cross) == len(frame)
    daily = frame.copy()
    daily['date'] = daily.date.dt.strftime('%Y-%m-%d')
    return {
        'lower_bor_inclusive': lower, 'upper_bor_exclusive': upper, 'n_days': len(frame),
        'ed_median_cutoff': median, 'days_equal_to_cutoff': int(frame.ed_attendances.eq(median).sum()),
        'groups': groups, 'by_weekday': by_weekday, 'weekday_ed_cross': cross,
        'high_minus_low_wait_hours': groups['high']['wait_daily_p50_mean_hours'] - groups['low']['wait_daily_p50_mean_hours'],
        'high_minus_low_bor_pp': groups['high']['bor_mean_pct'] - groups['low']['bor_mean_pct'],
        'daily': daily.to_dict(orient='records'),
    }


main = band_analysis(0.89, 0.91)
sensitivity = band_analysis(0.88, 0.92)
low, high = main['groups']['low'], main['groups']['high']
audit = {
    'hospital': 'CGH', 'year': 2024, 'complete_year_days': len(data), 'sources': source_audit['sources'],
    'parameters': {'primary_bor_band': '[0.89, 0.91)', 'sensitivity_bor_band': '[0.88, 0.92)',
                   'ed_split': 'Recompute ED median within each band; low <= median, high > median.',
                   'weekend_definition': 'Saturday and Sunday only; public holidays not classified.'},
    'main': main, 'sensitivity': sensitivity,
    'limitations': ['Exploratory descriptive grouping, not causal adjustment.',
                    'BOR values are similar, not identical; weekday and month composition may differ.',
                    'Sparse and empty weekday-by-ED cells prevent stable comparisons in some strata.',
                    'No significance, causal effect, or predictive gain estimated.'],
}
(WORK / 'cgh_similar_bor_groups_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')

font_path = 'C:/Windows/Fonts/msyh.ttc'
fontManager.addfont(font_path)
plt.rcParams['font.family'] = FontProperties(fname=font_path).get_name()
plt.rcParams['axes.unicode_minus'] = False
colors = {'low': '#4f7c9e', 'high': '#cf763c'}
fig, axes = plt.subplots(1, 2, figsize=(11.8, 6.0), dpi=160, gridspec_kw={'width_ratios': [0.85, 1.15]})
fig.patch.set_facecolor('white')
ax = axes[0]
values = [low['wait_daily_p50_mean_hours'], high['wait_daily_p50_mean_hours']]
ax.bar([0, 1], values, color=[colors['low'], colors['high']], width=0.57)
ax.set_xticks([0, 1], [f"急诊量较低组\n≤{main['ed_median_cutoff']:g}次/日（{low['n_days']}天）",
                       f"急诊量较高组\n>{main['ed_median_cutoff']:g}次/日（{high['n_days']}天）"], fontsize=10)
ax.set_ylim(0, 18)
ax.set_ylabel('组内每日等待中位数的均值（小时）', fontsize=10)
ax.set_title('平均占用率相近，等待均值不同', fontsize=12, pad=14)
for i, (value, group) in enumerate(zip(values, [low, high])):
    ax.text(i, value + 0.35, f'{value:.2f}小时', ha='center', fontsize=12, color='#253e50', fontweight='bold')
    ax.text(i, 0.55, f"BOR均值\n{group['bor_mean_pct']:.2f}%", ha='center', va='bottom', color='white', fontsize=10)

ax = axes[1]
for name, offset in [('low', -0.19), ('high', 0.19)]:
    counts = [row['n_days'] for row in main['weekday_ed_cross'] if row['ed_group'] == name]
    ax.bar([i + offset for i in range(7)], counts, width=0.36, color=colors[name],
           label='急诊量较低组' if name == 'low' else '急诊量较高组')
    for i, count in enumerate(counts):
        ax.text(i + offset, count + 0.35, str(count), ha='center', fontsize=9, color='#334b5e')
ax.set_xticks(range(7), weekdays, fontsize=10)
ax.set_ylim(0, 30)
ax.set_ylabel('纳入日期数量（天）', fontsize=10)
ax.set_title('但两组的星期构成并不相同', fontsize=12, pad=14)
for ax in axes:
    ax.set_axisbelow(True)
    ax.grid(axis='y', color='#e7edf1', linewidth=0.7)
    for side in ['top', 'right']:
        ax.spines[side].set_visible(False)
    for side in ['left', 'bottom']:
        ax.spines[side].set_color('#c5cfd8')
    ax.tick_params(axis='y', labelsize=9, colors='#4d6070')
fig.text(0.055, 0.945, 'CGH：占用率相近时，急诊量与等待的分组比较',
         fontsize=18, fontweight='bold', color='#253e50')
fig.text(0.055, 0.893, f"2024年；89% ≤ BOR < 91%；{main['n_days']}个完整日。以组内急诊量中位数{main['ed_median_cutoff']:g}次为分界。",
         fontsize=10.5, color='#526a7d')
handles, labels = axes[1].get_legend_handles_labels()
fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(0.62, 0.070), ncol=2, frameon=False, fontsize=10)
fig.text(0.055, 0.027, '来源：MOH公开日指标。占用率相近不等于其他条件相同；分组差值不能直接解释为急诊量的因果影响。',
         fontsize=9, color='#526a7d')
fig.subplots_adjust(left=0.08, right=0.98, top=0.76, bottom=0.22, wspace=0.28)
fig.savefig(OUT / 'CGH_相近占用率_急诊量与星期对照.png', facecolor='white')
plt.close(fig)


def group_table(result):
    return '\n'.join(
        f"| {'较低' if name == 'low' else '较高'}组：急诊量{'≤' if name == 'low' else '>'}{result['ed_median_cutoff']:g} | "
        f"{group['n_days']} | {group['ed_min']:.0f}—{group['ed_max']:.0f} | {group['ed_mean']:.2f} | "
        f"{group['bor_mean_pct']:.2f}% | {group['wait_daily_p50_mean_hours']:.2f} |"
        for name, group in result['groups'].items())


weekday_table = '\n'.join(f"| {row['label']} | {row['n_days']} | {row['ed_mean']:.2f} | {row['bor_mean_pct']:.2f}% | {row['wait_daily_p50_mean_hours']:.2f} |" for row in main['by_weekday'])
cross_lines = []
for weekday in range(7):
    cells = {row['ed_group']: row for row in main['weekday_ed_cross'] if row['weekday'] == weekday}
    a, b = cells['low'], cells['high']
    fmt = lambda row: f"{row['wait_daily_p50_mean_hours']:.2f}" if row['n_days'] else '不适用'
    cross_lines.append(f"| {weekdays[weekday]} | {a['n_days']} | {fmt(a)} | {b['n_days']} | {fmt(b)} |")
cross_table = '\n'.join(cross_lines)
report = f'''# CGH：在相近床位占用率下比较急诊量与星期

本步用已有日数据继续检查关联：占用率相近的日期，急诊量和星期几是否伴随不同的等待水平？这是探索性的分组比较，不是预测模型或因果估计。

## 怎样选数据

1. 先限定2024年CGH，366个日期的三指标均完整。前课发现分年相关强弱不同，本步先不混合年份，也与2024年五月案例处于同一年。
2. 选原始午夜BOR满足89%≤BOR<91%的日期，共{main['n_days']}天。区间围绕前课图中讨论的90%作教学选择，不是医疗阈值；没有先把BOR四舍五入再筛选。
3. 在这{main['n_days']}天中，计算急诊量中位数{main['ed_median_cutoff']:g}次，以≤中位数和>中位数分组。恰好等于中位数的{main['days_equal_to_cutoff']}天归较低组。所谓高低仅相对此样本，不是官方拥挤标准。
4. 每组计算日期数、急诊量范围和均值、BOR均值、每日等待P50的简单均值；然后检查星期构成及星期内部的分组结果。日期是样本单位，不能当成患者人数。

## 两组总体比较

| 急诊量组别（次/日） | 天数 | 急诊量范围 | 急诊量均值 | BOR均值 | 每日P50均值（小时） |
|---|---:|---:|---:|---:|---:|
{group_table(main)}

较高组比低组的等待均值高{main['high_minus_low_wait_hours']:.2f}小时，两组BOR均值仅相差{main['high_minus_low_bor_pp']:.4f}个百分点。但BOR落入同一范围、均值接近，不等于所有条件相同；不能把{main['high_minus_low_wait_hours']:.2f}小时称为“急诊量增加造成的等待”。

![相近BOR下的急诊量分组和星期构成](CGH_相近占用率_急诊量与星期对照.png)

## 星期构成为什么要检查

较低组有{low['weekend_days']}/{low['n_days']}个周六或周日，占{low['weekend_share']:.2%}；较高组仅{high['weekend_days']}/{high['n_days']}，占{high['weekend_share']:.2%}。两组同时在急诊量与星期构成上不同，无法把差值单独归给其中一个因素。这里“周末”只指周六周日，没有把公众假期划成工作日或非工作日。

在同一个BOR范围内，单按星期汇总：

| 星期 | 天数 | 急诊量均值（次） | BOR均值 | 每日等待P50均值（小时） |
|---|---:|---:|---:|---:|
{weekday_table}

这个样本中的星期差异可以作为进一步调查线索，不说明星期本身造成等待，也不能直接推断周末有更多人员或流程更好。

## 再细分后，有些组并没有足够的可比日期

同一{main['ed_median_cutoff']:g}次分界下，逐星期比较：

| 星期 | 较低组天数 | 较低组等待均值 | 较高组天数 | 较高组等待均值 |
|---|---:|---:|---:|---:|
{cross_table}

周一较低组仅1天、周六较高组仅1天，周日没有较高组；0天组的均值应显示“不适用”，不能填0小时。周五、周六的均值方向与整体不同，也不能据这些小组断言稳定反向关系。星期相同后仍可能有BOR具体数值、月份、病例、床位类型等差异，目前没有充分调整这些因素。

## 改变区间后的描述性检查

将BOR范围放宽到88%≤BOR<92%，得到{sensitivity['n_days']}天；在新样本重新按急诊量中位数{sensitivity['ed_median_cutoff']:g}次分组：

| 急诊量组别（次/日） | 天数 | 急诊量范围 | 急诊量均值 | BOR均值 | 每日P50均值（小时） |
|---|---:|---:|---:|---:|---:|
{group_table(sensitivity)}

本次放宽区间后，较高组的等待均值仍较高。但样本、中位数分界和BOR组间差异同时改变，这只检查所选另一种分组下的描述方向，不是因果或预测增益验证，没有搜索最佳区间。

## 当前结论及业务用途

在所选2024年CGH、89%—不足91%的BOR样本中，急诊量较高组有更高的等待均值，星期构成也明显不同。结果支持在看板中同时查看急诊量和星期信息，并为后续比较检查可比日期；不能确定二者各自的独立作用，也不能据此直接制定排班或招聘数量。小样本分组说明进一步细分并非总能产生可靠比较。

等待是入院相关人群的日P50，急诊量是全部急诊就诊次数，BOR是午夜快照；记录日期一致不代表同一批患者或先后因果关系。本步未调整日期自相关、节假日、病例或资源变化，未做显著性检验、预测评估或策略效果评估。

## 可复现与来源

脚本为`处理脚本/12_cgh_similar_bor_groups.py`，读取前课已核验的完整日记录并重新核对三份原始Excel哈希。脚本验证2024年完整日期和唯一性，检查各分组天数能回加至选定样本；详细日值与原单元格、主分析及敏感性参数保存在`处理脚本/.work_association/cgh_similar_bor_groups_audit.json`。没有改动原始记录，其他年份及区间外日期仍保留在底表。
'''
(OUT / 'CGH_相近占用率_急诊量与星期分析.md').write_text(report, encoding='utf-8')
print(json.dumps({'main_n': main['n_days'], 'main_median_ed': main['ed_median_cutoff'],
                  'main_groups': main['groups'], 'main_wait_difference_hours': main['high_minus_low_wait_hours'],
                  'sensitivity_n': sensitivity['n_days'], 'sensitivity_median_ed': sensitivity['ed_median_cutoff'],
                  'sensitivity_groups': sensitivity['groups']}, ensure_ascii=True, indent=2))

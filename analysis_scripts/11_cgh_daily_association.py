"""Describe same-date associations within CGH; no causal or forecasting claims."""
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

payload = json.loads((SCRIPTS / '.work_join/hospital_metrics.json').read_text(encoding='utf-8'))
sources = {}
for metric in ['ed', 'bor', 'wait']:
    info = payload['datasets'][metric]['audit']
    source = ROOT / '原始数据/2026-09-20' / info['file']
    assert sha256(source.read_bytes()).hexdigest() == info['sha256']
    sources[metric] = {'file': info['file'], 'sha256': info['sha256']}

data = pd.DataFrame(payload['joined']['rows'], columns=payload['joined']['fields'])
data = data.loc[data.hospital_code.eq('CGH')].copy()
data['date'] = pd.to_datetime(data['date'])
data = data.sort_values('date').set_index('date')
assert not data.index.duplicated().any()
assert data.index.equals(pd.date_range('2024-01-01', '2026-09-12', name='date'))
metrics = ['ed_attendances', 'bor_ratio', 'admission_wait_p50_hours']
complete = data[metrics].notna().all(axis=1)
observed = data.loc[complete].copy()
excluded = [day.strftime('%Y-%m-%d') for day in data.index[~complete]]
assert observed[metrics].ge(0).all().all()
assert observed.ed_attendances.mod(1).eq(0).all()
assert len(observed) + len(excluded) == len(data)


def associations(frame, label):
    # Pearson correlation of average ranks is Spearman's coefficient, including ties.
    ranks = frame[metrics].rank(method='average')
    rows = []
    for feature in ['bor_ratio', 'ed_attendances']:
        assert frame[feature].nunique() > 1 and frame.admission_wait_p50_hours.nunique() > 1
        rows.append({
            'period': label, 'feature': feature, 'n_days': len(frame),
            'start': frame.index.min().strftime('%Y-%m-%d'),
            'end': frame.index.max().strftime('%Y-%m-%d'),
            'spearman': float(ranks[feature].corr(ranks.admission_wait_p50_hours)),
            'pearson': float(frame[feature].corr(frame.admission_wait_p50_hours)),
        })
    return rows


stats = associations(observed, 'all')
for year, group in observed.groupby(observed.index.year):
    stats.extend(associations(group, str(year)))
overall = {row['feature']: row for row in stats if row['period'] == 'all'}
daily = []
for day, row in observed.iterrows():
    daily.append({'date': day.strftime('%Y-%m-%d'),
                  **{metric: float(row[metric]) for metric in metrics},
                  **{key: row[key] for key in ['ed_source', 'bor_source', 'wait_source']}})
audit = {
    'hospital': 'CGH', 'sources': sources, 'study_start': '2024-01-01', 'study_end': '2026-09-12',
    'calendar_days': len(data), 'complete_common_days': len(observed),
    'excluded_dates_missing_at_least_one_metric': excluded,
    'method': 'Same-date common complete observations; Spearman via Pearson correlation of average ranks; Pearson supplementary.',
    'statistics': stats, 'daily': daily,
    'limitations': ['Descriptive hospital-day association, not patient-level causal inference.',
                    'Serial correlation and weekday, season, case-mix, and resource confounding not adjusted.',
                    'BOR is a midnight snapshot; matching recorded dates does not establish temporal causality.',
                    'No p-values, causal effects, predictive accuracy, or business improvement estimated.'],
}
(WORK / 'cgh_daily_association_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')

font_path = 'C:/Windows/Fonts/msyh.ttc'
fontManager.addfont(font_path)
plt.rcParams['font.family'] = FontProperties(fname=font_path).get_name()
plt.rcParams['axes.unicode_minus'] = False
fig, axes = plt.subplots(1, 2, figsize=(11.8, 6.4), dpi=160, sharey=True)
fig.patch.set_facecolor('white')
palette = {2024: '#376a99', 2025: '#d47c39', 2026: '#338c79'}
specs = [('bor_ratio', 100, '午夜床位占用率（%）', '床位占用率与等待'),
         ('ed_attendances', 1, '每日急诊就诊量（次）', '急诊量与等待')]
for ax, (feature, scale, xlabel, title) in zip(axes, specs):
    for year, group in observed.groupby(observed.index.year):
        ax.scatter(group[feature] * scale, group.admission_wait_p50_hours,
                   s=13, alpha=0.45, linewidths=0, color=palette[year], label=str(year))
    ax.set_title(f"{title}\nSpearman 相关系数 {overall[feature]['spearman']:.3f}",
                 fontsize=12, color='#243c4f', pad=12)
    ax.set_xlabel(xlabel, fontsize=11, labelpad=9)
    ax.set_ylim(0, observed.admission_wait_p50_hours.max() + 1.5)
    ax.grid(color='#e8edf1', linewidth=0.7)
    ax.set_axisbelow(True)
    for edge in ['top', 'right']:
        ax.spines[edge].set_visible(False)
    ax.spines['bottom'].set_color('#c8d1da')
    ax.spines['left'].set_color('#c8d1da')
    ax.tick_params(colors='#485969', labelsize=9)
axes[0].set_ylabel('每日入院等待中位数（小时）', fontsize=11, labelpad=10)
fig.text(0.055, 0.952, 'CGH：较高的床位占用率、急诊量是否伴随较长等待？',
         fontsize=18, fontweight='bold', color='#243c4f')
fig.text(0.055, 0.900, '每个点代表同一个日期的两项观测；2024-01-01 至 2026-09-12，共979个完整日。',
         fontsize=10.5, color='#566979')
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, ['2024', '2025', '2026（截至9月12日）'], loc='lower center',
           bbox_to_anchor=(0.5, 0.080), ncol=3, frameon=False, markerscale=1.6, fontsize=10)
fig.text(0.055, 0.036, '来源：MOH三项公开日指标，2026-09-20下载快照。相关不等于因果；缺失7天未填0，原记录保留。',
         fontsize=9, color='#566979')
fig.subplots_adjust(left=0.085, right=0.98, bottom=0.22, top=0.76, wspace=0.18)
plot = OUT / 'CGH_三指标日度相关_散点图.png'
fig.savefig(plot, facecolor='white')
plt.close(fig)

period_names = {'all': '全期', '2024': '2024年', '2025': '2025年', '2026': '2026年（截至09-12）'}
summary_lines = []
for period in ['all', '2024', '2025', '2026']:
    pair = {item['feature']: item for item in stats if item['period'] == period}
    b, e = pair['bor_ratio'], pair['ed_attendances']
    summary_lines.append(f"| {period_names[period]} | {b['n_days']} | {b['spearman']:.3f} | {e['spearman']:.3f} | {b['pearson']:.3f} | {e['pearson']:.3f} |")
summary_table = '\n'.join(summary_lines)
report = f'''# CGH 三指标日度相关分析

问题：在CGH同一家医院内，记录日期上床位占用率或急诊量较高的日子，入院等待日P50是否也往往较高？本步使用实际公开数据寻找关联线索，没有假定它们是等待变化的原因。

## 数据与完整性

研究范围2024-01-01至2026-09-12，共{len(data)}个自然日。两组相关都使用三指标同时非空的同一组{len(observed)}个医院日期观测，便于比较；它们不是患者样本数。2026-08-02至08-08共{len(excluded)}天缺急诊与等待记录，因此不能参与本步配对计算；原底表中的BOR记录保留，没有填0或删除原始行。2024、2025、2026分别有366、365、248个完整日。

等待为每日入院等待中位数（小时）；急诊量为每日就诊次数；BOR原始为比例，图中乘100显示百分数。日期键唯一，原三Excel的SHA-256均已核对。未拼接其他医院、未把周均值混入日度样本、未只选择五月高值周，也没有去除真实高值。

## 分析方法

主要使用Spearman秩相关：把每天的两个指标分别从小到大排序，并列值取平均名次，再计算名次间的相关。它描述两个指标是否倾向于一起升高或一个升高另一个降低，不要求这种关系由一条直线表示；排序不消除共同趋势、混杂或所有极端值影响。

系数范围为-1至1。越接近1，数值排名越倾向同向；越接近-1，越倾向反向；接近0表示没有明显的单调关联，但不能据此否定其他关系。系数不是百分比，不是每增加一个单位带来的等待小时数，也不是预测准确率。

补充Pearson作为线性关联描述；另分年份重算，检查方向和强弱是否随时期变化。这只是分层描述，不等于已控制季节、星期或病例构成。没有独立性假设下的显著性检验或因果模型。

## 结果

| 时期 | 完整日数 | BOR与等待 Spearman | 急诊量与等待 Spearman | BOR与等待 Pearson | 急诊量与等待 Pearson |
|---|---:|---:|---:|---:|---:|
{summary_table}

全期BOR与等待秩相关约{overall['bor_ratio']['spearman']:.3f}，急诊量与等待约{overall['ed_attendances']['spearman']:.3f}。这表示在本医院、此期间、此日度口径下，两者均与等待呈正向单调关联，前者的样本系数更大；不能把系数差当成“谁的因果影响更大”，也不能把0.628解释为62.8%的等待由床位占用率造成。

分年检查提供了一个实际限制：2024年BOR与等待的秩相关约0.294，急诊量与等待约0.460，强弱顺序与全期不同；2025及2026样本中BOR系数则较高。因此全期关联强弱不能作为每年都适用的固定排名，也不能据此排除2024年急诊需求的作用。分年差异的成因仍未确认。

![CGH日度散点图](CGH_三指标日度相关_散点图.png)

图中每个点对应一个医院日期，横坐标是BOR或急诊量，纵坐标是当日等待P50；颜色表示年份。点云并不落在一条线上，说明仅凭某个横轴数值无法确定当天等待。年度系数的变化应与完整散点一起检查，不只引用全期一个数字。

## 能支持什么，不能支持什么

本步支持把需求、床位相关情况作为后续核查线索，不能证明其引起等待延长。午夜BOR是存量快照，急诊量是日流量，而等待是特定急诊入院人群的日P50；记录日期对齐不证明因果先后，统计日归属和BOR分母详细范围仍需核实。也不能用这些相关系数说明五月某一周的具体原因、需要招聘多少人或增加多少床。

相邻日可能相关，星期、季节、疾病背景、病例构成和资源变化都可能影响结果；本分析尚未调整这些因素。2026年不是完整年度，分年差异也可能与覆盖季节有关。没有事件真值标签、预测划分或业务执行数据，所以不报告异常准确率、预测效果、策略采纳率或等待改善。

## 可复现与来源

脚本：`处理脚本/11_cgh_daily_association.py`；详细系数、979个日值及各自原Excel单元格、排除的7个日期和三份原件哈希保存在`处理脚本/.work_association/cgh_daily_association_audit.json`。原始文件未改动。
'''
(OUT / 'CGH_三指标日度相关分析.md').write_text(report, encoding='utf-8')
print(json.dumps({'n_days': len(observed), 'excluded_dates': excluded, 'statistics': stats,
                  'ranges': {metric: {'min': float(observed[metric].min()), 'max': float(observed[metric].max())} for metric in metrics}},
                 ensure_ascii=True, indent=2))

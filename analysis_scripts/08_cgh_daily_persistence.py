"""Describe whether CGH's selected high-wait week depends on one peak day."""
from datetime import date, timedelta
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '处理脚本'
OUT = ROOT / 'outputs/01a0bcf0-303c-7d21-9f82-aafceef76c21'
WORK = SCRIPTS / '.work_baseline'
payload = json.loads((SCRIPTS / '.work_join/hospital_metrics.json').read_text(encoding='utf-8'))
source_audit = payload['datasets']['wait']['audit']
source = ROOT / '原始数据/2026-09-20' / source_audit['file']
assert sha256(source.read_bytes()).hexdigest() == source_audit['sha256']
records = [dict(zip(payload['joined']['fields'], row)) for row in payload['joined']['rows']]
cgh = [row for row in records if row['hospital_code'] == 'CGH']
by_date = {date.fromisoformat(row['date']): row for row in cgh}
assert len(by_date) == len(cgh)
start = date(2024, 5, 2)
weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']


def observation(day):
    row = by_date[day]
    value = row['admission_wait_p50_hours']
    assert value is not None
    return {'date': day.isoformat(), 'p50_hours': value, 'source_cell': row['wait_source']}


rows = []
for offset in range(7):
    day = start + timedelta(days=offset)
    target = observation(day)
    history = [observation(day - timedelta(days=7 * weeks)) for weeks in range(8, 0, -1)]
    baseline = mean(item['p50_hours'] for item in history)
    rows.append({
        'target': target, 'weekday': weekday_names[day.weekday()],
        'previous_week': history[-1], 'prior8_same_weekday': history,
        'prior8_same_weekday_mean': baseline,
        'change_from_previous_week': target['p50_hours'] - history[-1]['p50_hours'],
        'change_from_prior8_same_weekday_mean': target['p50_hours'] - baseline,
    })

history_dates = [item['date'] for row in rows for item in row['prior8_same_weekday']]
assert len(set(history_dates)) == 56
assert min(history_dates) == '2024-03-07' and max(history_dates) == '2024-05-01'
peak = max(rows, key=lambda row: row['target']['p50_hours'])
remaining = [row for row in rows if row is not peak]
full_mean = mean(row['target']['p50_hours'] for row in rows)
six_mean = mean(row['target']['p50_hours'] for row in remaining)
six_previous = mean(row['previous_week']['p50_hours'] for row in remaining)
six_history = mean(item['p50_hours'] for row in remaining for item in row['prior8_same_weekday'])
above_previous = sum(row['change_from_previous_week'] > 0 for row in rows)
above_history = sum(row['change_from_prior8_same_weekday_mean'] > 0 for row in rows)
audit = {
    'hospital': 'CGH', 'source_file': source.name, 'source_sha256': source_audit['sha256'],
    'daily_comparisons': rows, 'full_7day_mean': full_mean,
    'days_above_previous_week': above_previous, 'days_above_prior8_same_weekday_mean': above_history,
    'peak_sensitivity_only': {
        'omitted_date': peak['target']['date'], 'omitted_value': peak['target']['p50_hours'],
        'remaining_6day_mean': six_mean, 'previous_week_matching_6day_mean': six_previous,
        'prior8_matching_weekdays_mean_48values': six_history,
    },
    'limitations': '事后描述性探索；日P50不是患者级观测；参照非临床标准；未做显著性检验或因果推断；原始高值保留。',
}
WORK.mkdir(exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
(WORK / 'cgh_daily_persistence_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
table = '\n'.join(
    f"| {r['target']['date']}（{r['weekday']}） | {r['target']['p50_hours']:.2f} | "
    f"{r['previous_week']['p50_hours']:.2f} | {r['prior8_same_weekday_mean']:.2f} | "
    f"{r['change_from_prior8_same_weekday_mean']:+.2f} |"
    for r in rows
)
report = f'''# CGH：单日尖峰还是多日偏高

本步问题：2024-05-02 至 05-08 的每日入院等待中位数均值为 {full_mean:.2f} 小时，是否只因一个最高日被拉高？所有时长单位为小时，日值均为 MOH 每日 P50，不是患者平均等待。

## 比较方法

先展开目标7天的原始日P50；每一天与前周同星期值、此前8周同星期的8个日P50的简单均值比较。此前8周范围为2024-03-07至05-01，共56个日值，均非空。这样保留了前面的多周历史参照，并按星期几对齐，避免直接把周末与工作日混在一起比较；这不能控制节假日、趋势、病例或流程变化。

例如5月2日是周四，其历史参照由3月7、14、21、28日和4月4、11、18、25日这8个周四构成，不含目标日及其后数据。8个星期参照点较少，均值本身也受高低值影响；这里只用于描述，不视为正常或安全界限。

## 日度结果

| 目标日期 | 当日P50 | 前周同星期P50 | 前8周同星期P50均值 | 与8周参照差值 |
|---|---:|---:|---:|---:|
{table}

目标周有 {above_previous}/7 天高于前周同星期值，{above_history}/7 天高于此前8周各自同星期参照均值。这里的“多日偏高”是相对所选参照，不是说每日都超过历史同星期最大值，也不是说每天都比前一天更高。日值与日值参照比较，未将历史周均值最高13.45小时直接作为日度阈值。

## 最高日对结果有多大影响

最高日为 {peak['target']['date']}，日P50为 {peak['target']['p50_hours']:.2f} 小时。仅作敏感性演示暂不计入它，其余6个日P50均值为 {six_mean:.2f} 小时；前周对应6个星期几的均值为 {six_previous:.2f} 小时，前8周对应6个星期几共48个日值的均值为 {six_history:.2f} 小时。

这说明本案例的偏高观察不只依赖29小时这一个峰值。此操作没有从原始表或正式七日指标中删除最高日，也不把6日均值称为新的七日结果；同时去除参照中的周四是为保持星期构成可比。这只是对单一高值影响的描述性检查，不是统计显著性检验。

## 可以得出的结论

目标周的7个日P50均高于所选8周同星期参照均值；即使暂不计入最高日，其余6日仍高于同星期构成的参照。因此值得调查覆盖多个日期的共同背景和入院流程变化，不能仅把这一周概括为某一天的偶发峰值。该结果仍不能证明人手不足，也不能说明每位患者、每个时段都等待更久。目标周来自事后选例，没有告警回测、临床异常判定或业务改善成效。

## 可复现与来源

实现：`处理脚本/08_cgh_daily_persistence.py`。完整日值、8个同星期历史值及原Excel单元格保存在`处理脚本/.work_baseline/cgh_daily_persistence_audit.json`。运行时核对原始等待表SHA-256、CGH日期唯一性、63天完整覆盖与非空；原文件未修改。计算用未舍入值，表格最后保留两位小数。
'''
(OUT / 'CGH_20240502至0508_每日持续性核查.md').write_text(report, encoding='utf-8')
print(json.dumps({'daily': [{
    'date': r['target']['date'], 'p50': r['target']['p50_hours'],
    'prior8_weekday_mean': r['prior8_same_weekday_mean'],
    'difference': r['change_from_prior8_same_weekday_mean'],
} for r in rows], 'peak_sensitivity': audit['peak_sensitivity_only'],
    'above_history': above_history}, ensure_ascii=True, indent=2))

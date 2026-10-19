"""Replay one fixed weekly monitoring rule; measure frequency, not accuracy."""
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '处理脚本'
OUT = ROOT / 'outputs/01a0bcf0-303c-7d21-9f82-aafceef76c21'
WORK = SCRIPTS / '.work_rule_replay'
STUDY_START = date(2024, 1, 1)
STUDY_END = date(2026, 9, 12)
BASELINE_WEEKS = 8
payload = json.loads((SCRIPTS / '.work_join/hospital_metrics.json').read_text(encoding='utf-8'))
source_audit = payload['datasets']['wait']['audit']
source = ROOT / '原始数据/2026-09-20' / source_audit['file']
assert sha256(source.read_bytes()).hexdigest() == source_audit['sha256']
records = [dict(zip(payload['joined']['fields'], row)) for row in payload['joined']['rows']]
cgh = [row for row in records if row['hospital_code'] == 'CGH']
by_date = {date.fromisoformat(row['date']): row for row in cgh}
assert len(cgh) == len(by_date)
assert all(STUDY_START + timedelta(days=i) in by_date
           for i in range((STUDY_END - STUDY_START).days + 1))

first = STUDY_START + timedelta(days=(3 - STUDY_START.weekday()) % 7)
weeks, sums = [], []
start = first
while start + timedelta(days=6) <= STUDY_END:
    daily = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        row = by_date[day]
        value = row['admission_wait_p50_hours']
        assert value is None or (Decimal(str(value)).is_finite() and value >= 0)
        daily.append({'date': day.isoformat(), 'p50_hours': value, 'source_cell': row['wait_source']})
    valid = sum(item['p50_hours'] is not None for item in daily)
    total = sum((Decimal(str(item['p50_hours'])) for item in daily), Decimal(0)) if valid == 7 else None
    sums.append(total)
    weeks.append({
        'start': start.isoformat(), 'end': (start + timedelta(days=6)).isoformat(),
        'valid_days': valid, 'daily': daily,
        'mean_daily_p50_hours': float(total / 7) if total is not None else None,
    })
    start += timedelta(days=7)

for i, week in enumerate(weeks):
    week.update({'threshold_hours': None, 'excess_hours': None, 'triggered': None,
                 'baseline_week_starts': [], 'baseline_missing_week_starts': []})
    if sums[i] is None:
        week['status'] = 'current_week_incomplete'
    elif i < BASELINE_WEEKS:
        week['status'] = 'insufficient_history'
    else:
        baseline = weeks[i - BASELINE_WEEKS:i]
        week['baseline_week_starts'] = [item['start'] for item in baseline]
        week['baseline_missing_week_starts'] = [item['start'] for item in baseline if item['valid_days'] != 7]
        if week['baseline_missing_week_starts']:
            week['status'] = 'baseline_incomplete'
        else:
            max_sum = max(sums[i - BASELINE_WEEKS:i])
            # Each sum has seven days, so comparison is equivalent to comparing means.
            # Decimal sums avoid classifying a rounding artefact as a new maximum.
            trigger = sums[i] > max_sum
            week.update({'threshold_hours': float(max_sum / 7),
                         'excess_hours': float((sums[i] - max_sum) / 7),
                         'triggered': trigger,
                         'status': 'triggered' if trigger else 'not_triggered'})

counts = Counter(week['status'] for week in weeks)
eligible = counts['triggered'] + counts['not_triggered']
alerts = [week for week in weeks if week['triggered'] is True]
groups = []
for i, week in enumerate(weeks):
    if week['triggered'] is True:
        if i == 0 or weeks[i - 1]['triggered'] is not True:
            groups.append({'start': week['start'], 'end': week['end'], 'weeks': 1})
        else:
            groups[-1]['end'] = week['end']
            groups[-1]['weeks'] += 1
assert sum(group['weeks'] for group in groups) == len(alerts)
assert sum(counts.values()) == len(weeks)
target = next(week for week in weeks if week['start'] == '2024-05-02')
assert target['triggered'] is True
after_target = next(week for week in weeks if week['start'] == '2024-05-09')
summary = {
    'total_full_calendar_weeks': len(weeks), 'status_counts': dict(counts),
    'eligible_weeks': eligible, 'triggered_weeks': len(alerts),
    'trigger_rate_among_eligible_weeks': len(alerts) / eligible,
    'consecutive_trigger_groups': groups,
    'longest_trigger_group_weeks': max((group['weeks'] for group in groups), default=0),
    'extra_weekly_triggers_within_groups': len(alerts) - len(groups),
}
audit = {
    'hospital': 'CGH', 'source_file': source.name, 'source_sha256': source_audit['sha256'],
    'parameters': {'study_start': str(STUDY_START), 'study_end': str(STUDY_END),
                   'week_start': 'Thursday', 'baseline_weeks': BASELINE_WEEKS,
                   'rule': 'current complete 7-day mean > max of previous 8 consecutive complete calendar-week means',
                   'missing_policy': 'No zero filling or skipping incomplete weeks; trigger remains null if not evaluable.'},
    'boundary_days_not_in_full_weeks': ['2024-01-01', '2024-01-02', '2024-01-03',
                                      '2026-09-10', '2026-09-11', '2026-09-12'],
    'summary': summary, 'weeks': weeks,
    'limitations': ['Retrospective snapshot, not prospective evaluation or real-time delivery.',
                    'Rule was proposed after viewing selected history; no untouched test set claimed.',
                    'No verified incident labels, hence no precision, recall, sensitivity, or false-alarm estimates.',
                    'Non-trigger does not mean normal, safe, or resolved; missingness is not recovery.',
                    'Fixed weekly cadence only; no daily rolling rule was evaluated.'],
}
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)
(WORK / 'cgh_weekly_rule_replay_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
alert_table = '\n'.join(f"| {w['start']} 至 {w['end']} | {w['mean_daily_p50_hours']:.2f} | {w['threshold_hours']:.2f} | {w['excess_hours']:+.2f} |" for w in alerts)
group_table = '\n'.join(f"| {g['start']} 至 {g['end']} | {g['weeks']} |" for g in groups)
unavailable = '\n'.join(f"| {w['start']} 至 {w['end']} | {w['status']} | {w['valid_days']} |" for w in weeks if w['triggered'] is None)
report = f'''# CGH 候选提醒规则：历史触发频率

本次只检查已经提出的一条规则，不调整窗口或阈值以追求好看的结果。该检查回答“历史上会触发多少次、是否连续触发”，不回答“提醒是否准确”或“是否改善患者体验”。

## 规则与时间边界

- 范围：2024-01-01至2026-09-12；按前课周四至周三固定、不重叠的7天窗口，每周判定一次。
- 当周7个日P50的简单均值，严格大于此前连续8个自然周相同指标的最高值时触发。实际运算不先舍入；7天求和再比较与比较7天均值等价。
- 当前及8个参照周均须每天有值。前8周用于积累历史；存在缺失则标为不能判定，不填0、不自动标为未触发，也不跳过缺失周去补更早的周。
- 完整周范围为{weeks[0]['start']}至{weeks[-1]['end']}；边界2024-01-01至01-03及2026-09-10至09-12共6天未组成完整周，不进入周回放，原记录保留。不使用研究区间之前的2023年数据补足初始基线。
- 在逐周计算中，只使用当周和此前记录，没有使用未来周设阈值。但规则在已查看部分历史后提出；这份数据快照也不能还原当时实际发布日期或修订版本，因此是探索性历史回放，不是独立测试集评估或实时告警证明。

## 实际结果

| 统计项 | 数量 |
|---|---:|
| 组成完整自然周的窗口数 | {len(weeks)} |
| 历史不足8周 | {counts['insufficient_history']} |
| 当前周日值不完整 | {counts['current_week_incomplete']} |
| 当前周完整，但8周参照含缺失 | {counts['baseline_incomplete']} |
| 可以判定的周数 | {eligible} |
| 触发周数 | {len(alerts)} |
| 可判定但未触发 | {counts['not_triggered']} |
| 触发周占可判定周比例 | {len(alerts) / eligible:.2%} |
| 连续触发区段数（仅按相邻自然周分组） | {len(groups)} |
| 最长连续触发 | {summary['longest_trigger_group_weeks']}周 |

触发比例的分母是{eligible}个可判定周，不能把历史不足或缺失的周算作“没有问题”。这里的周不是患者样本，触发比例不是异常发生率、准确率或误报率。

## 哪些周会提醒

各数值单位为小时，均指每日入院等待中位数的七日均值。

| 触发窗口 | 当周值 | 此前8周最高值 | 超出小时数 |
|---|---:|---:|---:|
{alert_table}

前课目标周2024-05-02至05-08会触发：{target['mean_daily_p50_hours']:.2f} > {target['threshold_hours']:.2f}。它已用于提出规则，不能拿“命中这一周”证明规则有效。

## 连续提醒与业务含义

| 连续触发区段 | 触发周数 |
|---|---:|
{group_table}

如果每个触发周都发一条信息，就有{len(alerts)}条周提醒；如果将相邻触发周仅在列表中归成一个待核查区段，就有{len(groups)}个区段，其中{summary['extra_weekly_triggers_within_groups']}次为同一区段内后续周再次触发。这是计数展示，未部署合并或通知策略；不能认定同一区段有同一原因，也不能认定相邻区段是不同业务事件。连续触发可能意味着情况继续变化，不能一律把后续提醒当作无用重复。

更直接的局限是：这条规则寻找“超过近期最高值”，不能单独判断持续高位是否已经解决。例如目标后下一周（{after_target['start']}至{after_target['end']}）为{after_target['mean_daily_p50_hours']:.2f}小时，阈值已变成{after_target['threshold_hours']:.2f}小时，状态为{after_target['status']}。是否恢复，仍需结合日度曲线及明确的恢复条件检查，不能从“未再次突破近期最高值”直接推断。

目前可以量化潜在复核次数，但是否过于频繁，需要了解谁负责复核、可处理多少条、每次花多少时间。公开数据没有经院方确认的事件标签，不能计算业务误报率或漏报率，也没有策略采纳或等待改善数据。

## 不能判定的周

| 窗口 | 原因代码 | 当周有效日数 |
|---|---|---:|
{unavailable}

`insufficient_history`为研究区间内历史不足8周；`current_week_incomplete`为当前周日值缺失；`baseline_incomplete`为此前连续8周含不完整周。2026年8月的数据缺口不仅影响当周，还会影响后续基线完整性；没有把这些状态当成正常或恢复。

## 可复现与复核

脚本：`处理脚本/09_cgh_weekly_rule_replay.py`；逐周值、日值及原Excel单元格、基线周范围和判定状态保存在`处理脚本/.work_rule_replay/cgh_weekly_rule_replay_audit.json`。源文件为`{source.name}`，SHA-256为`{source_audit['sha256']}`。脚本核对原件哈希、日期唯一性、完整自然日索引、周度分类总数和触发区段计数一致，原始文件未修改。
'''
(OUT / 'CGH_候选提醒规则_历史回放.md').write_text(report, encoding='utf-8')
print(json.dumps({'summary': summary,
                  'alerts': [{k: w[k] for k in ['start', 'end', 'mean_daily_p50_hours', 'threshold_hours']} for w in alerts],
                  'after_target': {k: after_target[k] for k in ['start', 'mean_daily_p50_hours', 'threshold_hours', 'status']}},
                 ensure_ascii=True, indent=2))

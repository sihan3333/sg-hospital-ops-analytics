"""Illustrate a separate follow-up condition for one selected CGH alert."""
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / '处理脚本'
OUT = ROOT / 'outputs/01a0bcf0-303c-7d21-9f82-aafceef76c21'
WORK = SCRIPTS / '.work_rule_replay'
replay = json.loads((WORK / 'cgh_weekly_rule_replay_audit.json').read_text(encoding='utf-8'))
source = ROOT / '原始数据/2026-09-20' / replay['source_file']
assert sha256(source.read_bytes()).hexdigest() == replay['source_sha256']
weeks = {item['start']: item for item in replay['weeks']}
assert len(weeks) == len(replay['weeks'])
event_start = date(2024, 5, 2)
last_start = date(2024, 6, 13)
required_weeks = 2


def exact_mean(week):
    days = week['daily']
    start = date.fromisoformat(week['start'])
    assert [day['date'] for day in days] == [(start + timedelta(days=i)).isoformat() for i in range(7)]
    values = [day['p50_hours'] for day in days]
    if any(value is None for value in values):
        return None
    return sum((Decimal(str(value)) for value in values), Decimal(0)) / 7


baseline = [weeks[(event_start - timedelta(weeks=i)).isoformat()] for i in range(8, 0, -1)]
baseline_means = [exact_mean(week) for week in baseline]
assert all(value is not None for value in baseline_means)
fixed_upper = max(baseline_means)
assert weeks[event_start.isoformat()]['triggered'] is True
labels = {
    'initial_alert': '首次提醒，开始跟踪',
    'continue_followup': '继续跟踪',
    'one_week_below': '回落观察：连续1周',
    'candidate_condition_met': '满足候选回落条件',
    'insufficient_data': '数据不足，保留跟踪',
}
streak = 0
rows = []
start = event_start
while start <= last_start:
    week = weeks[start.isoformat()]
    current = exact_mean(week)
    if start == event_start:
        assert current > fixed_upper
        status = 'initial_alert'
    elif current is None:
        streak = 0
        status = 'insufficient_data'
    elif current <= fixed_upper:
        streak += 1
        status = 'candidate_condition_met' if streak >= required_weeks else 'one_week_below'
    else:
        streak = 0
        status = 'continue_followup'
    rows.append({
        'start': week['start'], 'end': week['end'], 'daily': week['daily'],
        'mean_daily_p50_hours': float(current) if current is not None else None,
        'original_rule_triggered': week['triggered'],
        'fixed_pre_event_upper_hours': float(fixed_upper),
        'consecutive_complete_weeks_at_or_below_upper': streak,
        'status': status, 'display_status': labels[status],
    })
    if status == 'candidate_condition_met':
        break
    start += timedelta(weeks=1)

audit = {
    'type': 'Single-event retrospective teaching example; not full-period validation',
    'source_file': replay['source_file'], 'source_sha256': replay['source_sha256'],
    'event_start': str(event_start), 'baseline_start': baseline[0]['start'],
    'baseline_end': baseline[-1]['end'], 'baseline_week_means': [float(x) for x in baseline_means],
    'fixed_upper_hours': float(fixed_upper), 'required_consecutive_weeks': required_weeks,
    'comparison': '<= using unrounded weekly means',
    'missing_policy': 'Keep follow-up active, set data-insufficient, reset consecutive-week count; do not infer recovery.',
    'rows': rows,
    'limitations': ['Criterion chosen for teaching after reviewing this case.',
                    'Two weeks and historical maximum are not validated operational or clinical standards.',
                    'Meeting this condition does not mean safe, normal, or operationally resolved.',
                    'No live notifications, interventions, adoption, or effects measured.',
                    'Week-end dates do not establish when MOH published the data.'],
}
(WORK / 'cgh_followup_example_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')
table = '\n'.join(
    f"| {row['start']} 至 {row['end']} | {row['mean_daily_p50_hours']:.2f} | "
    f"{row['consecutive_complete_weeks_at_or_below_upper']} | {row['display_status']} |"
    for row in rows
)
report = f'''# CGH：首次提醒之后怎样继续跟踪

本例解释“首次发现”和“满足回落条件”是两个不同判断。仅演示2024年5月的一次已选案例，没有替换原候选提醒规则，也没有对所有提醒回放新的跟踪方案。

## 教学候选条件

1. 首次提醒仍沿用原规则：当周每日P50的七日均值高于此前8周最高周均值。
2. 开始跟踪时，保存该次提醒之前8周（2024-03-07至05-01）的最高周均值 **{fixed_upper:.2f}小时**。本段跟踪暂固定这一参照，不将高值周及后续周混入它。
3. 跟踪期间，高于固定上限就继续观察，并把连续回落计数清零；连续 **{required_weeks}个完整7日窗口**（每个均为周四至周三）的同一指标不高于这一上限，才标记“满足候选回落条件”。第一次降到上限以下时，先记“回落观察：连续1周”。
4. 当前周有缺失就标“数据不足，保留跟踪”，中断连续回落计数，不能视为恢复。本例各周均有完整7天，未发生缺失。

这不是把高值从原始表删除；只是为跟踪这一段变化，保留了触发前的参照。比较使用未舍入值，展示保留两位小数。这里的上限来自历史描述，不是等待服务目标、临床标准或安全界限；低于上限也不代表达到之前的平均水平。

“连续2周”是为了说明需要观察回落是否持续的一项教学选择。本例在查看后续数据后提出，尚未验证2周是否合适、是否拖延核查或能否减少反复，不能因为本例看起来合理就宣称参数已优化。

## 逐周演示

下列时长均为“七个每日入院等待中位数的简单平均”，不是七天所有患者的平均等待。

| 周期 | 当周指标（小时） | 连续不高于固定上限的周数 | 教学状态 |
|---|---:|---:|---|
{table}

05-16至05-22虽降至13.39小时，但下一周又回到13.90小时。如果一周低于上限就宣布结束跟踪，这次会在短暂回落时提前停止；这只是本例观察，不能据此估计所有时期的误判率。

06-06至06-12为9.38小时，06-13至06-19为9.32小时，连续两周满足候选条件。因此在后一周数据齐备可获取后，按本演示可标记“满足候选回落条件”。06-19是观察周的结束日期，不代表真实通知或实际数据发布时间。

## 看板表达与业务价值

本例将原来的“触发/未触发”扩展成一次跟踪过程中的“首次提醒、继续跟踪、观察回落、满足候选回落条件”；缺失另作数据状态。这样业务人员能区分等待下降与已经满足结束跟踪的候选条件，而不是因为没有再创新高就忽略后续变化。

这是一项跟踪设计和单案例计算结果，没有真实业务使用、处理工时、策略采纳率、患者等待改善或院方确认的事件标签。状态应显示为规则判断，不写成“恢复正常”或“问题已解决”。尚未定义重新开启跟踪、多事件合并、长期基线更新或正式恢复标准。

## 来源与复核

脚本为`处理脚本/10_cgh_followup_example.py`，输入为已核查的逐周回放记录；运行时重查原始Excel哈希，依据每周7个原始日值重新计算均值并检查完整自然日。逐日值和原始单元格、固定参照、计数及状态保存在`处理脚本/.work_rule_replay/cgh_followup_example_audit.json`。原始文件及原09周度提醒规则没有改动。
'''
(OUT / 'CGH_首次提醒与持续跟踪_教学示例.md').write_text(report, encoding='utf-8')
print(json.dumps({
    'fixed_upper_hours': float(fixed_upper),
    'rows': [{key: row[key] for key in ['start', 'end', 'mean_daily_p50_hours',
             'consecutive_complete_weeks_at_or_below_upper', 'status']} for row in rows],
}, ensure_ascii=True, indent=2))

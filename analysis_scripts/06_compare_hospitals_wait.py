"""Compare each hospital with its own preceding seven days; do not infer causes."""
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/01a0bcf0-303c-7d21-9f82-aafceef76c21'
WORK = ROOT / '处理脚本/.work_comparison'
WINDOWS = [('2024-04-25', '2024-05-01'), ('2024-05-02', '2024-05-08')]
HOSPITALS = ['CGH', 'KTPH', 'NTFGH', 'NUH(A)', 'SGH', 'SKH', 'TTSH']

payload = json.loads((ROOT / '处理脚本/.work_join/hospital_metrics.json').read_text(encoding='utf-8'))
source_audit = payload['datasets']['wait']['audit']
source = ROOT / '原始数据/2026-09-20' / source_audit['file']
assert sha256(source.read_bytes()).hexdigest() == source_audit['sha256']
data = pd.DataFrame(payload['joined']['rows'], columns=payload['joined']['fields'])
data['date'] = pd.to_datetime(data['date'])
assert not data.duplicated(['date', 'hospital_code']).any()

summary, sources = [], []
for hospital in HOSPITALS:
    series = data.loc[data.hospital_code.eq(hospital)].set_index('date').sort_index()
    values = []
    for start, end in WINDOWS:
        group = series.loc[start:end]
        assert group.index.equals(pd.date_range(start, end, name='date'))
        assert group.admission_wait_p50_hours.notna().all()
        values.append(group.admission_wait_p50_hours.tolist())
        for day, row in group.iterrows():
            sources.append({'date': day.strftime('%Y-%m-%d'), 'hospital': hospital,
                            'wait_p50_hours': float(row.admission_wait_p50_hours),
                            'source': row.wait_source})
    before, after = [sum(group) / len(group) for group in values]
    summary.append({'hospital': hospital, 'before_days': len(values[0]), 'after_days': len(values[1]),
                    'before_mean_daily_p50_hours': before, 'after_mean_daily_p50_hours': after,
                    'difference_hours': after - before,
                    'relative_change_pct': (after / before - 1) * 100 if before != 0 else None,
                    'target_days_higher_than_previous_weekday': sum(b > a for a, b in zip(*values))})

excluded = {}
for hospital, reason in [('AH', 'Urgent Care 范围与主比较的急诊不同，单列处理。'),
                         ('WH', '需检查该窗口的有效记录，不能把缺失当作零。')]:
    s = data.loc[data.hospital_code.eq(hospital)].set_index('date')
    excluded[hospital] = {'reason': reason, 'nonmissing_days': [
        int(s.loc[start:end].admission_wait_p50_hours.notna().sum()) for start, end in WINDOWS]}

increased = sum(row['difference_hours'] > 0 for row in summary)
decreased = sum(row['difference_hours'] < 0 for row in summary)
unchanged = len(summary) - increased - decreased
audit = {'windows': WINDOWS, 'source_file': str(source), 'source_sha256': source_audit['sha256'],
         'summary': summary, 'excluded': excluded, 'increased': increased, 'decreased': decreased,
         'unchanged': unchanged, 'daily_values_and_sources': sources,
         'scope': '描述性同期对照；窗口事后选取；未作因果识别或运营效率排名。'}
WORK.mkdir(parents=True, exist_ok=True)
(WORK / 'hospital_comparison_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding='utf-8')

table = '\n'.join(
    f"| {row['hospital']} | {row['before_mean_daily_p50_hours']:.2f} | {row['after_mean_daily_p50_hours']:.2f} | "
    f"{row['difference_hours']:+.2f} | {row['relative_change_pct']:+.1f}% | "
    f"{row['target_days_higher_than_previous_weekday']}/7 |"
    for row in summary
)
report = f'''# CGH 等待偏高期间：其他医院是否也有变化

问题：CGH 在 2024-05-02 至 05-08 等待偏高时，其他有完整数据的急诊医院是否也出现同方向变化？各医院均先与自己前七天 2024-04-25 至 05-01 比较。

## 方法与样本

使用已经逐项核查的三指标底表中的等待字段，本步仅分析等待。七家医院每个窗口都有 7 个非空日值，共 98 条医院日期观测，不是 98 位患者或 98 个独立样本。两个窗口各含每个星期几一次，但仍可能有节假日、病例构成或院内资源差异。

每个窗口的统计量为七个每日入院等待 P50 的简单平均，单位小时。差值 = 后期均值 − 前期均值；相对变化 = 差值 ÷ 前期均值。它们都不是所有患者合并后的平均或中位等待。NUH(A) 保留成人范围标识。

## 结果

| 医院 | 04-25 至 05-01（小时） | 05-02 至 05-08（小时） | 差值（小时） | 相对变化 | 高于前周同星期的天数 |
|---|---:|---:|---:|---:|---:|
{table}

本次七家中 {increased} 家上升、{decreased} 家下降、{unchanged} 家不变。上升和下降仅按这两个窗口均值的方向判断，未做统计显著性检验。表按固定医院顺序排列，不是医院质量或效率排名。百分比受起点大小影响，须与小时差一起看。

## 纳入边界

AH 的公开数据对应 Urgent Care，本步不与急诊主比较混用，原始记录仍保留；其两个窗口分别有 {excluded['AH']['nonmissing_days'][0]}、{excluded['AH']['nonmissing_days'][1]} 个非空值。WH 两个窗口分别有 {excluded['WH']['nonmissing_days'][0]}、{excluded['WH']['nonmissing_days'][1]} 个非空值，没有据此计算变化，未填 0。

## 能支持和不能支持的结论

同期对照可说明等待增加是否仅在 CGH 被观察到，并为进一步调查提供范围。如果多院上升，值得检查共同背景以及各院对背景变化的不同反应；仍不能认定它们具有同一个原因。若某院不升，也不能据此排除全国性因素，因为医院的患者来源、病区结构与资源情况可能不同。

这些医院不是经过匹配的因果对照组；本步不是双重差分，也没有排除医院之间的病例构成差异。目标窗口来自 CGH 事后高点探索，不能把两周方向当作长期规律或已回测的告警效果。数据仍不足以确认人员不足、决定招聘人数或评价医院管理优劣。

## 可复核来源

来源为本项目 2026-09-20 下载的 `{source.name}`，哈希与原有下载记录一致，未改原件。处理使用 `admission_wait_p50_hours`，保留每日数值和原工作表单元格位置；逐条记录及未舍入汇总存于 `处理脚本/.work_comparison/hospital_comparison_audit.json`。实现脚本为 `处理脚本/06_compare_hospitals_wait.py`。
'''
OUT.mkdir(parents=True, exist_ok=True)
(OUT / '20240502至0508_七院等待同期对照.md').write_text(report, encoding='utf-8')
print(json.dumps({key: audit[key] for key in ['summary', 'excluded', 'increased', 'decreased', 'unchanged']}, ensure_ascii=True, indent=2))

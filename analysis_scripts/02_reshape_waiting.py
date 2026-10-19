"""第二步：把医院列展开为医院日期记录；保留缺失和原始单元格位置。"""
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / '处理脚本/.work_waiting'
SOURCE = ROOT / '原始数据/2026-09-20/入院等待时间_WT_week36Y2026.xlsx'
wide = json.loads((WORK / 'waiting_data.json').read_text(encoding='utf-8'))
if sha256(SOURCE.read_bytes()).hexdigest() != wide['audit']['source_sha256']:
    raise ValueError('原始文件版本已变化，请先重新运行第一步')

hospitals = wide['headers'][1:]
df = pd.DataFrame(wide['rows'], columns=['date', *hospitals, 'source_sheet', 'source_row'])
# id_vars 是每个等待数值随身携带的信息；value_vars 是要展开的医院列。
long = df.melt(
    id_vars=['date', 'source_sheet', 'source_row'],
    value_vars=hospitals,
    var_name='hospital_code',
    value_name='admission_wait_p50_hours',
)
long = long.sort_values(['date', 'hospital_code'], kind='stable').reset_index(drop=True)
if long.duplicated(['date', 'hospital_code']).any():
    raise ValueError('日期与医院的组合重复，须先调查，不能直接合并其他指标')

source_columns = {hospital: chr(ord('B') + i) for i, hospital in enumerate(hospitals)}
long['value_status'] = long['admission_wait_p50_hours'].apply(lambda x: '原表空白' if pd.isna(x) else '原表有值')
long['source_cell'] = long.apply(lambda r: source_columns[r['hospital_code']] + str(int(r['source_row'])), axis=1)
fields = ['date', 'hospital_code', 'admission_wait_p50_hours', 'value_status', 'source_sheet', 'source_cell']
rows = [[None if pd.isna(v) else v for v in r] for r in long[fields].itertuples(index=False, name=None)]

# 将展开结果映回原来的日期和医院格子，核对数值、空值以及来源位置。
expected = {}
for row in wide['rows']:
    for i, hospital in enumerate(hospitals, 1):
        expected[(row[0], hospital)] = (row[i], row[-2], source_columns[hospital] + str(row[-1]))
assert len(rows) == len(wide['rows']) * len(hospitals) == len(expected)
for day, hospital, value, status, source_sheet, source_cell in rows:
    assert (value, source_sheet, source_cell) == expected[(day, hospital)]
    assert status == ('原表空白' if value is None else '原表有值')

audit = {
    'study_start': wide['audit']['study_start'], 'study_end': wide['audit']['study_end'],
    'source_sha256': wide['audit']['source_sha256'],
    'source_date_rows': len(wide['rows']), 'hospital_columns': len(hospitals),
    'long_rows': len(rows), 'nonblank_wait_values': int(long['admission_wait_p50_hours'].notna().sum()),
    'blank_wait_values': int(long['admission_wait_p50_hours'].isna().sum()),
    'zero_wait_values': int(long['admission_wait_p50_hours'].eq(0).sum()),
    'duplicate_date_hospital_keys': int(long.duplicated(['date', 'hospital_code']).sum()),
    'missing_whole_dates': wide['audit']['missing_dates'],
    'policy': '只改变排列方式，保留原始空白与数值0；不补原文件缺失的日期行，不增加观测。',
}
(WORK / 'waiting_long.json').write_text(json.dumps({'audit': audit, 'fields': fields, 'rows': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(audit, ensure_ascii=True, indent=2))

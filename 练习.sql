-- SQLite 练习：补全五处 __...__ 填空后保存，再运行 python run_exercise.py。
-- 任务：查询 CGH 在 2024-05-02 至 2024-05-08（含首尾）的等待有效天数与日 P50 均值。
-- 指标字段：admission_wait_p50_hours。不要把缺失值改成 0。

SELECT
    COUNT(__WAIT_FIELD__) AS valid_days,
    ROUND(AVG(__WAIT_FIELD__), 2) AS daily_p50_mean_hours
FROM hospital_metrics
WHERE hospital_code = '__HOSPITAL__'
  AND date BETWEEN '__START_DATE__' AND '__END_DATE__';

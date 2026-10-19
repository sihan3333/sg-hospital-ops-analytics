"""Run the learner's single SQLite query against the existing read-only database."""

from contextlib import closing
from pathlib import Path
import re
import sqlite3
import sys


ROOT = Path(__file__).resolve().parent
SQL_PATH = ROOT / "练习.sql"
DB_PATH = ROOT / "data" / "hospital_metrics.sqlite"
PLACEHOLDER = re.compile(r"__[A-Z][A-Z_]*__")
READ_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    sqlite3.SQLITE_RECURSIVE,
}


def allow_reads_only(action, _arg1, _arg2, _database, _trigger):
    """Reject writes, ATTACH, PRAGMA and other non-query operations."""
    return sqlite3.SQLITE_OK if action in READ_ACTIONS else sqlite3.SQLITE_DENY


def execute_readonly_query(sql, db_path=DB_PATH):
    """Return column names and rows; sqlite3.execute rejects multiple statements."""
    if not sql.strip():
        raise ValueError("练习.sql 为空，请先补全查询。")
    # Ignore comment text when looking for the learner's unfilled placeholders.
    query_text = re.sub(r"--[^\n]*|/\*.*?\*/", "", sql, flags=re.DOTALL)
    if PLACEHOLDER.search(query_text):
        raise ValueError("练习.sql 还有 __...__ 填空，请亲手补全并保存后再运行。")
    db_path = Path(db_path).resolve()
    if not db_path.is_file():
        raise ValueError("找不到 data/hospital_metrics.sqlite，请先运行 python build_data.py。")
    with closing(sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.set_authorizer(allow_reads_only)
        cursor = connection.execute(sql)
        if cursor.description is None:
            raise ValueError("请只提交一条返回结果的 SELECT 查询。")
        return [column[0] for column in cursor.description], cursor.fetchall()


def main():
    try:
        sql = SQL_PATH.read_text(encoding="utf-8-sig")
        columns, rows = execute_readonly_query(sql)
    except (OSError, ValueError, sqlite3.Error) as error:
        print(f"未执行完成：{error}", file=sys.stderr)
        return 1
    print("\t".join(columns))
    for row in rows:
        print("\t".join("NULL" if value is None else str(value) for value in row))
    print(f"返回 {len(rows)} 行。查询以只读方式运行。")
    return 0


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())

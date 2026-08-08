"""
viz/_data.py
============
One shared entry point that every visualization uses to obtain the attendance
table as a pandas DataFrame, with columns:

    date (datetime64), student_id, index_no, name,
    present (0/1), ink_colour (str, '' if absent), forged (0/1)

Resolution order:
  1. Member 6's SQLite database (data/attendance.db) once the pipeline has run.
  2. Otherwise data/output/attendance.csv (ground truth from the generator,
     or the CSV the pipeline exports), so charts are testable before the DB
     exists.

Keeping this in one place means no member re-implements data loading, and the
switch from CSV to the real database happens for everyone at once.
"""

import os
import sqlite3
import sys

import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import config  # noqa: E402


_COLUMNS = ["date", "student_id", "index_no", "name", "present", "ink_colour", "forged"]


def _from_database() -> pd.DataFrame | None:
    """Read the joined attendance view from Member 6's database, if present."""
    if not config.DATABASE_FILE.exists():
        return None
    try:
        con = sqlite3.connect(config.DATABASE_FILE)
        # Expected schema (Member 6): Students(student_id, index_no, name),
        # Attendance(date, student_id, present, ink_colour, forged).
        query = """
            SELECT a.date       AS date,
                   s.student_id AS student_id,
                   s.index_no   AS index_no,
                   s.name       AS name,
                   a.present    AS present,
                   COALESCE(a.ink_colour, '') AS ink_colour,
                   COALESCE(a.forged, 0)      AS forged
            FROM Attendance a
            JOIN Students   s ON s.student_id = a.student_id
        """
        df = pd.read_sql_query(query, con)
        con.close()
        return df if not df.empty else None
    except Exception:
        # DB exists but schema not ready yet -> fall back to CSV.
        return None


def _from_csv() -> pd.DataFrame:
    csv = config.OUTPUT_DIR / "attendance.csv"
    if not csv.exists():
        raise FileNotFoundError(
            f"No attendance data found.\n"
            f"Run:  python tools/generate_synthetic_sheets.py   (creates {csv})\n"
            f"or run the pipeline to build {config.DATABASE_FILE}."
        )
    return pd.read_csv(csv, dtype={"student_id": str, "index_no": str})


def load_attendance() -> pd.DataFrame:
    df = _from_database()
    if df is None:
        df = _from_csv()
    df = df.reindex(columns=_COLUMNS)
    df["date"] = pd.to_datetime(df["date"])
    df["present"] = df["present"].fillna(0).astype(int)
    df["forged"] = df["forged"].fillna(0).astype(int)
    df["ink_colour"] = df["ink_colour"].fillna("")
    return df.sort_values(["date", "student_id"]).reset_index(drop=True)


# --- convenience aggregations reused by several charts ----------------------
def per_session(df: pd.DataFrame) -> pd.DataFrame:
    """One row per date: present count, total, percentage."""
    g = df.groupby("date")["present"].agg(["sum", "count"]).reset_index()
    g = g.rename(columns={"sum": "present", "count": "total"})
    g["pct"] = (g["present"] / g["total"] * 100).round(1)
    return g


def per_student(df: pd.DataFrame) -> pd.DataFrame:
    """One row per student: sessions attended, total, percentage."""
    g = df.groupby(["student_id", "name"])["present"].agg(["sum", "count"]).reset_index()
    g = g.rename(columns={"sum": "attended", "count": "total"})
    g["pct"] = (g["attended"] / g["total"] * 100).round(1)
    return g.sort_values("student_id").reset_index(drop=True)


if __name__ == "__main__":
    d = load_attendance()
    print(d.head(8).to_string(index=False))
    print("\nPer session:\n", per_session(d).to_string(index=False))
    print("\nPer student:\n", per_student(d).to_string(index=False))

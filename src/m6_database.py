"""
src/m6_database.py   (Member 6 - Image Processing / DB Link)
==============================================================
SQLite controller: stores the mapped data (Member 5's info.xml roster +
per-session presence/ink-colour from Members 2-4) into a local database, so
Member 5/8's data layer (viz/_data.py) can read from a real DB instead of
the placeholder CSV. Three tables:

    Subject_Info(code PK, name, programme, faculty, university, lecturer)
    Students(student_id PK, index_no UNIQUE, name, title, row)
    Attendance(id PK, date, student_id FK, present, ink_colour, forged,
               UNIQUE(date, student_id))

DAO pattern: `Database` wraps the connection and exposes one method per
table operation; callers never write raw SQL.
"""

import os
import sqlite3
import sys
from typing import Dict, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "src", "common")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config          # noqa: E402


_SCHEMA = """
CREATE TABLE IF NOT EXISTS Subject_Info (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    programme   TEXT,
    faculty     TEXT,
    university  TEXT,
    lecturer    TEXT
);

CREATE TABLE IF NOT EXISTS Students (
    student_id  TEXT PRIMARY KEY,
    index_no    TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    title       TEXT,
    row         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS Attendance (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    student_id  TEXT NOT NULL REFERENCES Students(student_id),
    present     INTEGER NOT NULL CHECK (present IN (0, 1)),
    ink_colour  TEXT,
    forged      INTEGER NOT NULL DEFAULT 0 CHECK (forged IN (0, 1)),
    UNIQUE(date, student_id)
);
"""


class Database:
    """
    DAO wrapper around sqlite3.Connection. Use as a context manager:

        with Database() as db:
            db.upsert_student({...})
    """

    def __init__(self, path=None):
        self.path = str(path or config.DATABASE_FILE)
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        self._conn = sqlite3.connect(self.path)
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        return self._conn

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        self.close()

    # --- writes (all upserts -> idempotent) --------------------------------
    def upsert_subject(self, subject: Dict):
        self._conn.execute(
            """INSERT INTO Subject_Info (code, name, programme, faculty, university, lecturer)
               VALUES (:code, :name, :programme, :faculty, :university, :lecturer)
               ON CONFLICT(code) DO UPDATE SET
                   name=excluded.name, programme=excluded.programme,
                   faculty=excluded.faculty, university=excluded.university,
                   lecturer=excluded.lecturer""",
            subject,
        )

    def upsert_student(self, student: Dict):
        self._conn.execute(
            """INSERT INTO Students (student_id, index_no, name, title, row)
               VALUES (:id, :indexNo, :name, :title, :row)
               ON CONFLICT(student_id) DO UPDATE SET
                   index_no=excluded.index_no, name=excluded.name,
                   title=excluded.title, row=excluded.row""",
            student,
        )

    def upsert_attendance(self, date: str, student_id: str, present: bool,
                           ink_colour: Optional[str], forged: int = 0):
        self._conn.execute(
            """INSERT INTO Attendance (date, student_id, present, ink_colour, forged)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(date, student_id) DO UPDATE SET
                   present=excluded.present, ink_colour=excluded.ink_colour,
                   forged=excluded.forged""",
            (date, student_id, int(present), ink_colour, int(forged)),
        )


if __name__ == "__main__":
    with Database() as db:
        print(f"[M6] schema ready at {db.path}")

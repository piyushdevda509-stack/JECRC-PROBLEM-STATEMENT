# db_compat.py
"""
Compatibility layer so code that does `import sqlite3` or uses sqlite3.connect(...)
can instead use Postgres via psycopg2 when DATABASE_URL is present.

Usage:
- Replace `import sqlite3` in big app file with:
    import db_compat as sqlite3
  OR ensure this module is imported before sqlite3 is used.
- Set env var DATABASE_URL (postgres://...) on Render.

Note: Install psycopg2-binary in requirements.txt
"""

import os
import re
from urllib.parse import urlparse, unquote
import psycopg2
import psycopg2.extras
import sqlite3 as _sqlite3  # fallback for local dev with a real sqlite file
from contextlib import contextmanager

DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or None

# Simple Row object supporting both index and name access like sqlite3.Row
class Row(tuple):
    def __new__(cls, cols, vals):
        # store mapping of name->index
        obj = tuple.__new__(cls, vals)
        obj._cols = cols
        return obj

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                idx = self._cols.index(key)
            except ValueError:
                raise KeyError(key)
            return tuple.__getitem__(self, idx)
        else:
            return tuple.__getitem__(self, key)

    def keys(self):
        return list(self._cols)

    def asdict(self):
        return {k: self[i] for i,k in enumerate(self._cols)}

    def __repr__(self):
        return f"Row({self.asdict()})"

# Cursor wrapper to emulate sqlite3.Cursor API
class Cursor:
    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = None

    def execute(self, sql, params=None):
        # psycopg2 expects %s placeholders; assume the app uses ? or %s
        # If the SQL uses '?' placeholders, convert to %s.
        if params is None:
            params = ()
        if "?" in sql:
            sql = sql.replace("?", "%s")
        try:
            self._cur.execute(sql, params)
        except Exception:
            # re-raise with SQL for debugging
            raise
        # try to get lastrowid for INSERT ... RETURNING id
        try:
            if self._cur.description is None and self._cur.rowcount == 1:
                # If INSERT with RETURNING was used, fetchone available
                pass
        except Exception:
            pass
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        if isinstance(row, dict):
            cols = list(row.keys())
            vals = [row[c] for c in cols]
            return Row(cols, vals)
        # psycopg2 by default returns tuple, but cursor.description present
        if hasattr(self._cur, "description") and self._cur.description:
            cols = [d.name for d in self._cur.description]
            vals = list(row)
            return Row(cols, vals)
        return row

    def fetchall(self):
        rows = self._cur.fetchall()
        if rows is None:
            return []
        if not rows:
            return []
        if hasattr(self._cur, "description") and self._cur.description:
            cols = [d.name for d in self._cur.description]
            return [Row(cols, list(r)) for r in rows]
        return rows

    def fetchmany(self, size):
        rows = self._cur.fetchmany(size)
        if rows is None:
            return []
        if not rows:
            return []
        if hasattr(self._cur, "description") and self._cur.description:
            cols = [d.name for d in self._cur.description]
            return [Row(cols, list(r)) for r in rows]
        return rows

    def __iter__(self):
        for r in self.fetchall():
            yield r

    def close(self):
        try:
            self._cur.close()
        except Exception:
            pass

    def mogrify(self, *args, **kwargs):
        return self._cur.mogrify(*args, **kwargs)

# Connection wrapper to emulate sqlite3.Connection API
class Connection:
    def __init__(self, conn, is_psql=True):
        self._conn = conn
        self.row_factory = None  # match sqlite3 API
        self._is_psql = is_psql

    def cursor(self):
        if self._is_psql:
            # use dict cursor for easier access
            cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            return Cursor(cur)
        else:
            return Cursor(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def close(self):
        try:
            return self._conn.close()
        except Exception:
            pass

    def execute(self, sql, params=None):
        c = self.cursor()
        return c.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        c = self.cursor()
        # convert ? to %s if present
        if "?" in sql:
            sql = sql.replace("?", "%s")
        self._conn.cursor().executemany(sql, seq_of_params)
        return None

# Public connect(...) to mirror sqlite3.connect
def connect(db_path_or_uri, *args, **kwargs):
    """
    If DATABASE_URL is set, ignore db_path_or_uri and connect to Postgres.
    Otherwise, fallback to sqlite3.connect.
    """
    if DATABASE_URL:
        # parse DATABASE_URL, use psycopg2.connect directly
        # psycopg2 accepts the URL directly
        conn = psycopg2.connect(DATABASE_URL)
        return Connection(conn, is_psql=True)
    else:
        # fallback: use sqlite3 for local development
        conn = _sqlite3.connect(db_path_or_uri, *args, **kwargs)
        # ensure sqlite3.Row behavior works
        conn.row_factory = _sqlite3.Row
        return Connection(conn, is_psql=False)

# Make module-level names similar to sqlite3
Row = Row
OperationalError = psycopg2.OperationalError if DATABASE_URL else _sqlite3.OperationalError
IntegrityError = psycopg2.IntegrityError if DATABASE_URL else _sqlite3.IntegrityError
print("🔄 db_compat: Using", "Postgres if DATABASE_URL else SQLite3 succesfully ")
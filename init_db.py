import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "your_render_postgres_url_here")

conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode="require")
cur = conn.cursor()

# -------------------------
# Students Table
# -------------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS students (
    roll_no TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    branch TEXT,
    batch TEXT,
    dob TEXT,
    email TEXT UNIQUE,
    password TEXT,
    password_changed BOOLEAN DEFAULT FALSE
);
""")

# -------------------------
# Problems Table
# -------------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS problems (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    skill TEXT,
    category TEXT,
    branch TEXT,
    external_link TEXT,
    created_by_name TEXT,
    created_by_roll TEXT,
    created_by_branch TEXT,
    created_by_batch TEXT,
    synopsis_path TEXT,
    certificate_path TEXT,
    report_path TEXT,
    status TEXT DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rejection_reason TEXT,
    student_id TEXT
);
""")

# Add unique constraint on (title, student_id)
cur.execute("""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'problems_title_student_key'
    ) THEN
        ALTER TABLE problems
        ADD CONSTRAINT problems_title_student_key UNIQUE (title, student_id);
    END IF;
END$$;
""")

conn.commit()
cur.close()
conn.close()
print("✅ PostgreSQL Database initialized successfully!")

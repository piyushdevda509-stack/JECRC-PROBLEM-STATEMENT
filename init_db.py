import sqlite3
import os
import csv
from pathlib import Path

# -----------------------
# Paths
# -----------------------
DATABASE = Path("instance/merged_solver.db")  # Main DB
PROBLEMS_CSV = Path("problems.csv")

# Ensure instance folder exists
os.makedirs("instance", exist_ok=True)

# -----------------------
# Initialize / Migrate Database
# -----------------------
conn_main = sqlite3.connect(DATABASE)
conn_main.row_factory = sqlite3.Row
c = conn_main.cursor()

# -----------------------
# Create / Migrate Students Table
# -----------------------
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='students'")
students_table = c.fetchone()

if not students_table:
    print("⚡ Creating fresh students table...")
    c.execute("""
    CREATE TABLE students (
        roll_no TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        branch TEXT,
        batch TEXT,
        dob TEXT,                       -- Format: DDMMYYYY
        email TEXT UNIQUE,              -- 👈 Email for OTP
        password TEXT,
        password_changed INTEGER DEFAULT 0   -- 0 = not changed, 1 = changed
    )
    """)
    # Default Student
    c.execute("""
    INSERT INTO students (roll_no, name, branch, batch, dob, email, password, password_changed)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, ("24EJCAD102", "Default Student", "AIDS", "2028", "10092006",
          "piyushdevda.ai28@jecrc.ac.in", "10092006", 0))
else:
    print("ℹ️ Students table exists, checking migration...")
    # Check if password_changed column exists
    c.execute("PRAGMA table_info(students)")
    columns = [col[1] for col in c.fetchall()]

    if "password_changed" not in columns:
        print("⚡ Adding password_changed column...")
        c.execute("ALTER TABLE students ADD COLUMN password_changed INTEGER DEFAULT 0")

    # Fix wrong values if any
    c.execute("UPDATE students SET password_changed = 0 WHERE password_changed IS NULL OR password_changed NOT IN (0,1)")

# -----------------------
# Create / Reset Admin Table
# -----------------------
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='admin'")
admin_table = c.fetchone()

if not admin_table:
    print("⚡ Creating admin table...")
    c.execute("""
    CREATE TABLE admin (
        id TEXT PRIMARY KEY,
        password TEXT NOT NULL
    )
    """)
    c.execute("INSERT INTO admin (id, password) VALUES (?, ?)", ("24EJCAD102", "@Piyush1912"))

# -----------------------
# Create / Migrate Problems Table
# -----------------------
c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='problems'")
problems_table = c.fetchone()

if not problems_table:
    print("⚡ Creating problems table...")
    c.execute("""
    CREATE TABLE problems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
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
        status TEXT DEFAULT 'pending',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        rejection_reason TEXT,
        student_id TEXT  -- 👈 roll_no yaha store hoga
    )
    """)

    # Import Problems from CSV if exists
    if PROBLEMS_CSV.exists():
        with open(PROBLEMS_CSV, newline='', encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                c.execute("""
                    INSERT OR IGNORE INTO problems (
                        title, description, skill, category, branch, external_link,
                        created_by_name, created_by_roll, created_by_branch, created_by_batch,
                        status, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    row["title"], row["description"], row["skill"], row["category"], row["branch"],
                    row.get("external_link"), row["created_by_name"], row["created_by_roll"],
                    row["created_by_branch"], row["created_by_batch"], "Pending"
                ))
else:
    print("ℹ️ Problems table exists, checking migration...")
    c.execute("PRAGMA table_info(problems)")
    columns = [col[1] for col in c.fetchall()]

    if "synopsis_path" not in columns:
        print("⚡ Adding synopsis_path column...")
        c.execute("ALTER TABLE problems ADD COLUMN synopsis_path TEXT")

    if "certificate_path" not in columns:
        print("⚡ Adding certificate_path column...")
        c.execute("ALTER TABLE problems ADD COLUMN certificate_path TEXT")

    if "report_path" not in columns:
        print("⚡ Adding report_path column...")
        c.execute("ALTER TABLE problems ADD COLUMN report_path TEXT")

    if "status" not in columns:
        print("⚡ Adding status column...")
        c.execute("ALTER TABLE problems ADD COLUMN status TEXT DEFAULT 'pending'")

    if "created_at" not in columns:
        print("⚡ Adding created_at column...")
        c.execute("ALTER TABLE problems ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")

    if "rejection_reason" not in columns:
        print("⚡ Adding rejection_reason column...")
        c.execute("ALTER TABLE problems ADD COLUMN rejection_reason TEXT")

    if "student_id" not in columns:
        print("⚡ Adding student_id column...")
        c.execute("ALTER TABLE problems ADD COLUMN student_id TEXT")

# Commit and close main DB
conn_main.commit()
conn_main.close()

print("✅ Database initialized / migrated successfully with Student and Admin (24EJCAD102 / @Piyush1912)")

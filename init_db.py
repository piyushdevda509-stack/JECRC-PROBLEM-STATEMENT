import os
import csv
import psycopg2
from psycopg2.extras import RealDictCursor

# -----------------------
# Database Connection
# -----------------------
DATABASE_URL = os.getenv("DATABASE_URL")  # from Render
if not DATABASE_URL:
    raise Exception("❌ DATABASE_URL not set. Add it in Render Environment.")

conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
cur = conn.cursor()

# -----------------------
# Create Students Table
# -----------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS students (
    roll_no TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    branch TEXT,
    batch TEXT,
    dob TEXT,
    email TEXT UNIQUE,
    password TEXT,
    password_changed INTEGER DEFAULT 0
)
""")

# Insert default student if not exists
cur.execute("SELECT * FROM students WHERE roll_no = %s", ("24EJCAD102",))
if not cur.fetchone():
    cur.execute("""
        INSERT INTO students (roll_no, name, branch, batch, dob, email, password, password_changed)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, ("24EJCAD102", "Default Student", "AIDS", "2028", "10092006",
          "piyushdevda.ai28@jecrc.ac.in", "10092006", 0))

# -----------------------
# Create Admin Table
# -----------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS admin (
    id TEXT PRIMARY KEY,
    password TEXT NOT NULL
)
""")
cur.execute("SELECT * FROM admin WHERE id = %s", ("24EJCAD102",))
if not cur.fetchone():
    cur.execute("INSERT INTO admin (id, password) VALUES (%s, %s)", ("24EJCAD102", "@Piyush1912"))

# -----------------------
# Create Problems Table
# -----------------------
cur.execute("""
CREATE TABLE IF NOT EXISTS problems (
    id SERIAL PRIMARY KEY,
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rejection_reason TEXT,
    student_id TEXT
)
""")

# Import Problems from CSV if available
if os.path.exists("problems.csv"):
    with open("problems.csv", newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            cur.execute("""
                INSERT INTO problems (
                    title, description, skill, category, branch, external_link,
                    created_by_name, created_by_roll, created_by_branch, created_by_batch, status
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
            """, (
                row["title"], row["description"], row["skill"], row["category"], row["branch"],
                row.get("external_link"), row["created_by_name"], row["created_by_roll"],
                row["created_by_branch"], row["created_by_batch"], "Pending"
            ))

conn.commit()
cur.close()
conn.close()

print("✅ PostgreSQL Database initialized successfully!")

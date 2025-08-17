import sqlite3
import os
import csv

# Paths
ADMIN_DATABASE = "database.db"   # Admin DB
SOLVER_DATABASE = "instance/problem_solver.db"  # Student DB
PROBLEMS_CSV = "problems.csv"

# Ensure instance folder exists
os.makedirs("instance", exist_ok=True)

# Connect to both databases
conn_admin = sqlite3.connect(ADMIN_DATABASE)
conn_solver = sqlite3.connect(SOLVER_DATABASE)

# Enable dictionary-style row access
conn_admin.row_factory = sqlite3.Row
conn_solver.row_factory = sqlite3.Row

c_admin = conn_admin.cursor()
c_solver = conn_solver.cursor()

# -----------------------
# Create Students Table (in solver DB)
# -----------------------
c_solver.execute("""
CREATE TABLE IF NOT EXISTS students (
    roll_no TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    branch TEXT,
    batch TEXT,
    dob TEXT,
    password TEXT
)
""")

# -----------------------
# Create Admin Table (in admin DB)
# -----------------------
c_admin.execute("""
CREATE TABLE IF NOT EXISTS admin (
    id TEXT PRIMARY KEY,
    password TEXT NOT NULL
)
""")

# ✅ Ensure Default Admin Exists
c_admin.execute("SELECT COUNT(*) FROM admin")
if c_admin.fetchone()[0] == 0:
    print("⚡ Adding default admin...")
    c_admin.execute("INSERT INTO admin (id, password) VALUES (?, ?)", ("24EJCAD102", "@Piyush1912"))

# -----------------------
# Create Problems Table (in both DBs)
# -----------------------
for cursor in [c_admin, c_solver]:
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS problems (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT UNIQUE,
        description TEXT,
        skill TEXT,
        category TEXT,
        branch TEXT,
        external_link TEXT,
        created_by_name TEXT,
        created_by_roll TEXT,
        created_by_branch TEXT,
        created_by_batch TEXT
    )
    """)

# -----------------------
# Ensure Columns Exist
# -----------------------
def ensure_columns(cursor, table, columns):
    cursor.execute(f"PRAGMA table_info({table})")
    existing_cols = [row[1] for row in cursor.fetchall()]

    for col, col_type in columns.items():
        if col not in existing_cols:
            print(f"Adding missing column {col} to {table}")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")

extra_columns = {
    "skill": "TEXT",
    "category": "TEXT",
    "branch": "TEXT",
    "external_link": "TEXT",
    "created_by_name": "TEXT",
    "created_by_roll": "TEXT",
    "created_by_branch": "TEXT",
    "created_by_batch": "TEXT"
}

for cursor in [c_admin, c_solver]:
    ensure_columns(cursor, "problems", extra_columns)

# -----------------------
# Import Problems from CSV
# -----------------------
if os.path.exists(PROBLEMS_CSV):
    with open(PROBLEMS_CSV, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        problems = list(reader)

        for row in problems:
            for cursor in [c_admin, c_solver]:
                cursor.execute("""
                    INSERT OR IGNORE INTO problems (
                        title, description, skill, category, branch, external_link,
                        created_by_name, created_by_roll, created_by_branch, created_by_batch
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["title"], row["description"], row["skill"], row["category"], row["branch"],
                    row["external_link"], row["created_by_name"], row["created_by_roll"],
                    row["created_by_branch"], row["created_by_batch"]
                ))

# Commit and Close
conn_admin.commit()
conn_solver.commit()
conn_admin.close()
conn_solver.close()

print("✅ Databases initialized and problems imported successfully.")

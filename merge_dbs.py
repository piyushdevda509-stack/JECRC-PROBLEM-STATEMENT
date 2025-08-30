import sqlite3
import os
import shutil

# Paths
ADMIN_DB = "database.db"                     # Students + Admin
SOLVER_DB = "instance/problem_solver.db"     # Problems
MERGED_DB = "instance/merged_solver.db"      # Final DB

# Ensure folders exist
os.makedirs("instance", exist_ok=True)
os.makedirs("backup", exist_ok=True)

# Step 1: Backup old DBs
if os.path.exists(ADMIN_DB):
    shutil.copy(ADMIN_DB, "backup/database_backup.db")
    print("✅ Admin DB backed up")
else:
    print("⚠️ Admin DB not found, skipping backup")

if os.path.exists(SOLVER_DB):
    shutil.copy(SOLVER_DB, "backup/problem_solver_backup.db")
    print("✅ Solver DB backed up")
else:
    print("⚠️ Solver DB not found, skipping backup")

# Step 2: Start with solver DB as base
if not os.path.exists(SOLVER_DB):
    print("❌ ERROR: Solver DB does not exist. Cannot merge.")
    exit(1)

shutil.copy(SOLVER_DB, MERGED_DB)
print("✅ Solver DB copied as base for merged DB")

conn = sqlite3.connect(MERGED_DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Step 3: Ensure admin + students tables exist in merged DB
c.execute("""
CREATE TABLE IF NOT EXISTS admin (
    id TEXT PRIMARY KEY,
    password TEXT NOT NULL
)
""")
print("✅ Admin table ensured in merged DB")

c.execute("""
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
print("✅ Students table ensured in merged DB")

# Step 4: Copy admin + student data from database.db → merged DB
if os.path.exists(ADMIN_DB):
    conn_admin = sqlite3.connect(ADMIN_DB)
    conn_admin.row_factory = sqlite3.Row
    c_admin = conn_admin.cursor()

    # Copy admin
    try:
        admins = c_admin.execute("SELECT id, password FROM admin").fetchall()
        for a in admins:
            c.execute("INSERT OR IGNORE INTO admin (id, password) VALUES (?, ?)", (a["id"], a["password"]))
        print(f"✅ {len(admins)} admin(s) copied")
    except Exception as e:
        print("⚠️ Could not read admin table:", e)

    # Copy students
    try:
        students = c_admin.execute("SELECT roll_no, name, branch, batch, dob, email, password, password_changed FROM students").fetchall()
        for s in students:
            c.execute("""
            INSERT OR IGNORE INTO students 
            (roll_no, name, branch, batch, dob, email, password, password_changed)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (s["roll_no"], s["name"], s["branch"], s["batch"], s["dob"], s["email"], s["password"], s["password_changed"]))
        print(f"✅ {len(students)} student(s) copied")
    except Exception as e:
        print("⚠️ Could not read students table:", e)

    conn_admin.close()
else:
    print("⚠️ Admin DB not found, skipping copy")

# Step 5: Ensure problems table exists (base me already hai)
c.execute("""
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
    created_by_batch TEXT,
    status TEXT DEFAULT 'Pending'
)
""")
print("✅ Problems table ensured in merged DB")

# Commit & close
conn.commit()
conn.close()

print("\n🎉 Merge complete!")
print("👉 Final DB is at:", MERGED_DB)

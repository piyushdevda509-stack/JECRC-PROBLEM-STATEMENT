import sqlite3
import csv
from werkzeug.security import generate_password_hash
import os

DB_PATH = "instance/problem_solver.db"

if not os.path.exists(DB_PATH):
    raise FileNotFoundError("❌ Database not found. Run init_db.py first.")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# -------------------------------
# 1️⃣ Insert default test user
# -------------------------------
hashed_password = generate_password_hash("01012000")
cur.execute("""
INSERT OR IGNORE INTO users (name, roll_no, password)
VALUES (?, ?, ?)
""", ("Test Student", "101", hashed_password))

# -------------------------------
# 2️⃣ Load problems from CSV
# -------------------------------
if not os.path.exists("problems.csv"):
    raise FileNotFoundError("❌ problems.csv file is missing!")

with open("problems.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cur.execute("""
        INSERT OR IGNORE INTO problems (title, description, skill, category, branch, external_link)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            row.get("title", ""),
            row.get("description", ""),
            row.get("skill", ""),
            row.get("category", ""),
            row.get("branch", ""),
            row.get("external_link", "")
        ))

conn.commit()
conn.close()

print("✅ Data imported successfully! Test user created: Roll No = 101, Password = 01012000")

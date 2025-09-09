import os
import csv
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("❌ DATABASE_URL not set.")

conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
cur = conn.cursor()

# -------------------------------
# 1️⃣ Insert default test user
# -------------------------------
hashed_password = generate_password_hash("01012000")
cur.execute("SELECT * FROM students WHERE roll_no = %s", ("101",))
if not cur.fetchone():
    cur.execute("""
        INSERT INTO students (roll_no, name, password)
        VALUES (%s, %s, %s)
    """, ("101", "Test Student", hashed_password))

# -------------------------------
# 2️⃣ Load problems from CSV
# -------------------------------
if not os.path.exists("problems.csv"):
    raise FileNotFoundError("❌ problems.csv file is missing!")

with open("problems.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        cur.execute("""
            INSERT INTO problems (title, description, skill, category, branch, external_link)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            row.get("title", ""),
            row.get("description", ""),
            row.get("skill", ""),
            row.get("category", ""),
            row.get("branch", ""),
            row.get("external_link", "")
        ))

conn.commit()
cur.close()
conn.close()

print("✅ Data imported successfully! Test student created: Roll No = 101, Password = 01012000")

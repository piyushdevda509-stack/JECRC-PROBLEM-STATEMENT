import os
import csv
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv("DATABASE_URL", "your_render_postgres_url_here")

conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor, sslmode="require")
cur = conn.cursor()

# -------------------------
# Import Students
# -------------------------
if os.path.exists("students.csv"):
    with open("students.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cur.execute("""
                INSERT INTO students (roll_no, name, password, branch, batch, dob, password_changed)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (roll_no) DO NOTHING;
            """, (
                row.get("roll_no"), row.get("name"), row.get("password"),
                row.get("branch"), row.get("batch"), row.get("dob"),
                True if row.get("password_changed", "no").lower() in ("yes", "true", "1") else False
            ))

# -------------------------
# Import Problems
# -------------------------
if os.path.exists("problems.csv"):
    with open("problems.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cur.execute("""
                INSERT INTO problems (
                    title, description, skill, category, branch, external_link,
                    created_by_name, created_by_roll, created_by_branch, created_by_batch,
                    synopsis_path, certificate_path, report_path, status, created_at,
                    rejection_reason, student_id
                ) VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s
                )
                ON CONFLICT (title, student_id) DO NOTHING;
            """, (
                row.get("title"), row.get("description"), row.get("skill"), row.get("category"),
                row.get("branch"), row.get("external_link"),
                row.get("created_by_name"), row.get("created_by_roll"), row.get("created_by_branch"), row.get("created_by_batch"),
                row.get("synopsis_path"), row.get("certificate_path"), row.get("report_path"),
                row.get("status"), row.get("created_at"),
                row.get("rejection_reason"), row.get("student_id")
            ))

conn.commit()
cur.close()
conn.close()
print("✅ Students & Problems imported successfully (duplicates skipped)")

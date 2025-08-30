import sqlite3

MERGED_DB = "instance/merged_solver.db"

conn = sqlite3.connect(MERGED_DB)
cursor = conn.cursor()

# List all tables
print("📌 Tables in merged DB:")
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
for t in tables:
    print("-", t[0])

print("\n📌 Table Schemas:")
for t in tables:
    print(f"\n--- {t[0]} ---")
    schema = cursor.execute(f"PRAGMA table_info({t[0]})").fetchall()
    for col in schema:
        print(col)

conn.close()

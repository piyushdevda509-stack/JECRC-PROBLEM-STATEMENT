import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("ALTER TABLE students ADD COLUMN roll_no TEXT")
cursor.execute("ALTER TABLE students ADD COLUMN dob TEXT")

conn.commit()
conn.close()
print("✅ 'roll_no' and 'dob' columns added to 'students' table.")
import re
import shutil

# File paths
APP_FILE = "app.py"
BACKUP_FILE = "app_backup.py"

# Step 1: Backup app.py
shutil.copy(APP_FILE, BACKUP_FILE)
print(f"✅ Backup created: {BACKUP_FILE}")

# Step 2: Read file
with open(APP_FILE, "r", encoding="utf-8") as f:
    code = f.read()

# Step 3: Replace only database.db or problem_solver.db connects
pattern = r"sqlite3\.connect\((?:['\"]database\.db['\"]|['\"]instance/problem_solver\.db['\"])\)"
replaced_code = re.sub(pattern, "get_db()", code)

# Step 4: Save updated file
with open(APP_FILE, "w", encoding="utf-8") as f:
    f.write(replaced_code)

print("🎉 Replacement complete! Only database.db & problem_solver.db connects → get_db()")

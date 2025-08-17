from flask import Flask, render_template, request, redirect, url_for, session, flash, g
import sqlite3
import csv
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# -----------------------
# Paths & Config
# -----------------------
ADMIN_DATABASE = 'database.db'
PROBLEM_SOLVER_DATABASE = 'instance/problem_solver.db'
PROBLEMS_CSV = 'problems.csv'

# Default test student
DEFAULT_USER = {
    "roll_no": "24EJCAD102",
    "password": "10092006"
}

# Static admin credentials
ADMIN_USER = {
    "username": "24EJCAD102",
    "password": "@Piyush1912"
}

# -----------------------
# DB Connections
# -----------------------
def get_admin_db_connection():
    conn = sqlite3.connect(ADMIN_DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_solver_db_connection():
    conn = sqlite3.connect(PROBLEM_SOLVER_DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# g-scoped connection for admin DB
DATABASE = "database.db"

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

# -----------------------
# CSV Problem Functions
# -----------------------
def load_problems_csv():
    problems = []
    if os.path.exists(PROBLEMS_CSV):
        with open(PROBLEMS_CSV, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                problems.append(row)
    return problems

def save_problems_csv(problems):
    with open(PROBLEMS_CSV, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ["title", "description", "skill", "category", "branch",
                      "external_link", "created_by_name", "created_by_roll",
                      "created_by_branch", "created_by_batch"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(problems)

# -----------------------
# Home Page (Student Dashboard)
# -----------------------
@app.route('/')
def home():
    if 'user' in session:
        conn = get_admin_db_connection()
        problems = conn.execute("SELECT * FROM problems").fetchall()
        conn.close()
        return render_template('home.html', user=session['user'], problems=problems)
    return redirect(url_for('login'))

# -----------------------
# Student Login / Logout
# -----------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        roll_no = request.form['roll_no']
        password = request.form['password']

        # Default student
        if roll_no == DEFAULT_USER["roll_no"] and password == DEFAULT_USER["password"]:
            session['user'] = roll_no
            flash('Logged in successfully!', 'success')
            return redirect(url_for('home'))

        # From problem_solver.db
        conn = get_solver_db_connection()
        user = conn.execute('SELECT * FROM students WHERE roll_no = ?', (roll_no,)).fetchone()
        conn.close()

        if user and user['password'] == password:
            session['user'] = roll_no
            flash('Logged in successfully!', 'success')
            return redirect(url_for('home'))

        flash('Invalid Roll No or Password', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

# -----------------------
# Forget Password
# -----------------------
@app.route('/forget_password', methods=['GET', 'POST'])
def forget_password():
    if request.method == 'POST':
        roll_no = request.form['roll_no']
        dob = request.form['dob']

        if roll_no == DEFAULT_USER["roll_no"] and dob == DEFAULT_USER["password"]:
            flash(f"Your password is: {DEFAULT_USER['password']}", 'info')
        else:
            conn = get_solver_db_connection()
            user = conn.execute('SELECT * FROM students WHERE roll_no = ?', (roll_no,)).fetchone()
            conn.close()

            if user and user['dob'] == dob:
                flash(f"Your password is: {user['password']}", 'info')
            else:
                flash('Invalid details', 'danger')

    return render_template('forget_password.html')

# -----------------------
# Student Change Password
# -----------------------
@app.route("/student/change_password", methods=["GET", "POST"])
def change_password():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        # Match the field names in your HTML
        current = request.form.get("old_password", "").strip()
        new = request.form.get("new_password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        if not current or not new or not confirm:
            flash("All fields are required.", "danger")
            return render_template("change_password.html")

        conn = get_solver_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT password FROM students WHERE roll_no = ?", (session["user"],))
        student = cur.fetchone()

        if not student or student["password"] != current:
            flash("Current password is incorrect.", "danger")
        elif new != confirm:
            flash("New passwords do not match.", "danger")
        else:
            cur.execute("UPDATE students SET password = ? WHERE roll_no = ?", (new, session["user"]))
            conn.commit()
            flash("Password updated successfully!", "success")

        conn.close()

    return render_template("change_password.html")


# -----------------------
# Helpdesk
# -----------------------
@app.route('/helpdesk')
def helpdesk():
    return render_template('helpdesk.html')

# -----------------------
# Problem Details (Student View)
# -----------------------
@app.route('/problem/<int:problem_id>')
def problem_detail(problem_id):
    conn = get_admin_db_connection()
    problem = conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
    conn.close()

    if not problem:
        return "Problem not found", 404
    return render_template("problem_detail.html", problem=problem)

# -----------------------
# Admin Login
# -----------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # ✅ Use "admin" table
        cur.execute("SELECT * FROM admin WHERE id = ? AND password = ?", (username, password))
        admin = cur.fetchone()

        if admin:
            session["admin"] = admin["id"]
            flash("Login successful!", "success")
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Invalid Admin ID or Password", "danger")

    return render_template("admin_login.html")


# -----------------------
# Admin Dashboard
# -----------------------
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))

    conn = get_solver_db_connection()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()

    conn2 = get_admin_db_connection()
    problems = conn2.execute("SELECT * FROM problems").fetchall()
    conn2.close()

    return render_template("admin_dashboard.html", students=students, problems=problems)

# -----------------------
# Admin - Manage Students
# -----------------------
@app.route("/admin/students")
def admin_students():
    if 'admin' not in session:
        return redirect(url_for('admin_login'))
    conn = get_solver_db_connection()
    students = conn.execute("SELECT * FROM students").fetchall()
    conn.close()
    return render_template("admin_students.html", students=students)

@app.route("/admin/students/add", methods=["GET", "POST"])
def admin_add_student():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        roll_no = request.form["roll_no"]
        name = request.form["name"]
        branch = request.form["branch"]
        batch = request.form["batch"]
        dob = request.form["dob"]
        password = request.form["password"]

        conn = get_solver_db_connection()
        try:
            conn.execute(
                "INSERT INTO students (roll_no, name, branch, batch, dob, password) VALUES (?, ?, ?, ?, ?, ?)",
                (roll_no, name, branch, batch, dob, password)
            )
            conn.commit()
            flash("Student added successfully!", "success")
        except sqlite3.IntegrityError:
            flash("Roll number already exists!", "danger")
        finally:
            conn.close()

        return redirect(url_for("admin_students"))

    return render_template("add_student.html")

@app.route("/admin/students/edit/<roll_no>", methods=["GET", "POST"])
def admin_edit_student(roll_no):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_solver_db_connection()
    student = conn.execute("SELECT * FROM students WHERE roll_no = ?", (roll_no,)).fetchone()

    if not student:
        conn.close()
        flash("Student not found!", "danger")
        return redirect(url_for("admin_students"))

    if request.method == "POST":
        name = request.form["name"]
        branch = request.form["branch"]
        batch = request.form["batch"]
        dob = request.form["dob"]
        password = request.form.get("password")

        if password and password.strip():
            conn.execute(
                "UPDATE students SET name=?, branch=?, batch=?, dob=?, password=? WHERE roll_no=?",
                (name, branch, batch, dob, password, roll_no),
            )
        else:
            conn.execute(
                "UPDATE students SET name=?, branch=?, batch=?, dob=? WHERE roll_no=?",
                (name, branch, batch, dob, roll_no),
            )

        conn.commit()
        conn.close()
        flash("Student updated successfully!", "success")
        return redirect(url_for("admin_students"))

    conn.close()
    return render_template("admin_edit_student.html", student=student)

@app.route("/admin/students/delete/<roll_no>")
def admin_delete_student(roll_no):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_solver_db_connection()
    conn.execute("DELETE FROM students WHERE roll_no = ?", (roll_no,))
    conn.commit()
    conn.close()

    flash("Student deleted successfully!", "success")
    return redirect(url_for("admin_students"))

# -----------------------
# Admin - Change Student Password
# -----------------------
@app.route('/change_student_password', methods=['GET', 'POST'])
def change_student_password():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    if request.method == 'POST':
        roll_no = request.form['roll_no']
        new_password = request.form['new_password']

        conn = get_solver_db_connection()
        conn.execute("UPDATE students SET password = ? WHERE roll_no = ?", (new_password, roll_no))
        conn.commit()
        conn.close()

        flash("Password updated successfully!", "success")
        return redirect(url_for('admin_dashboard'))

    return render_template('change_student_password.html')

# -----------------------
# Admin - Manage Problems
# -----------------------
@app.route("/admin/problems")
def admin_problems():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_admin_db_connection()
    problems = conn.execute("SELECT * FROM problems").fetchall()
    conn.close()

    return render_template("admin_problems.html", problems=problems)

@app.route("/admin/problems/add", methods=["GET", "POST"])
def admin_add_problem():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        skill = request.form["skill"]
        category = request.form["category"]
        branch = request.form["branch"]
        external_link = request.form.get("external_link")
        created_by_name = request.form.get("created_by_name")
        created_by_roll = request.form.get("created_by_roll")
        created_by_branch = request.form.get("created_by_branch")
        created_by_batch = request.form.get("created_by_batch")

        conn = get_admin_db_connection()
        conn.execute("""
            INSERT INTO problems 
            (title, description, skill, category, branch, external_link, created_by_name, created_by_roll, created_by_branch, created_by_batch)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, description, skill, category, branch, external_link,
              created_by_name, created_by_roll, created_by_branch, created_by_batch))
        conn.commit()
        conn.close()

        flash("✅ Problem added successfully!", "success")
        return redirect(url_for("admin_problems"))

    return render_template("add_problem.html")

@app.route("/admin/problems/edit/<int:problem_id>", methods=["GET", "POST"])
def admin_edit_problem(problem_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_admin_db_connection()
    problem = conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()

    if not problem:
        conn.close()
        return "Problem not found", 404

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        skill = request.form["skill"]
        category = request.form["category"]
        branch = request.form["branch"]
        external_link = request.form.get("external_link")
        created_by_name = request.form.get("created_by_name")
        created_by_roll = request.form.get("created_by_roll")
        created_by_branch = request.form.get("created_by_branch")
        created_by_batch = request.form.get("created_by_batch")

        conn.execute("""
            UPDATE problems 
            SET title=?, description=?, skill=?, category=?, branch=?, external_link=?, 
                created_by_name=?, created_by_roll=?, created_by_branch=?, created_by_batch=? 
            WHERE id=?
        """, (title, description, skill, category, branch, external_link,
              created_by_name, created_by_roll, created_by_branch, created_by_batch, problem_id))
        conn.commit()
        conn.close()

        flash("✅ Problem updated successfully!", "success")
        return redirect(url_for("admin_problems"))

    conn.close()
    return render_template("admin_edit_problem.html", problem=problem)

@app.route("/admin/problems/delete/<int:problem_id>")
def admin_delete_problem(problem_id):
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    conn = get_admin_db_connection()
    problem = conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()

    if not problem:
        conn.close()
        return "Problem not found", 404

    conn.execute("DELETE FROM problems WHERE id = ?", (problem_id,))
    conn.commit()
    conn.close()

    flash("🗑️ Problem deleted successfully!", "danger")
    return redirect(url_for("admin_problems"))

# -----------------------
# Admin Change Password
# -----------------------
@app.route("/admin/change_password", methods=["GET", "POST"])
def admin_change_password():
    if "admin" not in session:
        flash("Please login first", "danger")
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        old_password = request.form["old_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        conn = get_db()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # ✅ Use "admin" table
        cur.execute("SELECT password FROM admin WHERE id = ?", (session["admin"],))
        admin = cur.fetchone()

        if not admin:
            flash(f"Admin account not found for ID: {session['admin']}", "danger")
            return redirect(url_for("admin_change_password"))

        if admin["password"] != old_password:
            flash("Old password is incorrect", "danger")
            return redirect(url_for("admin_change_password"))

        if new_password != confirm_password:
            flash("New passwords do not match", "danger")
            return redirect(url_for("admin_change_password"))

        cur.execute("UPDATE admin SET password = ? WHERE id = ?", (new_password, session["admin"]))
        conn.commit()
        conn.close()

        flash("Password updated successfully", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_change_password.html")


# -----------------------
# Run App
# -----------------------
if __name__ == '__main__':
    app.run(debug=True)

# app.py
import os
import csv
import datetime as dt
import sqlite3
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, send_from_directory, abort
)
from werkzeug.security import generate_password_hash
import smtplib,random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
# -----------------------------------------------------------------------------
# Paths & Flask Config
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DB_PATH = INSTANCE_DIR / "merged_solver.db"
UPLOADS_DIR = BASE_DIR / "uploads"      # where we save user files
CSV_PATH = BASE_DIR / "problems.csv"    # CSV mirror of problems

# Ensure dirs exist
INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = "change_me_please"   # change in production

# Upload folder config
app.config["UPLOAD_FOLDER"] = str(UPLOADS_DIR)

# Allowed extensions
ALLOWED_DOC = {".pdf"}
ALLOWED_IMG = {".pdf", ".jpg", ".jpeg", ".png"}

# -----------------------------------------------------------------------------
# Serve Uploaded Files (Direct View)
# -----------------------------------------------------------------------------
@app.route("/uploads/<path:relpath>")
def serve_upload(relpath):
    """
    Serve files from uploads folder.
    Example: http://127.0.0.1:5000/uploads/problem_7/file.pdf
    """
    return send_from_directory(app.config["UPLOAD_FOLDER"], relpath, as_attachment=False)


# -----------------------------------------------------------------------------
# DB helpers
# -----------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema():
    """
    Creates tables if missing and adds any new columns required by newer code.
    Prevents 'no such column' or BuildError from templates linking to routes.
    """
    conn = get_db()
    cur = conn.cursor()

    # Students
    cur.execute("""
        CREATE TABLE IF NOT EXISTS students (
            roll_no TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            branch TEXT,
            batch TEXT,
            dob TEXT,
            email TEXT UNIQUE,
            password TEXT,
            password_changed TEXT DEFAULT 'no'
        )
    """)

    # Admin
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    """)

    # Problems (create base)
    cur.execute("""
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
            status TEXT DEFAULT 'pending'
        )
    """)

    # Add missing columns safely
    cur.execute("PRAGMA table_info(problems)")
    cols = {r["name"] for r in cur.fetchall()}

    def add_col(name, sqltype):
        cur.execute(f"ALTER TABLE problems ADD COLUMN {name} {sqltype}")

    if "created_at" not in cols:
        add_col("created_at", "TEXT")
    if "synopsis_path" not in cols:
        add_col("synopsis_path", "TEXT")
    if "certificate_path" not in cols:
        add_col("certificate_path", "TEXT")
    if "report_path" not in cols:
        add_col("report_path", "TEXT")

    conn.commit()


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------
def require_student():
    return "user" in session


def require_admin():
    return "admin" in session


def _ext(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def allowed_file(filename: str, kind: str) -> bool:
    ext = _ext(filename)
    if kind == "doc":
        return ext in ALLOWED_DOC
    if kind == "img":
        return ext in ALLOWED_IMG
    return False

def save_upload(file_storage, subdir: str) -> str:
    """
    Save file as uploads/<subdir>/<secure_filename>, return relative path
    e.g. 'problem_12/my.pdf'. This rel path is stored in DB and used by /uploads/<path>.
    """
    filename = secure_filename(file_storage.filename)
    target_dir = UPLOADS_DIR / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    filepath = target_dir / filename
    file_storage.save(filepath)
    # return relative path WITHOUT "uploads/"
    return f"{subdir}/{filename}"




def now_iso_utc():
    return dt.datetime.now(dt.timezone.utc).isoformat()


# -----------------------------------------------------------------------------
# CSV sync (problems -> problems.csv)
# -----------------------------------------------------------------------------
def update_csv_from_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM problems ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        header = [
            "id", "title", "description", "skill", "category", "branch", "external_link",
            "created_by_name", "created_by_roll", "created_by_branch", "created_by_batch",
            "status", "created_at", "synopsis_path", "certificate_path", "report_path"
        ]
        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)
        return

    fieldnames = rows[0].keys()  # keep whatever columns exist
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(dict(r))





# -----------------------------------------------------------------------------
# Auth: Student
# -----------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        roll_no = request.form.get("roll_no", "").strip()
        password = request.form.get("password", "").strip()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE roll_no=? AND password=?", (roll_no, password))
        student = cur.fetchone()
        conn.close()
        if student:
            session["user"] = student["roll_no"]
            session["student_name"] = student["name"]
            flash("Logged in successfully.", "success")
            return redirect(url_for("home"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("login"))

# -----------------------------------------------------------------------------
# Auth: Admin
# -----------------------------------------------------------------------------
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin WHERE id=? AND password=?", (username, password))
        admin = cur.fetchone()
        conn.close()

        if admin:
            session.clear()  
            session["admin"] = admin["id"]   # ✅ template 
            flash("Admin logged in.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "danger")
    return render_template("admin_login.html")


def require_admin():
    return "admin" in session   # ✅base.html 


@app.route("/admin/dashboard")
def admin_dashboard():
    if not require_admin():
        return redirect(url_for("admin_login"))
    return render_template("admin_dashboard.html")


@app.route("/admin/change_password", methods=["GET", "POST"])
def admin_change_password():
    if not require_admin():
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        old_pw = request.form.get("old_password", "").strip()
        new_pw = request.form.get("new_password", "").strip()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM admin WHERE id=? AND password=?", (session["admin"], old_pw))
        admin = cur.fetchone()

        if not admin:
            conn.close()
            flash("Old password incorrect.", "danger")
            return redirect(url_for("admin_change_password"))

        cur.execute("UPDATE admin SET password=? WHERE id=?", (new_pw, session["admin"]))
        conn.commit()
        conn.close()
        flash("Password updated successfully!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_change_password.html")






# -----------------------------------------------------------------------------
# Public/Student pages
# -----------------------------------------------------------------------------
@app.route("/")
def home():
    if not require_student():
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM problems WHERE status='approved' ORDER BY id DESC")
    problems = cur.fetchall()
    conn.close()
    return render_template("home.html", problems=problems)


@app.route("/problem/<int:problem_id>")
def problem_detail(problem_id):
    if not require_student():
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM problems WHERE id=?", (problem_id,))
    problem = cur.fetchone()
    conn.close()
    if not problem:
        abort(404)
    return render_template("problem_detail.html", problem=problem)


# -----------------------------------------------------------------------------
# Student: add / my problems
# -----------------------------------------------------------------------------
import sqlite3

def get_problem_by_id(problem_id):
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM problems WHERE id=?", (problem_id,))
    problem = cur.fetchone()
    conn.close()
    return problem

def update_problem(problem_id, form_data):
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("""
        UPDATE problems
        SET title=?, description=?, skill=?, category=?, branch=?, external_link=?
        WHERE id=?
    """, (
        form_data["title"],
        form_data["description"],
        form_data["skill"],
        form_data["category"],
        form_data["branch"],
        form_data["external_link"],
        problem_id
    ))
    conn.commit()
    conn.close()
def get_db_connection():
    conn = sqlite3.connect("database.db")   # <-- your database filename
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/student/add_problem", methods=["GET", "POST"])
def student_add_problem():
    if not require_student():
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE roll_no=?", (session["user"],))
    s = cur.fetchone()
    if not s:
        conn.close()
        session.clear()
        flash("Student not found. Please login again.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        skill = request.form.get("skill", "").strip()
        category = request.form.get("category", "").strip()
        branch = request.form.get("branch", "").strip()
        external_link = request.form.get("external_link", "").strip() or None

        synopsis = request.files.get("synopsis")
        certificate = request.files.get("certificate")
        report = request.files.get("report")

        if not title or not description or not skill or not category or not branch:
            flash("All fields are required.", "danger")
            conn.close()
            return redirect(url_for("student_add_problem"))

        # 🔥 yaha student_id bhi insert kar diya
        cur.execute("""
            INSERT INTO problems
                (title, description, skill, category, branch, external_link,
                 created_by_name, created_by_roll, created_by_branch, created_by_batch,
                 status, created_at, student_id)
            VALUES (?,?,?,?,?,?,?,?,?,?, 'pending', ?, ?)
        """, (title, description, skill, category, branch, external_link,
              s["name"], s["roll_no"], s["branch"], s["batch"],
              now_iso_utc(), s["roll_no"]))   # 👈 student_id = roll_no
        conn.commit()

        # new id
        cur.execute("SELECT last_insert_rowid() AS id")
        pid = cur.fetchone()["id"]
        subdir = f"problem_{pid}"

        syn_path = cert_path = rep_path = None

        if synopsis and synopsis.filename:
            if allowed_file(synopsis.filename, "doc"):
                syn_path = save_upload(synopsis, subdir)
            else:
                flash("Synopsis must be a PDF.", "danger")

        if certificate and certificate.filename:
            if allowed_file(certificate.filename, "img"):
                cert_path = save_upload(certificate, subdir)
            else:
                flash("Certificate must be an image/PDF.", "danger")

        if report and report.filename:
            if allowed_file(report.filename, "doc"):
                rep_path = save_upload(report, subdir)
            else:
                flash("Report must be a PDF.", "danger")

        cur.execute("""
            UPDATE problems
            SET synopsis_path=?, certificate_path=?, report_path=?
            WHERE id=?
        """, (syn_path, cert_path, rep_path, pid))
        conn.commit()
        conn.close()

        update_csv_from_db()
        flash("Problem submitted! Waiting for admin approval.", "success")
        return redirect(url_for("student_problems"))

    # GET
    student_branch = s["branch"]
    student_batch = s["batch"]
    conn.close()
    return render_template("student_add_problem.html",
                           student_branch=student_branch,
                           student_batch=student_batch)


@app.route("/student_problems")
def student_problems():
    if not require_student():
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM problems WHERE created_by_roll=? ORDER BY id DESC",
                (session["user"],))
    my = cur.fetchall()
    cur.execute("""
        SELECT * FROM problems
        WHERE created_by_roll != ? AND status='approved'
        ORDER BY id DESC
    """, (session["user"],))
    others = cur.fetchall()
    conn.close()
    return render_template("student_problems.html", my_problems=my, other_problems=others)

# -----------------------
# Student Edit Problem
# -----------------------
import os
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = "static/uploads"

@app.route("/student/edit_problem/<int:pid>", methods=["GET", "POST"])
def student_edit_problem(pid):
    if not require_student():
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM problems WHERE id=? AND created_by_roll=?", (pid, session["user"]))
    problem = cur.fetchone()

    if not problem:
        conn.close()
        flash("Problem not found or not yours.", "danger")
        return redirect(url_for("student_problems"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        skill = request.form.get("skill", "").strip()
        category = request.form.get("category", "").strip()
        branch = request.form.get("branch", "").strip()
        external_link = request.form.get("external_link", "").strip() or None

        # file handling
        synopsis_file = request.files.get("synopsis")
        certificate_file = request.files.get("certificate")
        report_file = request.files.get("report")

        synopsis_path = problem["synopsis_path"]
        certificate_path = problem["certificate_path"]
        report_path = problem["report_path"]

        subdir = f"problem_{pid}"
        os.makedirs(os.path.join(UPLOAD_FOLDER, subdir), exist_ok=True)

        if synopsis_file and synopsis_file.filename:
            if allowed_file(synopsis_file.filename, "doc"):
                filename = secure_filename(synopsis_file.filename)
                synopsis_path = f"uploads/{subdir}/{filename}"
                synopsis_file.save(os.path.join("static", synopsis_path))
            else:
                flash("Synopsis must be a PDF.", "danger")

        if certificate_file and certificate_file.filename:
            if allowed_file(certificate_file.filename, "img"):
                filename = secure_filename(certificate_file.filename)
                certificate_path = f"uploads/{subdir}/{filename}"
                certificate_file.save(os.path.join("static", certificate_path))
            else:
                flash("Certificate must be an image/PDF.", "danger")

        if report_file and report_file.filename:
            if allowed_file(report_file.filename, "doc"):
                filename = secure_filename(report_file.filename)
                report_path = f"uploads/{subdir}/{filename}"
                report_file.save(os.path.join("static", report_path))
            else:
                flash("Report must be a PDF.", "danger")

        cur.execute("""
            UPDATE problems
            SET title=?, description=?, skill=?, category=?, branch=?, external_link=?,
                synopsis_path=?, certificate_path=?, report_path=?, status='pending'
            WHERE id=? AND created_by_roll=?
        """, (title, description, skill, category, branch, external_link,
              synopsis_path, certificate_path, report_path, pid, session["user"]))
        conn.commit()
        conn.close()

        flash("Problem updated & resubmitted for approval.", "success")
        return redirect(url_for("student_problems"))

    conn.close()
    return render_template("student_edit_problem.html", problem=problem)





# ---------------------------------------------------------------------------
# Admin: List / Approve / Reject / Delete / Edit / Add Problems
# ---------------------------------------------------------------------------

@app.route("/admin/problems")
def admin_problems():
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    # Ensure rows are returned as dictionaries
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM problems ORDER BY id DESC")
    problems = cur.fetchall()
    conn.close()

    return render_template("admin_problems.html", problems=problems)


@app.route("/admin/problems/approve/<int:problem_id>")
def admin_approve_problem(problem_id):
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    cur = conn.cursor()
    # Ensure status is lowercase to match template logic
    cur.execute("UPDATE problems SET status='approved' WHERE id=?", (problem_id,))
    conn.commit()
    conn.close()

    update_csv_from_db()
    flash("✔ Problem approved.", "success")
    return redirect(url_for("admin_problems"))




@app.route("/admin/problems/reject/<int:problem_id>", methods=["GET", "POST"])
def admin_reject_problem(problem_id):
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    cur = conn.cursor()

    # Get problem info
    cur.execute("SELECT * FROM problems WHERE id=?", (problem_id,))
    problem = cur.fetchone()

    if not problem:
        conn.close()
        abort(404)

    if request.method == "POST":
        reason = request.form.get("reason", "").strip()
        cur.execute(
            "UPDATE problems SET status='rejected', rejection_reason=? WHERE id=?",
            (reason, problem_id)
        )
        conn.commit()
        conn.close()
        update_csv_from_db()
        flash("❌ Problem rejected with reason.", "warning")
        return redirect(url_for("admin_problems"))

    conn.close()
    return render_template("admin_reject_problem.html", problem=problem)



@app.route("/admin/problems/delete/<int:problem_id>")
def admin_delete_problem(problem_id):
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT synopsis_path, certificate_path, report_path FROM problems WHERE id=?", (problem_id,))
    row = cur.fetchone()

    # Delete uploaded files if they exist
    if row:
        for rel in (row["synopsis_path"], row["certificate_path"], row["report_path"]):
            if rel:
                p = UPLOADS_DIR / rel
                if p.exists():
                    try:
                        p.unlink()
                    except Exception:
                        pass
                # Remove folder if empty
                try:
                    (UPLOADS_DIR / rel.split("/")[0]).rmdir()
                except Exception:
                    pass
        cur.execute("DELETE FROM problems WHERE id=?", (problem_id,))
        conn.commit()

    conn.close()
    update_csv_from_db()
    flash("🗑 Problem deleted.", "danger")
    return redirect(url_for("admin_problems"))


@app.route("/admin/problems/edit/<int:problem_id>", methods=["GET", "POST"])
def admin_edit_problem(problem_id):
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        skill = request.form.get("skill", "").strip()
        category = request.form.get("category", "").strip()
        branch = request.form.get("branch", "").strip()
        external_link = request.form.get("external_link", "").strip() or None

        cur.execute("""
            UPDATE problems
            SET title=?, description=?, skill=?, category=?, branch=?, external_link=?
            WHERE id=?
        """, (title, description, skill, category, branch, external_link, problem_id))
        conn.commit()
        conn.close()

        update_csv_from_db()
        flash("💾 Problem updated.", "success")
        return redirect(url_for("admin_problems"))

    cur.execute("SELECT * FROM problems WHERE id=?", (problem_id,))
    problem = cur.fetchone()
    conn.close()
    if not problem:
        abort(404)
    return render_template("admin_edit_problem.html", problem=problem)

@app.route("/admin/problems")
def admin_problems_panel():  # <-- changed function name
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM problems ORDER BY id DESC")
    problems = cur.fetchall()
    conn.close()

    return render_template("admin_problems.html", problems=problems)


# -----------------------------------------------------------------------------
# Admin: add problem    

@app.route("/admin/add_problem", methods=["GET", "POST"])
def admin_add_problem():
    if not require_admin():
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        skill = request.form.get("skill", "").strip()
        category = request.form.get("category", "").strip()
        branch = request.form.get("branch", "").strip()
        external_link = request.form.get("external_link", "").strip() or None

        if not title or not description or not skill or not category or not branch:
            flash("All fields are required.", "danger")
            return redirect(url_for("admin_add_problem"))

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO problems
                (title, description, skill, category, branch, external_link,
                 created_by_name, created_by_roll, created_by_branch, created_by_batch,
                 status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?, 'approved', ?)
        """, (title, description, skill, category, branch, external_link,
              "Admin", "ADMIN", "-", "-", now_iso_utc()))
        conn.commit()
        conn.close()
        update_csv_from_db()
        flash("✅ Problem added.", "success")
        return redirect(url_for("admin_problems"))

    return render_template("problem_form.html", problem=None)


# -----------------------------------------------------------------------------
# Password management (student + admin) and helpdesk/forget
# -----------------------------------------------------------------------------
@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if not require_student():
        return redirect(url_for("login"))
    if request.method == "POST":
        old = request.form.get("old_password", "")
        new = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if new != confirm:
            flash("New password and confirmation do not match.", "danger")
            return redirect(url_for("change_password"))

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM students WHERE roll_no=?", (session["user"],))
        s = cur.fetchone()
        if not s or s["password"] != old:
            conn.close()
            flash("Old password incorrect.", "danger")
            return redirect(url_for("change_password"))

        cur.execute("UPDATE students SET password=?, password_changed='yes' WHERE roll_no=?",
                    (new, session["user"]))
        conn.commit()
        conn.close()
        flash("Password changed.", "success")
        return redirect(url_for("home"))
    return render_template("change_password.html")

#-----------------------------------------------------------------------------
# forget password
#-----------------------------------------------------------------------------
# ------------------ FORGET PASSWORD ROUTE ------------------
@app.route("/student/forget_password", methods=["GET", "POST"])
def forget_password():
    if request.method == "POST":
        roll_no = request.form["roll_no"].strip()
        dob = request.form["dob"].strip()

        # Fetch student data from DB
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM students WHERE roll_no = ? AND dob = ?", (roll_no, dob))
        student = cursor.fetchone()
        conn.close()

        if student:
            email = student[0]
            otp = str(random.randint(100000, 999999))  # 6-digit OTP

            # Store OTP in session for verification
            session["otp"] = otp
            session["roll_no"] = roll_no

            # Send OTP via email
            send_email(email, "Password Reset OTP", f"Your OTP is {otp}")

            flash("✅ OTP has been sent to your registered email.", "success")
            return redirect(url_for("verify_otp"))  # 👈 verify_otp route hona chahiye
        else:
            flash("❌ Invalid Roll No or DOB!", "danger")
            return redirect(url_for("forget_password"))

    return render_template("forget_password.html")


#-----------------------------------------------------------------------------
# OTP Verification
#-----------------------------------------------------------------------------
@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        otp_entered = request.form['otp']

        # check session me otp hai kya
        if 'otp' not in session or 'roll_no' not in session:
            flash("Session expired, please try again.", "danger")
            return redirect(url_for('forget_password'))

        if otp_entered == session['otp']:
            # OTP sahi hai → reset password page
            return redirect(url_for('reset_password'))
        else:
            flash("Invalid OTP. Please try again.", "danger")
            return redirect(url_for('verify_otp'))

    return render_template("verify_otp.html")
#-----------------------------------------------------------------------------
# Reset Password
#-----------------------------------------------------------------------------
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('reset_password'))

        if 'roll_no' not in session:
            flash("Session expired, please try again.", "danger")
            return redirect(url_for('forget_password'))

        roll_no = session['roll_no']

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()

        # update password in DB
        cursor.execute("UPDATE students SET password = ? WHERE roll_no = ?", (new_password, roll_no))
        conn.commit()
        conn.close()

        # clear otp/session data
        session.pop('otp', None)
        session.pop('roll_no', None)

        flash("Password reset successfully! Please login with your new password.", "success")
        return redirect(url_for('login'))

    return render_template("reset_password.html")
#-----------------------------------------------------------------------------
# sENDING EMAIL
#-----------------------------------------------------------------------------
def send_email(to, subject, body):
    sender = "your_email@gmail.com"       # 👈 apna Gmail ID
    password = "xxxx xxxx xxxx xxxx"      # 👈 Gmail App Password (16 characters)

    try:
        # Create email
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Gmail SMTP
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, password)    # 👈 login with App Password
        server.sendmail(sender, to, msg.as_string())
        server.quit()
        print(f"✅ Email sent successfully to {to}")

    except Exception as e:
        print(f"❌ Error sending email: {e}")
# -----------------------------------------------------------------------------
# Helpdesk
#------------------------------------------------------------------------------
@app.route("/helpdesk")
def helpdesk():
    return render_template("helpdesk.html")


# -----------------------------------------------------------------------------
# Public page: approved problems table (used by admin menu too)
# -----------------------------------------------------------------------------
# ----------------------- #
# Admin: View Single Problem
# ----------------------- #
@app.route("/admin/problem/<int:problem_id>")
def admin_view_problem(problem_id):
    # Admin authentication check
    if "admin" not in session:
        flash("Please login as admin to continue.", "danger")
        return redirect(url_for("admin_login"))

    conn = get_db()
    conn.row_factory = sqlite3.Row   # ✅ important for dict-like access
    cur = conn.cursor()

    # Fetch the problem by ID
    cur.execute("SELECT * FROM problems WHERE id = ?", (problem_id,))
    problem = cur.fetchone()
    conn.close()

    if not problem:
        flash(f"Problem with ID {problem_id} not found.", "danger")
        return redirect(url_for("admin_problems"))

    return render_template("admin_view_problem.html", problem=problem)


#------------
# ADMIN CHNAGE STUDENT PASSWORD 
#------------

@app.route("/admin/change_student_password", methods=["GET", "POST"])
def change_student_password():
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        roll_no = request.form["roll_no"]
        new_password = request.form["new_password"]

        conn = get_db()
        conn.execute(
            "UPDATE students SET password=? WHERE roll_no=?",
            (generate_password_hash(new_password), roll_no)
        )
        conn.commit()
        conn.close()

        flash("Password updated successfully!", "success")
        return redirect(url_for("admin_students"))

    return render_template("change_student_password.html")


#--------------------------------------------------------------------------------
# Problem view
#--------------------------------------------------------------------------------

@app.route("/problems")
def problems():
    conn = get_db()
    problems = conn.execute("SELECT * FROM problems WHERE status='approved'").fetchall()
    conn.close()
    return render_template("problems.html", problems=problems)


# -----------------------------------------------------------------------------
# ADMIN : MANAGE STUDENT DETAILS
# -----------------------------------------------------------------------------

@app.route("/admin/students")
def admin_students():
    if not require_admin():
        return redirect(url_for("admin_login"))
    conn = get_db()
    students = conn.execute("SELECT * FROM students ORDER BY roll_no").fetchall()
    conn.close()
    return render_template("admin_students.html", students=students)


@app.route("/admin/add_student", methods=["GET", "POST"])
def admin_add_student():
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        roll_no = request.form["roll_no"].strip()
        name = request.form["name"].strip()
        branch = request.form["branch"].strip()
        batch = request.form["batch"].strip()
        dob = request.form["dob"].strip()
        password = request.form["password"].strip()
        email = request.form["email"]

        try:
            cur.execute("""
                INSERT INTO students (roll_no, name, branch, batch, dob, password, email)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (roll_no, name, branch, batch, dob, password))
            conn.commit()
            flash("✅ Student added successfully!", "success")
        except sqlite3.IntegrityError:
            flash("❌ Roll No already exists!", "danger")

        return redirect(url_for("admin_students"))

    # GET → fetch all students for table display
    students = cur.execute("SELECT * FROM students ORDER BY roll_no").fetchall()
    conn.close()
    return render_template("add_student.html", students=students)


@app.route("/admin/edit_student/<roll_no>", methods=["GET", "POST"])
def admin_edit_student(roll_no):
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name").strip()
        password = request.form.get("password").strip()
        cur.execute("UPDATE students SET name=?, password=? WHERE roll_no=?",
                    (name, password, roll_no))
        conn.commit()
        conn.close()
        flash("✅ Student updated successfully!", "success")
        return redirect(url_for("admin_students"))

    cur.execute("SELECT * FROM students WHERE roll_no=?", (roll_no,))
    student = cur.fetchone()
    conn.close()
    if not student:
        flash("❌ Student not found!", "danger")
        return redirect(url_for("admin_students"))
    return render_template("admin_edit_student.html", student=student)


@app.route("/admin/delete_student/<roll_no>", methods=["POST", "GET"])
def admin_delete_student(roll_no):
    if not require_admin():
        return redirect(url_for("admin_login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM students WHERE roll_no=?", (roll_no,))
    conn.commit()
    conn.close()
    flash("🗑 Student deleted successfully!", "success")
    return redirect(url_for("admin_students"))


# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)

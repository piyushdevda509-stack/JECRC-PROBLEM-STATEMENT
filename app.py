# app.py
import os
import csv
import datetime as dt
import db_compat as sqlite3
import psycopg2
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, send_from_directory, abort
)
from werkzeug.security import generate_password_hash
import smtplib,random
from email.mime.text import MIMEText
from email.utils import formataddr
import sys
import db_compat
sys.modules['sqlite3'] = db_compat
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
    cur.execute("""
        SELECT id, title, description, skill, category, branch, external_link,
               created_by_name, created_by_roll, created_by_branch, created_by_batch,
               synopsis_path, certificate_path, report_path, status, created_at,
               rejection_reason, student_id
        FROM problems ORDER BY id ASC
    """)
    rows = cur.fetchall()
    conn.close()

    fieldnames = [
        "id", "title", "description", "skill", "category", "branch", "external_link",
        "created_by_name", "created_by_roll", "created_by_branch", "created_by_batch",
        "synopsis_path", "certificate_path", "report_path", "status", "created_at",
        "rejection_reason", "student_id"
    ]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(dict(r))

# ----------------------------------------------------------------------------- 
# CSV sync (students -> students.csv)
# ----------------------------------------------------------------------------- 
def update_students_csv():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT roll_no, name, branch, batch, dob, email FROM students ORDER BY roll_no ASC")
    rows = cur.fetchall()
    conn.close()

    if not rows:
        header = ["roll_no", "name", "branch", "batch", "dob", "email"]
        with open("students.csv", "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(header)
        return

    fieldnames = rows[0].keys()
    with open("students.csv", "w", newline="", encoding="utf-8") as f:
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

@app.route("/student/profile")
def student_profile():
    if not require_student():
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM students WHERE roll_no=?", (session["user"],))
    student = cur.fetchone()
    conn.close()
    return render_template("student_profile.html", student=student)


# -----------------------------------------------------------------------------
# Student: add / my problems
# -----------------------------------------------------------------------------
import sqlite3

def get_problem_by_id(problem_id):
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM problems WHERE id=?", (problem_id,))
    problem = cur.fetchone()
    conn.close()
    return problem

def update_problem(problem_id, form_data):
    conn = get_db()
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
    conn = get_db()   # <-- your database filename
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
        pid = cur.lastrowid  # For SQLite
# For PostgreSQL, use RETURNING id in the INSERT statement
        if pid is None:
            cur.execute("SELECT id FROM problems WHERE title=?", (title,))
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

        if synopsis_file and synopsis_file.filename:
            if allowed_file(synopsis_file.filename, "doc"):
                synopsis_path = save_upload(synopsis_file, subdir)
            else:
                flash("Synopsis must be a PDF.", "danger")

        if certificate_file and certificate_file.filename:
            if allowed_file(certificate_file.filename, "img"):
                certificate_path = save_upload(certificate_file, subdir)
            else:
                flash("Certificate must be an image/PDF.", "danger")

        if report_file and report_file.filename:
            if allowed_file(report_file.filename, "doc"):
                report_path = save_upload(report_file, subdir)
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
    flash("Problem Approved!", "success")
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
        branch = request.form.get("branch", "").strip()  # Problem branch
        external_link = request.form.get("external_link", "").strip() or None

        # Creator details
        created_by_name = request.form.get("created_by_name", "").strip()
        created_by_roll = request.form.get("created_by_roll", "").strip()
        created_by_branch = request.form.get("created_by_branch", "").strip()
        created_by_batch = request.form.get("created_by_batch", "").strip()

        # Validation
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
        """, (
            title, description, skill, category, branch, external_link,
            created_by_name, created_by_roll, created_by_branch, created_by_batch,
            now_iso_utc()
        ))
        conn.commit()
        conn.close()

        # Sync CSV
        update_csv_from_db()

        flash("✅ Problem added.", "success")
        return redirect(url_for("admin_problems"))

    # Show form + existing problems
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM problems ORDER BY id DESC")
    problems = cur.fetchall()
    conn.close()

    return render_template("add_problem.html", problems=problems, problem=None)



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
def now_iso_utc():
    return dt.datetime.utcnow().isoformat(timespec="seconds") + "Z"

@app.route("/student/forget_password", methods=["GET", "POST"])
def forget_password():
    if request.method == "POST":
        roll_no = request.form.get("roll_no", "").strip()
        dob = request.form.get("dob", "").strip()

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT email FROM students WHERE roll_no = ? AND dob = ?", (roll_no, dob))
        row = cur.fetchone()
        conn.close()

        if not row:
            flash("❌ Invalid Roll No or DOB!", "danger")
            return redirect(url_for("forget_password"))

        email = row["email"]
        otp = f"{random.randint(100000, 999999)}"  # 6-digit

        # store OTP + expiry (5 min) in session
        session["otp"] = otp
        session["otp_exp"] = (dt.datetime.utcnow() + dt.timedelta(minutes=5)).isoformat()
        session["roll_no"] = roll_no

        ok = send_email(
            email,
            "JECRC Password Reset OTP",
            f"Your OTP is: {otp}\nThis OTP will expire in 5 minutes.\nRequested at {now_iso_utc()}."
        )

        if not ok:
            flash("❌ Could not send OTP email. Contact support.", "danger")
            return redirect(url_for("forget_password"))

        flash("✅ OTP sent to your registered email.", "success")
        return redirect(url_for("verify_otp"))

    return render_template("forget_password.html")

#-----------------------------------------------------------------------------
# OTP Verification
#-----------------------------------------------------------------------------
@app.route("/verify_otp", methods=["GET", "POST"])
def verify_otp():
    if request.method == "POST":
        otp_entered = request.form.get("otp", "").strip()
        if "otp" not in session or "roll_no" not in session:
            flash("Session expired, please try again.", "danger")
            return redirect(url_for("forget_password"))

        # expiry check
        try:
            exp = dt.datetime.fromisoformat(session.get("otp_exp").replace("Z",""))
        except Exception:
            exp = dt.datetime.utcnow() - dt.timedelta(seconds=1)

        if dt.datetime.utcnow() > exp:
            flash("OTP expired. Please request a new one.", "warning")
            session.pop("otp", None)
            session.pop("otp_exp", None)
            return redirect(url_for("forget_password"))

        if otp_entered == session["otp"]:
            # success → allow reset
            return redirect(url_for("reset_password"))
        else:
            flash("Invalid OTP. Please try again.", "danger")
            return redirect(url_for("verify_otp"))

    return render_template("verify_otp.html")

#-----------------------------------------------------------------------------
# Reset Password
#-----------------------------------------------------------------------------
@app.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if "roll_no" not in session:
        flash("Unauthorized. Please start again.", "danger")
        return redirect(url_for("forget_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()
        if not new_password or new_password != confirm:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("reset_password"))

        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE students SET password=?, password_changed=1 WHERE roll_no=?",
                    (new_password, session["roll_no"]))
        conn.commit()
        conn.close()

        # cleanup
        session.pop("otp", None)
        session.pop("otp_exp", None)
        session.pop("roll_no", None)

        flash("✅ Password reset successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")

#-----------------------------------------------------------------------------
# SENDING EMAIL
#-----------------------------------------------------------------------------
def send_email(to, subject, body):
    user = os.getenv("SMTP_USER")
    app_pw = os.getenv("SMTP_PASS")
    from_name = os.getenv("SMTP_FROM_NAME", "JECRC OTP")

    if not user or not app_pw:
        print("❌ Email not configured: set SMTP_USER and SMTP_PASS env vars.")
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((from_name, user))
    msg["To"] = to

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as s:
            s.ehlo()
            s.starttls()
            s.login(user, app_pw)
            s.sendmail(user, [to], msg.as_string())
        print(f"✅ Email sent to {to}")
        return True
    except Exception as e:
        print("❌ Error sending email:", e)
        return False

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
        name = request.form.get("name").strip().upper()  # Convert to uppercase
        roll_no = request.form.get("roll_no").strip().upper()  # Convert to uppercase
        branch = request.form["branch"]
        batch = request.form["batch"]
        dob = request.form["dob"]
        email = request.form["email"].strip().lower()
        mobile = request.form.get("mobile", "").strip()
        password = request.form["password"]
        try:
            cur.execute("""
                INSERT INTO students (roll_no, name, branch, batch, dob, email, mobile, password)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (roll_no, name, branch, batch, dob, email, mobile, password))
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
        branch = request.form.get("branch").strip()
        batch = request.form.get("batch").strip()
        dob = request.form.get("dob").strip()
        email = request.form.get("email").strip()  # Retrieve the email from the form
        mobile = request.form.get("mobile", "").strip()
        password = request.form.get("password").strip()

        # This is the corrected UPDATE statement that includes the email field.
        cur.execute("UPDATE students SET name=?, branch=?, batch=?, dob=?, email=?, mobile=?, password=? WHERE roll_no=?",
                    (name, branch, batch, dob, email, mobile, password, roll_no))
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
    
    # Returning a dictionary to render_template for easier access in the template.
    student_dict = {
        'name': student[1],
        'roll_no': student[0],
        'branch': student[2],
        'batch': student[3],
        'dob': student[4],
        
        'email': student[5],
        'mobile': student[6],
        'password': student[7],
    }

    return render_template("admin_edit_student.html", student=student_dict)


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

#--------------------------------------------------------------------------------
# Update CSV from DB    
#--------------------------------------------------------------------------------
import csv

def export_students_to_csv():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT roll_no, name, branch, batch, dob, email FROM students")
    rows = cur.fetchall()
    conn.close()

    with open("students.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Roll No", "Name", "Branch", "Batch", "DOB", "Email"])  # header
        for r in rows:
            writer.writerow([r["roll_no"], r["name"], r["branch"], r["batch"], r["dob"], r["email"]])


def export_problems_to_csv():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""SELECT id, title, description, skill, category, branch,
                          external_link, created_by_name, created_by_roll,
                          created_by_branch, created_by_batch, status
                   FROM problems""")
    rows = cur.fetchall()
    conn.close()

    with open("problems.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "ID","Title","Description","Skill","Category","Branch","Link",
            "Created By Name","Created By Roll","Created By Branch","Created By Batch","Status"
        ])
        for r in rows:
            writer.writerow([
                r["id"], r["title"], r["description"], r["skill"], r["category"],
                r["branch"], r["external_link"], r["created_by_name"], r["created_by_roll"],
                r["created_by_branch"], r["created_by_batch"], r["status"]
            ])
# ...existing code...

def get_db_connection():
    """
    Connects to PostgreSQL if a DATABASE_URL environment variable is set,
    otherwise connects to the local SQLite database.
    """
    db_url = os.environ.get('DATABASE_URL')
    
    if db_url:
        # Connect to PostgreSQL using the URL provided by Render
        try:
            conn = psycopg2.connect(db_url)
            return conn
        except Exception as e:
            print(f"Error connecting to PostgreSQL: {e}")
            return None
    else:
        # Connect to the local SQLite database for development
        try:
            conn = sqlite3.connect('instance/merged_solver.db')
            conn.row_factory = sqlite3.Row 
            return conn
        except Exception as e:
            print(f"Error connecting to SQLite: {e}")
            return None

# ...existing code...
# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)

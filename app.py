import os
from functools import wraps

import mysql.connector
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from mysql.connector import Error
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import Config


ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt", "zip", "png", "jpg", "jpeg"}

app = Flask(__name__)
app.config.from_object(Config)
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


def get_db_connection():
    return mysql.connector.connect(
        host=app.config["MYSQL_HOST"],
        user=app.config["MYSQL_USER"],
        password=app.config["MYSQL_PASSWORD"],
        database=app.config["MYSQL_DATABASE"],
    )


def query_db(query, params=None, fetchone=False, commit=False):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(query, params or ())
        if commit:
            connection.commit()
            return cursor.lastrowid
        result = cursor.fetchone() if fetchone else cursor.fetchall()
        return result
    finally:
        cursor.close()
        connection.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login first.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def instructor_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get("role") not in {"instructor", "admin"}:
            flash("Only instructors can access that page.", "danger")
            return redirect(url_for("dashboard"))
        return view(*args, **kwargs)

    return wrapped_view


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")

        if not name or not username or not email or not password:
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if role not in {"student", "instructor"}:
            role = "student"

        existing_user = query_db(
            "SELECT id FROM users WHERE email = %s OR username = %s",
            (email, username),
            fetchone=True,
        )
        if existing_user:
            flash("An account with that email or username already exists.", "danger")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        query_db(
            """
            INSERT INTO users (name, username, email, password_hash, role)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (name, username, email, password_hash, role),
            commit=True,
        )
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        login_id = request.form.get("login_id", "").strip().lower()
        password = request.form.get("password", "")
        user = query_db(
            "SELECT * FROM users WHERE email = %s OR username = %s",
            (login_id, login_id),
            fetchone=True,
        )

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        flash("Welcome back.", "success")
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        login_id = request.form.get("login_id", "").strip().lower()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not login_id or not new_password or not confirm_password:
            flash("All fields are required.", "danger")
            return render_template("forgot_password.html")

        if new_password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("forgot_password.html")

        user = query_db(
            "SELECT id FROM users WHERE email = %s OR username = %s",
            (login_id, login_id),
            fetchone=True,
        )
        if not user:
            flash("No account found with that username or email.", "danger")
            return render_template("forgot_password.html")

        query_db(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (generate_password_hash(new_password), user["id"]),
            commit=True,
        )
        flash("Password reset successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    if session.get("role") == "student":
        courses = query_db(
            """
            SELECT c.*, u.name AS instructor_name,
                CASE WHEN e.id IS NULL THEN 0 ELSE 1 END AS is_selected
            FROM courses c
            LEFT JOIN users u ON c.instructor_id = u.id
            LEFT JOIN course_enrollments e
                ON e.course_id = c.id AND e.student_id = %s
            ORDER BY c.created_at DESC
            """,
            (session["user_id"],),
        )
        notes = query_db(
            """
            SELECT n.*, c.title AS course_title
            FROM module_notes n
            JOIN courses c ON n.course_id = c.id
            JOIN course_enrollments e ON e.course_id = c.id
            WHERE e.student_id = %s
            ORDER BY n.created_at DESC
            LIMIT 5
            """,
            (session["user_id"],),
        )
    else:
        courses = query_db(
            """
            SELECT c.*, u.name AS instructor_name
            FROM courses c
            LEFT JOIN users u ON c.instructor_id = u.id
            ORDER BY c.created_at DESC
            """
        )
        notes = query_db(
            """
            SELECT n.*, c.title AS course_title
            FROM module_notes n
            JOIN courses c ON n.course_id = c.id
            WHERE n.instructor_id = %s
            ORDER BY n.created_at DESC
            LIMIT 5
            """,
            (session["user_id"],),
        )
    return render_template("dashboard.html", courses=courses, notes=notes)


@app.route("/courses/select/<int:course_id>", methods=["POST"])
@login_required
def select_course(course_id):
    if session.get("role") != "student":
        flash("Only students can select courses.", "danger")
        return redirect(url_for("dashboard"))

    query_db(
        """
        INSERT IGNORE INTO course_enrollments (student_id, course_id)
        VALUES (%s, %s)
        """,
        (session["user_id"], course_id),
        commit=True,
    )
    flash("Course selected successfully.", "success")
    return redirect(url_for("dashboard"))


@app.route("/courses/remove/<int:course_id>", methods=["POST"])
@login_required
def remove_course(course_id):
    if session.get("role") != "student":
        flash("Only students can remove selected courses.", "danger")
        return redirect(url_for("dashboard"))

    query_db(
        "DELETE FROM course_enrollments WHERE student_id = %s AND course_id = %s",
        (session["user_id"], course_id),
        commit=True,
    )
    flash("Course removed from your list.", "info")
    return redirect(url_for("dashboard"))


@app.route("/courses/add", methods=["GET", "POST"])
@login_required
@instructor_required
def add_course():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not title:
            flash("Course title is required.", "danger")
            return render_template("add_course.html")

        query_db(
            """
            INSERT INTO courses (title, description, instructor_id)
            VALUES (%s, %s, %s)
            """,
            (title, description, session["user_id"]),
            commit=True,
        )
        flash("Course added successfully.", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_course.html")


@app.route("/assignments", methods=["GET", "POST"])
@login_required
def assignments():
    if session.get("role") == "student":
        courses = query_db(
            """
            SELECT c.id, c.title
            FROM courses c
            JOIN course_enrollments e ON e.course_id = c.id
            WHERE e.student_id = %s
            ORDER BY c.title
            """,
            (session["user_id"],),
        )
    else:
        courses = query_db("SELECT id, title FROM courses ORDER BY title")

    if request.method == "POST":
        course_id = request.form.get("course_id")
        title = request.form.get("title", "").strip()
        file = request.files.get("assignment_file")

        if not course_id or not title or not file:
            flash("Course, title, and file are required.", "danger")
            return render_template("assignments.html", courses=courses, submissions=[])

        if file.filename == "" or not allowed_file(file.filename):
            flash("Please upload an allowed file type.", "danger")
            return render_template("assignments.html", courses=courses, submissions=[])

        safe_name = secure_filename(file.filename)
        stored_name = f"{session['user_id']}_{course_id}_{safe_name}"
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], stored_name))

        query_db(
            """
            INSERT INTO assignments (course_id, student_id, title, file_name)
            VALUES (%s, %s, %s, %s)
            """,
            (course_id, session["user_id"], title, stored_name),
            commit=True,
        )
        flash("Assignment uploaded successfully.", "success")
        return redirect(url_for("assignments"))

    if session.get("role") == "student":
        submissions = query_db(
            """
            SELECT a.*, c.title AS course_title
            FROM assignments a
            JOIN courses c ON a.course_id = c.id
            WHERE a.student_id = %s
            ORDER BY a.uploaded_at DESC
            """,
            (session["user_id"],),
        )
    else:
        submissions = query_db(
            """
            SELECT a.*, c.title AS course_title, u.name AS student_name
            FROM assignments a
            JOIN courses c ON a.course_id = c.id
            JOIN users u ON a.student_id = u.id
            ORDER BY a.uploaded_at DESC
            """
        )

    return render_template("assignments.html", courses=courses, submissions=submissions)


@app.route("/notes")
@login_required
def notes():
    if session.get("role") == "student":
        notes_list = query_db(
            """
            SELECT n.*, c.title AS course_title, u.name AS instructor_name
            FROM module_notes n
            JOIN courses c ON n.course_id = c.id
            JOIN users u ON n.instructor_id = u.id
            JOIN course_enrollments e ON e.course_id = c.id
            WHERE e.student_id = %s
            ORDER BY n.created_at DESC
            """,
            (session["user_id"],),
        )
    else:
        notes_list = query_db(
            """
            SELECT n.*, c.title AS course_title
            FROM module_notes n
            JOIN courses c ON n.course_id = c.id
            WHERE n.instructor_id = %s
            ORDER BY n.created_at DESC
            """,
            (session["user_id"],),
        )

    return render_template("notes.html", notes=notes_list)


@app.route("/notes/add", methods=["GET", "POST"])
@login_required
@instructor_required
def add_note():
    courses = query_db(
        "SELECT id, title FROM courses WHERE instructor_id = %s ORDER BY title",
        (session["user_id"],),
    )

    if request.method == "POST":
        course_id = request.form.get("course_id")
        module_title = request.form.get("module_title", "").strip()
        content = request.form.get("content", "").strip()

        if not course_id or not module_title or not content:
            flash("Course, module title, and notes are required.", "danger")
            return render_template("add_note.html", courses=courses)

        query_db(
            """
            INSERT INTO module_notes (course_id, instructor_id, module_title, content)
            VALUES (%s, %s, %s, %s)
            """,
            (course_id, session["user_id"], module_title, content),
            commit=True,
        )
        flash("Module notes added successfully.", "success")
        return redirect(url_for("notes"))

    return render_template("add_note.html", courses=courses)


@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename, as_attachment=True)


@app.route("/results")
@login_required
def results():
    if session.get("role") == "student":
        marks = query_db(
            """
            SELECT m.*, c.title AS course_title
            FROM marks m
            JOIN courses c ON m.course_id = c.id
            WHERE m.student_id = %s
            ORDER BY c.title
            """,
            (session["user_id"],),
        )
    else:
        marks = query_db(
            """
            SELECT m.*, c.title AS course_title, u.name AS student_name
            FROM marks m
            JOIN courses c ON m.course_id = c.id
            JOIN users u ON m.student_id = u.id
            ORDER BY c.title, u.name
            """
        )

    return render_template("results.html", marks=marks)


@app.route("/marks/add", methods=["GET", "POST"])
@login_required
@instructor_required
def add_marks():
    courses = query_db("SELECT id, title FROM courses ORDER BY title")
    students = query_db("SELECT id, name, email FROM users WHERE role = 'student' ORDER BY name")

    if request.method == "POST":
        course_id = request.form.get("course_id")
        student_id = request.form.get("student_id")
        marks = request.form.get("marks")
        total_marks = request.form.get("total_marks")
        remarks = request.form.get("remarks", "").strip()

        if not course_id or not student_id or not marks or not total_marks:
            flash("Course, student, marks, and total marks are required.", "danger")
            return render_template("add_marks.html", courses=courses, students=students)

        query_db(
            """
            INSERT INTO marks (course_id, student_id, marks, total_marks, remarks)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                marks = VALUES(marks),
                total_marks = VALUES(total_marks),
                remarks = VALUES(remarks)
            """,
            (course_id, student_id, marks, total_marks, remarks),
            commit=True,
        )
        flash("Marks saved successfully.", "success")
        return redirect(url_for("results"))

    return render_template("add_marks.html", courses=courses, students=students)


@app.errorhandler(Error)
def handle_database_error(error):
    return render_template("error.html", message=f"Database error: {error}"), 500


if __name__ == "__main__":
    app.run(debug=True)

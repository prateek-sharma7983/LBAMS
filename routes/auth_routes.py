from sqlalchemy.exc import SQLAlchemyError
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from models import Admin, Student, Teacher, User, db, generate_student_code


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    login_email = normalize_email(request.args.get("email", ""))
    selected_teacher_email = login_email

    if current_user.is_authenticated:
        if login_email:
            logout_user()
            flash("Please enter the selected teacher password to continue.", "info")
        else:
            return redirect_by_role(current_user.role)

    if request.method == "POST":
        selected_teacher_email = normalize_email(request.form.get("selected_teacher_email", ""))
        email = selected_teacher_email or normalize_email(request.form.get("email", ""))
        password = request.form.get("password", "")

        user = authenticate_by_email(email, password)
        if selected_teacher_email and (not user or user.role != "teacher" or user.username != selected_teacher_email):
            print(
                "DEBUG: Teacher quick login failed "
                f"for selected_teacher_email={selected_teacher_email}, submitted_email={request.form.get('email', '')}"
            )
            flash("Invalid teacher credentials for the selected account.", "danger")
            login_email = selected_teacher_email
        elif user:
            # Role-based login validation
            expected_role = request.args.get("for_role")

            # Teacher login context from home page link
            if not expected_role and normalize_email(request.args.get("email", "")):
                expected_role = "teacher"

            # Default to student for general login page
            if not expected_role:
                expected_role = "student"

            if user.role != expected_role:
                flash(
                    f"Incorrect account type. This login is for {expected_role} accounts only.",
                    "danger",
                )
                preserved_args = {k: v for k, v in request.args.items() if k in ['for_role', 'email']}
                return redirect(url_for("auth.login", **preserved_args))

            login_user(user)
            flash("Login successful.", "success")

            next_page = request.args.get("next")
            if next_page:
                return redirect(next_page)
            return redirect_by_role(user.role)
        else:
            print(f"DEBUG: Login failed for email={email}")
            flash("Invalid Credentials", "danger")
            login_email = email

    return render_template(
        "auth/login.html",
        login_email=login_email,
        selected_teacher_email=selected_teacher_email,
    )


@auth_bp.route("/register/student", methods=["GET", "POST"])
def register_student():
    if current_user.is_authenticated:
        return redirect_by_role(current_user.role)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = normalize_email(request.form.get("email", ""))
        semester = request.form.get("semester", type=int)
        password = request.form.get("password", "")

        if not full_name or not email or not password or semester is None:
            flash("All fields are required.", "danger")
            return redirect(url_for("auth.register_student"))

        if User.query.filter_by(username=email).first() or Student.query.filter_by(email=email).first():
            flash("Email already exists.", "danger")
            return redirect(url_for("auth.register_student"))

        try:
            user = User(username=email, role="student")
            user.password_hash = generate_password_hash(password)
            db.session.add(user)
            db.session.flush()

            student = Student(
                user_id=user.id,
                student_code=generate_student_code(),
                full_name=full_name,
                email=email,
                semester=semester,
            )
            db.session.add(student)
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            print(f"DEBUG: Student registration failed for email={email}: {exc}")
            flash("Registration failed.", "danger")
            return redirect(url_for("auth.register_student"))

        flash(f"Registration successful. Student ID: {student.student_code}", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register_student.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("main.home"))


def redirect_by_role(role):
    if role == "admin":
        return redirect(url_for("admin.dashboard"))
    if role == "teacher":
        return redirect(url_for("teacher.dashboard"))
    return redirect(url_for("student.dashboard"))


def normalize_email(value):
    return value.strip().lower()


def authenticate_by_email(email, password):
    admin = (
        db.session.query(Admin, User)
        .join(User, Admin.user_id == User.id)
        .filter(User.username == email)
        .first()
    )
    if admin:
        _admin_record, user = admin
        if user.role == "admin" and user.password_hash and check_password_hash(user.password_hash, password):
            return user
        print(f"DEBUG: Admin password mismatch for email={email}")

    teacher = (
        db.session.query(Teacher, User)
        .join(User, Teacher.user_id == User.id)
        .filter(User.username == email)
        .first()
    )
    if teacher:
        _teacher_record, user = teacher
        if user.role == "teacher" and user.password_hash and check_password_hash(user.password_hash, password):
            return user
        print(f"DEBUG: Teacher password mismatch for email={email}")

    student = (
        db.session.query(Student, User)
        .join(User, Student.user_id == User.id)
        .filter(Student.email == email)
        .first()
    )
    if student:
        _student_record, user = student
        if user.role == "student" and user.password_hash and check_password_hash(user.password_hash, password):
            return user
        print(f"DEBUG: Student password mismatch for email={email}")

    print(f"DEBUG: No matching admin/teacher/student account for email={email}")
    return None

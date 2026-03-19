from datetime import datetime
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, logout_user
from sqlalchemy import case, func
from sqlalchemy.orm import joinedload
from werkzeug.security import check_password_hash, generate_password_hash

from lecture_schedule import LECTURE_SLOTS
from models import Attendance, Student, Subject, Teacher, User, db

admin_bp = Blueprint("admin", __name__)


def admin_required():
    return current_user.is_authenticated and current_user.role == "admin"


def require_admin_login():
    if admin_required():
        return None

    if current_user.is_authenticated:
        logout_user()

    flash("Admin email and password are required to open the admin dashboard.", "danger")
    return redirect(url_for("auth.login"))


@admin_bp.route("/dashboard")
@login_required
def dashboard():
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    selected_semester = request.args.get("semester", type=int)
    if selected_semester not in {1, 2, 3, 4, 5, 6, None}:
        selected_semester = None

    stats = {
        "students": Student.query.count(),
        "teachers": Teacher.query.count(),
        "subjects": Subject.query.count(),
    }
    active_teachers = (
        Teacher.query.options(
            joinedload(Teacher.user),
            joinedload(Teacher.subject_assignments),
        )
        .filter(Teacher.is_active.is_(True))
        .order_by(Teacher.full_name)
        .all()
    )
    removed_teachers = (
        Teacher.query.options(joinedload(Teacher.user))
        .filter(Teacher.is_active.is_(False))
        .order_by(Teacher.full_name)
        .all()
    )
    subjects = (
        Subject.query.order_by(
            case((Subject.start_time.is_(None), 1), else_=0),
            Subject.start_time.asc(),
            Subject.name.asc(),
        ).all()
    )
    students_query = Student.query
    if selected_semester is not None:
        students_query = students_query.filter_by(semester=selected_semester)
    students = students_query.order_by(Student.full_name).all()
    recent_reports = (
        db.session.query(Attendance, Student, Subject)
        .join(Student, Attendance.student_id == Student.id)
        .join(Subject, Attendance.subject_id == Subject.id)
        .order_by(Attendance.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "admin/dashboard.html",
        stats=stats,
        teachers=active_teachers,
        removed_teachers=removed_teachers,
        subjects=subjects,
        students=students,
        selected_semester=selected_semester,
        recent_reports=recent_reports,
        lecture_slots=LECTURE_SLOTS,
    )


@admin_bp.route("/student-attendance")
@login_required
def student_attendance():
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    roll_number = request.args.get("roll_number", "").strip().upper()
    student = None
    summary_rows = []
    history_records = []

    if roll_number:
        student = Student.query.filter_by(roll_number=roll_number).first()
        if student is None:
            flash("Student not found for the entered roll number.", "danger")
        else:
            summary_rows = (
                db.session.query(
                    Subject.name.label("subject_name"),
                    func.count(Attendance.id).label("total_classes"),
                    func.sum(case((Attendance.status == "present", 1), else_=0)).label("present_count"),
                )
                .join(Attendance, Attendance.subject_id == Subject.id)
                .filter(Attendance.student_id == student.id)
                .group_by(Subject.id, Subject.name)
                .order_by(Subject.name.asc())
                .all()
            )
            history_records = (
                Attendance.query.options(
                    joinedload(Attendance.subject),
                    joinedload(Attendance.lecture),
                )
                .filter(Attendance.student_id == student.id)
                .order_by(Attendance.attendance_date.desc(), Attendance.created_at.desc())
                .all()
            )

    return render_template(
        "admin/student_attendance.html",
        roll_number=roll_number,
        student=student,
        summary_rows=summary_rows,
        history_records=history_records,
    )


@admin_bp.route("/pending-students")
@login_required
def pending_students():
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    students = (
        Student.query.filter_by(is_approved=False, is_rejected=False)
        .order_by(Student.created_at.asc())
        .all()
    )
    return render_template("admin/pending_students.html", students=students)


@admin_bp.route("/approve-student/<int:student_id>", methods=["POST"])
@login_required
def approve_student(student_id):
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    student = db.session.get(Student, student_id)
    if not student or student.is_rejected:
        flash("Student not found.", "danger")
        return redirect(url_for("admin.pending_students"))

    student.is_approved = True
    student.is_rejected = False
    db.session.commit()
    flash(f"{student.full_name} has been approved.", "success")
    return redirect(url_for("admin.pending_students"))


@admin_bp.route("/reject-student/<int:student_id>", methods=["POST"])
@login_required
def reject_student(student_id):
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    student = db.session.get(Student, student_id)
    if not student or student.is_approved:
        flash("Pending student not found.", "danger")
        return redirect(url_for("admin.pending_students"))

    student.is_rejected = True
    student.is_approved = False
    db.session.commit()

    flash("Student registration rejected.", "danger")
    return redirect(url_for("admin.pending_students"))


@admin_bp.route("/manage-teacher-subjects")
@login_required
def manage_teacher_subjects():
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    teachers = Teacher.query.filter_by(is_active=True).order_by(Teacher.full_name).all()

    return render_template(
        "admin/manage_teacher_subjects.html",
        teachers=teachers,
    )


@admin_bp.route("/teacher/<int:teacher_id>")
@login_required
def teacher_subjects(teacher_id):
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    teacher = (
        Teacher.query.options(
            joinedload(Teacher.subject_assignments),
            joinedload(Teacher.user),
        )
        .filter(Teacher.id == teacher_id, Teacher.is_active.is_(True))
        .first_or_404()
    )
    assigned_subjects = sorted(
        teacher.subject_assignments,
        key=lambda subject: (
            subject.start_time is None,
            subject.start_time or "",
            subject.code,
            subject.name,
        ),
    )
    return render_template(
        "admin/teacher_subjects.html",
        teacher=teacher,
        assigned_subjects=assigned_subjects,
    )


@admin_bp.route("/create-teacher", methods=["POST"])
@login_required
def create_teacher():
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    employee_code = request.form.get("employee_code", "").strip()
    password = request.form.get("password", "")
    subject_ids = request.form.getlist("subject_ids", type=int)

    if User.query.filter_by(username=email).first():
        flash("Teacher email already exists.", "danger")
        return redirect(url_for("admin.dashboard"))

    if Teacher.query.filter_by(employee_code=employee_code).first():
        flash("Employee code already exists.", "danger")
        return redirect(url_for("admin.dashboard"))

    user = User(username=email, role="teacher")
    user.password_hash = generate_password_hash(password)
    db.session.add(user)
    db.session.flush()

    teacher = Teacher(user_id=user.id, full_name=full_name, employee_code=employee_code)
    db.session.add(teacher)
    db.session.flush()

    if subject_ids:
        subjects = Subject.query.filter(Subject.id.in_(subject_ids)).all()
        teacher.subject_assignments.extend(subjects)

    db.session.commit()

    if subject_ids:
        flash("Teacher created and subjects assigned.", "success")
    else:
        flash("Teacher created.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/create-subject", methods=["POST"])
@login_required
def create_subject():
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip()
    semester = request.form.get("semester", type=int)
    subject_type = request.form.get("subject_type", "theory").strip()

    if not all([name, code, semester, subject_type]):
        flash("All fields (Name, Code, Semester, Type) are required.", "danger")
        return redirect(url_for("admin.dashboard"))

    if Subject.query.filter((Subject.name == name) | (Subject.code == code)).first():
        flash("Subject name or code already exists.", "danger")
        return redirect(url_for("admin.dashboard"))

    subject = Subject(
        name=name, code=code, semester=semester, subject_type=subject_type
    )
    db.session.add(subject)
    db.session.commit()

    flash("Subject created successfully. You can assign a teacher and set lecture times.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/assign-subject", methods=["POST"])
@login_required
def assign_subject():
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    subject_id = request.form.get("subject_id", type=int)
    teacher_id = request.form.get("teacher_id", type=int)

    subject = db.session.get(Subject, subject_id)
    teacher = Teacher.query.filter_by(id=teacher_id, is_active=True).first()
    if not subject or not teacher:
        flash("Subject or teacher not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    if teacher not in subject.teachers:
        subject.teachers.append(teacher)
    db.session.commit()
    flash("Subject assigned to teacher.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/remove_teacher/<int:teacher_id>", methods=["POST"])
@login_required
def remove_teacher(teacher_id):
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    teacher = db.session.get(Teacher, teacher_id)
    if not teacher or not teacher.is_active:
        flash("Active teacher not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    password = request.form.get("admin_password", "")
    if not password or not check_password_hash(current_user.password_hash, password):
        flash("Incorrect admin password.", "danger")
        return redirect(url_for("admin.dashboard"))

    teacher.is_active = False
    db.session.commit()
    flash(f"{teacher.full_name} has been removed.", "danger")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/restore_teacher/<int:teacher_id>", methods=["POST"])
@login_required
def restore_teacher(teacher_id):
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    teacher = db.session.get(Teacher, teacher_id)
    if not teacher or teacher.is_active:
        flash("Removed teacher not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    teacher.is_active = True
    db.session.commit()
    flash(f"{teacher.full_name} has been restored.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/teacher/<int:teacher_id>/subject/<int:subject_id>/remove", methods=["POST"])
@login_required
def remove_teacher_subject(teacher_id, subject_id):
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    teacher = db.session.get(Teacher, teacher_id)
    subject = db.session.get(Subject, subject_id)
    if not teacher or not subject:
        flash("Teacher or subject not found.", "danger")
        return redirect(url_for("admin.manage_teacher_subjects"))

    if subject in teacher.subject_assignments:
        teacher.subject_assignments.remove(subject)
        db.session.commit()
        flash("Subject removed from teacher successfully.", "success")
    else:
        flash("Subject is not assigned to this teacher.", "danger")

    return redirect(url_for("admin.teacher_subjects", teacher_id=teacher.id))


@admin_bp.route("/change-lecture-time", methods=["GET", "POST"])
@login_required
def change_lecture_time():
    access_redirect = require_admin_login()
    if access_redirect:
        return access_redirect

    if request.method == "POST":
        subject_id = request.form.get("subject_id", type=int)
        start_time_str = request.form.get("start_time")
        end_time_str = request.form.get("end_time")

        subject = db.session.get(Subject, subject_id)
        if not subject:
            flash("Subject not found. Please select a valid subject.", "danger")
            return redirect(url_for("admin.change_lecture_time"))

        try:
            start_time = datetime.strptime(start_time_str, "%H:%M").time()
            end_time = datetime.strptime(end_time_str, "%H:%M").time()

            if start_time >= end_time:
                flash("End time must be after start time.", "danger")
                return redirect(url_for("admin.change_lecture_time"))

            else:
                subject.start_time = start_time
                subject.end_time = end_time

                # Update the default 'Everyday' lecture template if it exists
                lecture = Lecture.query.filter_by(subject_id=subject.id, day_of_week="Everyday").first()
                if lecture:
                    lecture.start_time = start_time
                    lecture.end_time = end_time

                db.session.commit()
                flash(f"Lecture time updated for {subject.name}.", "success")
                return redirect(url_for("admin.dashboard"))
        except (ValueError, TypeError):
            flash("Invalid time format. Both start and end times are required.", "danger")
            return redirect(url_for("admin.change_lecture_time"))

    subjects = Subject.query.order_by(Subject.semester, Subject.name).all()
    return render_template("admin/change_lecture_time.html", subjects=subjects)

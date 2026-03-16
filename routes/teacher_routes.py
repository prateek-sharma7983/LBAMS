from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case

from models import (
    Attendance,
    Subject,
    Teacher,
    db,
    reconcile_lecture_attendance,
    teacher_subjects,
    update_attendance_summary,
)


teacher_bp = Blueprint("teacher", __name__)


def teacher_required():
    return current_user.is_authenticated and current_user.role == "teacher"


@teacher_bp.route("/dashboard")
@login_required
def dashboard():
    if not teacher_required():
        return redirect(url_for("auth.login"))

    reconcile_lecture_attendance()
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    subjects = (
        Subject.query.join(teacher_subjects, Subject.id == teacher_subjects.c.subject_id)
        .filter(teacher_subjects.c.teacher_id == teacher.id)
        .order_by(
            case((Subject.start_time.is_(None), 1), else_=0),
            Subject.start_time.asc(),
            Subject.name.asc(),
        )
        .all()
    )
    pending_requests = (
        Attendance.query.join(Subject)
        .join(teacher_subjects, Subject.id == teacher_subjects.c.subject_id)
        .filter(teacher_subjects.c.teacher_id == teacher.id, Attendance.status == "pending")
        .order_by(Attendance.attendance_date.desc(), Attendance.created_at.desc())
        .all()
    )
    notifications = [
        f"{record.student.full_name} marked attendance for {record.subject.name}"
        for record in pending_requests
    ]
    history = (
        Attendance.query.join(Subject)
        .join(teacher_subjects, Subject.id == teacher_subjects.c.subject_id)
        .filter(teacher_subjects.c.teacher_id == teacher.id)
        .order_by(Attendance.attendance_date.desc(), Attendance.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "teacher/dashboard.html",
        teacher=teacher,
        subjects=subjects,
        pending_requests=pending_requests,
        notifications=notifications,
        history=history,
    )


@teacher_bp.route("/subject/<int:subject_id>")
@login_required
def subject_detail(subject_id):
    if not teacher_required():
        return redirect(url_for("auth.login"))

    reconcile_lecture_attendance()
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    subject = (
        Subject.query.join(teacher_subjects, Subject.id == teacher_subjects.c.subject_id)
        .filter(Subject.id == subject_id, teacher_subjects.c.teacher_id == teacher.id)
        .first_or_404()
    )
    pending_records = (
        Attendance.query.filter_by(subject_id=subject.id, status="pending")
        .order_by(Attendance.attendance_date.desc(), Attendance.created_at.desc())
        .all()
    )
    history = (
        Attendance.query.filter(Attendance.subject_id == subject.id, Attendance.status != "pending")
        .order_by(Attendance.attendance_date.desc(), Attendance.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "teacher/subject_detail.html",
        teacher=teacher,
        subject=subject,
        pending_records=pending_records,
        history=history,
    )


@teacher_bp.route("/attendance/<int:attendance_id>/update", methods=["POST"])
@login_required
def update_attendance(attendance_id):
    if not teacher_required():
        return redirect(url_for("auth.login"))

    reconcile_lecture_attendance()
    teacher = Teacher.query.filter_by(user_id=current_user.id).first_or_404()
    attendance = (
        Attendance.query.join(Subject)
        .join(teacher_subjects, Subject.id == teacher_subjects.c.subject_id)
        .filter(Attendance.id == attendance_id, teacher_subjects.c.teacher_id == teacher.id)
        .first_or_404()
    )
    status = request.form.get("status", "")
    if status not in {"present", "absent"}:
        flash("Invalid attendance status.", "danger")
        return redirect(url_for("teacher.dashboard"))

    attendance.status = status
    update_attendance_summary(attendance.student_id, attendance.subject_id)
    db.session.commit()
    flash(f"Attendance {status}.", "success")
    return redirect(request.referrer or url_for("teacher.dashboard"))

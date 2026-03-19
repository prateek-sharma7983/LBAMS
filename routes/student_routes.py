from datetime import datetime
import pytz

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import case

from models import (
    ALLOWED_RADIUS_METERS,
    COLLEGE_LATITUDE,
    COLLEGE_LONGITUDE,
    Attendance,
    Student,
    Subject,
    db,
    ensure_subject_lecture,
    haversine_distance,
    reconcile_lecture_attendance,
    update_attendance_summary,
)

student_bp = Blueprint("student", __name__)
IST = pytz.timezone("Asia/Kolkata")


def student_required():
    return current_user.is_authenticated and current_user.role == "student"


def get_current_student():
    return Student.query.filter_by(user_id=current_user.id).first_or_404()


def require_roll_number(student):
    if not student.roll_number or not student.roll_number.strip():
        return redirect(url_for("student.update_roll_number"))
    return None


@student_bp.route("/update-roll-number", methods=["GET", "POST"])
@login_required
def update_roll_number():
    if not student_required():
        return redirect(url_for("auth.login"))

    student = get_current_student()
    if request.method == "POST":
        roll_number = request.form.get("roll_number", "").strip().upper()

        if not roll_number:
            return render_template(
                "student/update_roll_number.html",
                student=student,
                error_message="Roll number is required.",
            )

        existing_student = Student.query.filter(
            Student.roll_number == roll_number,
            Student.id != student.id,
        ).first()
        if existing_student:
            return render_template(
                "student/update_roll_number.html",
                student=student,
                error_message="Roll number already exists.",
            )

        student.roll_number = roll_number
        db.session.commit()
        return redirect(url_for("student.dashboard"))

    if student.roll_number and student.roll_number.strip():
        return redirect(url_for("student.dashboard"))

    return render_template("student/update_roll_number.html", student=student)


@student_bp.route("/dashboard")
@login_required
def dashboard():
    if not student_required():
        return redirect(url_for("auth.login"))

    student = get_current_student()
    roll_number_redirect = require_roll_number(student)
    if roll_number_redirect:
        return roll_number_redirect

    reconcile_lecture_attendance()
    subjects = (
        Subject.query.filter_by(semester=student.semester)
        .order_by(
            case((Subject.start_time.is_(None), 1), else_=0),
            Subject.start_time.asc(),
            Subject.name.asc(),
        )
        .all()
    )

    # Fetch today's attendance status for all subjects
    todays_attendance = Attendance.query.filter_by(
        student_id=student.id,
        attendance_date=datetime.now(IST).date()
    ).all()
    attendance_status = {att.subject_id: att.status for att in todays_attendance}

    summary = []
    for subject in subjects:
        stored_summary = update_attendance_summary(student.id, subject.id)
        summary.append(
            {
                "subject": subject,
                "total_classes": stored_summary.total_classes if stored_summary else 0,
                "present": stored_summary.present_classes if stored_summary else 0,
                "percentage": stored_summary.attendance_percentage if stored_summary else 0,
            }
        )

    db.session.commit()

    history = (
        Attendance.query.filter_by(student_id=student.id)
        .order_by(Attendance.attendance_date.desc(), Attendance.created_at.desc())
        .all()
    )
    return render_template(
        "student/dashboard.html",
        student=student,
        subjects=subjects,
        summary=summary,
        history=history,
        allowed_radius=ALLOWED_RADIUS_METERS,
        attendance_status=attendance_status,
    )


@student_bp.route("/subject/<int:subject_id>/attendance-history")
@login_required
def subject_attendance_history(subject_id):
    if not student_required():
        return redirect(url_for("auth.login"))

    student = get_current_student()
    roll_number_redirect = require_roll_number(student)
    if roll_number_redirect:
        return roll_number_redirect

    reconcile_lecture_attendance()
    subject = Subject.query.filter_by(id=subject_id, semester=student.semester).first_or_404()
    records = (
        Attendance.query.filter_by(student_id=student.id, subject_id=subject.id)
        .order_by(Attendance.attendance_date.desc(), Attendance.created_at.desc())
        .all()
    )
    return render_template(
        "student/subject_attendance_history.html",
        student=student,
        subject=subject,
        records=records,
    )


@student_bp.route("/mark-attendance", methods=["POST"])
@login_required
def mark_attendance():
    if not student_required():
        return jsonify({"ok": False, "message": "Unauthorized"}), 403

    reconcile_lecture_attendance() # auto absent
    student = get_current_student()
    if not student.roll_number or not student.roll_number.strip():
        return jsonify({"ok": False, "message": "Please update your roll number first."}), 400
    subject_id = request.form.get("subject_id", type=int)
    latitude = request.form.get("latitude", type=float)
    longitude = request.form.get("longitude", type=float)

    if not all([subject_id, latitude is not None, longitude is not None]):
        return jsonify({"ok": False, "message": "Could not get your location. Please enable GPS and try again."}), 400

    subject = Subject.query.filter_by(id=subject_id, semester=student.semester).first()
    if not subject:
        return jsonify({"ok": False, "message": "Subject not available for your semester."}), 404

    # Lecture Time Validation
    if subject.start_time and subject.end_time:
        current_time = datetime.now(IST).time()
        if current_time < subject.start_time:
            return jsonify({"ok": False, "message": "Lecture has not started yet."}), 400
        if current_time > subject.end_time:
            return jsonify({"ok": False, "message": "Lecture time is over."}), 400

    existing = Attendance.query.filter_by(
        student_id=student.id,
        subject_id=subject.id,
        attendance_date=datetime.now(IST).date(),
    ).first()
    if existing:
        return jsonify({"ok": False, "message": "Attendance already marked for this subject today."}), 400

    # Location Validation
    distance = haversine_distance(latitude, longitude, COLLEGE_LATITUDE, COLLEGE_LONGITUDE)
    if distance > ALLOWED_RADIUS_METERS:
        return jsonify({"ok": False, "message": f"You are too far from campus ({distance:.1f}m) to mark attendance."}), 400

    lecture = ensure_subject_lecture(subject)
    attendance = Attendance(
        student_id=student.id,
        subject_id=subject.id,
        lecture_id=lecture.id,
        attendance_date=datetime.now(IST).date(),
        status="pending",
        latitude=latitude,
        longitude=longitude,
        distance_meters=distance,
    )
    db.session.add(attendance)
    db.session.commit()
    return jsonify({"ok": True, "message": "Attendance sent to teacher for approval."})

    # Steps Performed:
    # 1. Checked if student is authorized
    # 2. Extracted the data from the form
    # 3. Validated the subject and student semester
    # 4. Validated the lecture time
    # 5. Prevented duplicate attendance
    # 6. Calculated the Haversine distance
    # 7. Finally, marked the attendance

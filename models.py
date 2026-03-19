from datetime import date, datetime, time
import math
import pytz

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

COLLEGE_LATITUDE = 28.355040
COLLEGE_LONGITUDE = 79.418186
ALLOWED_RADIUS_METERS = 60

IST = pytz.timezone("Asia/Kolkata")


teacher_subjects = db.Table(
    "teacher_subjects",
    db.Column("teacher_id", db.Integer, db.ForeignKey("teachers.id"), primary_key=True),
    db.Column("subject_id", db.Integer, db.ForeignKey("subjects.id"), primary_key=True),
)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)

    student = db.relationship("Student", back_populates="user", uselist=False)
    teacher = db.relationship("Teacher", back_populates="user", uselist=False)
    admin = db.relationship("Admin", back_populates="user", uselist=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Admin(db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)

    user = db.relationship("User", back_populates="admin")


class Teacher(db.Model):
    __tablename__ = "teachers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    employee_code = db.Column(db.String(30), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    user = db.relationship("User", back_populates="teacher")
    subject_assignments = db.relationship(
        "Subject",
        secondary=teacher_subjects,
        back_populates="teachers",
    )


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), unique=True, nullable=False)
    student_code = db.Column(db.String(30), unique=True, nullable=False)
    roll_number = db.Column(db.String(30), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    is_rejected = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="student")
    attendances = db.relationship("Attendance", back_populates="student", passive_deletes=True)
    attendance_summaries = db.relationship(
        "AttendanceSummary",
        back_populates="student",
        passive_deletes=True,
    )


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    semester = db.Column(db.Integer, nullable=False)
    subject_type = db.Column("type", db.String(20), nullable=False, default="theory")
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=True)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)

    teachers = db.relationship(
        "Teacher",
        secondary=teacher_subjects,
        back_populates="subject_assignments",
    )
    lectures = db.relationship("Lecture", back_populates="subject", cascade="all, delete-orphan")
    attendances = db.relationship("Attendance", back_populates="subject")
    attendance_summaries = db.relationship("AttendanceSummary", back_populates="subject")

    @property
    def lecture_time_label(self):
        if self.subject_type == "lab":
            return "Lab subject"
        if self.subject_type == "project":
            return "Project"
        if not self.start_time or not self.end_time:
            return "Time not set"
        start = self.start_time.strftime("%I:%M %p").lstrip("0")
        end = self.end_time.strftime("%I:%M %p").lstrip("0")
        return f"{start} - {end}"

    @property
    def display_label(self):
        return f"{self.code} - {self.name} (Semester {self.semester})"


class Lecture(db.Model):
    __tablename__ = "lectures"
    __table_args__ = (
        UniqueConstraint("subject_id", "lecture_date", name="uq_lecture_subject_date"),
    )

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    lecture_date = db.Column(db.Date, nullable=True)
    day_of_week = db.Column(db.String(15), nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)

    subject = db.relationship("Subject", back_populates="lectures")
    attendances = db.relationship("Attendance", back_populates="lecture")


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("student_id", "lecture_id", "attendance_date", name="uq_attendance_once"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    lecture_id = db.Column(db.Integer, db.ForeignKey("lectures.id"), nullable=False)
    attendance_date = db.Column(db.Date, default=date.today, nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False) # status can be pending, present, absent
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    distance_meters = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="attendances")
    subject = db.relationship("Subject", back_populates="attendances")
    lecture = db.relationship("Lecture", back_populates="attendances")


class AttendanceSummary(db.Model):
    __tablename__ = "attendance_summaries"
    __table_args__ = (
        UniqueConstraint("student_id", "subject_id", name="uq_attendance_summary"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("subjects.id"), nullable=False)
    total_classes = db.Column(db.Integer, default=0, nullable=False)
    present_classes = db.Column(db.Integer, default=0, nullable=False)
    attendance_percentage = db.Column(db.Float, default=0.0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    student = db.relationship("Student", back_populates="attendance_summaries")
    subject = db.relationship("Subject", back_populates="attendance_summaries")


def generate_student_code():
    last_student = Student.query.order_by(Student.id.desc()).first()
    next_number = 1001 if last_student is None else int(last_student.student_code[3:]) + 1
    return f"STU{next_number}"


def haversine_distance(lat1, lon1, lat2, lon2):
    radius = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def update_attendance_summary(student_id, subject_id):
    total_classes = Lecture.query.filter(
        Lecture.subject_id == subject_id,
        Lecture.lecture_date.isnot(None),
    ).count()
    present_classes = Attendance.query.filter(
        Attendance.student_id == student_id,
        Attendance.subject_id == subject_id,
        Attendance.status == "present",
    ).count()
    percentage = round((present_classes / total_classes) * 100, 2) if total_classes else 0.0

    summary = AttendanceSummary.query.filter_by(
        student_id=student_id,
        subject_id=subject_id,
    ).first()
    if summary is None:
        summary = AttendanceSummary(student_id=student_id, subject_id=subject_id)
        db.session.add(summary)

    summary.total_classes = total_classes
    summary.present_classes = present_classes
    summary.attendance_percentage = percentage
    return summary


def ensure_subject_lecture(subject, lecture_date=None):
    lecture_date = lecture_date or date.today()
    lecture_date = lecture_date or datetime.now(IST).date()
    lecture = Lecture.query.filter_by(subject_id=subject.id, lecture_date=lecture_date).first()
    start_time = subject.start_time or time(hour=0, minute=0)
    end_time = subject.end_time or time(hour=0, minute=0)
    day_of_week = lecture_date.strftime("%A")

    if lecture is None:
        lecture = Lecture(
            subject_id=subject.id,
            lecture_date=lecture_date,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
        )
        db.session.add(lecture)
        db.session.flush()
        return lecture

    if lecture.day_of_week != day_of_week:
        lecture.day_of_week = day_of_week
    if lecture.start_time != start_time:
        lecture.start_time = start_time
    if lecture.end_time != end_time:
        lecture.end_time = end_time
    db.session.flush()
    return lecture


def backfill_lecture_records_from_attendance():
    attendance_dates = (
        db.session.query(Attendance.subject_id, Attendance.attendance_date)
        .distinct()
        .order_by(Attendance.subject_id.asc(), Attendance.attendance_date.asc())
        .all()
    )
    summaries_to_refresh = set()

    for subject_id, attendance_date in attendance_dates:
        subject = db.session.get(Subject, subject_id)
        if subject is None or attendance_date is None:
            continue

        lecture = ensure_subject_lecture(subject, attendance_date)
        records = Attendance.query.filter_by(
            subject_id=subject_id,
            attendance_date=attendance_date,
        ).all()
        for record in records:
            if record.lecture_id == lecture.id:
                continue
            record.lecture_id = lecture.id
            summaries_to_refresh.add((record.student_id, subject_id))

    for student_id, subject_id in summaries_to_refresh:
        update_attendance_summary(student_id, subject_id)


def lecture_has_ended(lecture, reference_dt=None):
    reference_dt = reference_dt or datetime.now()
    reference_dt = reference_dt or datetime.now(IST)
    lecture_day = lecture.lecture_date or reference_dt.date()
    lecture_end_time = lecture.end_time or time(hour=0, minute=0)
    lecture_end = datetime.combine(lecture_day, lecture_end_time)
    # Handle timezone awareness for correct comparison
    if reference_dt.tzinfo is not None and lecture_end.tzinfo is None:
        lecture_end = reference_dt.tzinfo.localize(lecture_end)
    return reference_dt >= lecture_end


def auto_mark_absent_for_completed_lectures(reference_dt=None):
    reference_dt = reference_dt or datetime.now()
    reference_dt = reference_dt or datetime.now(IST)
    lectures = (
        Lecture.query.filter(Lecture.lecture_date.isnot(None))
        .order_by(Lecture.lecture_date.asc(), Lecture.subject_id.asc())
        .all()
    )
    summaries_to_refresh = set()

    for lecture in lectures:
        if not lecture_has_ended(lecture, reference_dt):
            continue

        existing_student_ids = {
            student_id
            for (student_id,) in db.session.query(Attendance.student_id)
            .filter(
                Attendance.subject_id == lecture.subject_id,
                Attendance.attendance_date == lecture.lecture_date,
            )
            .all()
        }
        students = Student.query.filter_by(semester=lecture.subject.semester).all()
        for student in students:
            if student.id in existing_student_ids:
                continue

            db.session.add(
                Attendance(
                    student_id=student.id,
                    subject_id=lecture.subject_id,
                    lecture_id=lecture.id,
                    attendance_date=lecture.lecture_date,
                    status="absent",
                    latitude=0.0,
                    longitude=0.0,
                    distance_meters=0.0,
                )
            )
            summaries_to_refresh.add((student.id, lecture.subject_id))

    if summaries_to_refresh:
        db.session.flush()
        for student_id, subject_id in summaries_to_refresh:
            update_attendance_summary(student_id, subject_id)


def reconcile_lecture_attendance(reference_dt=None):
    reference_dt = reference_dt or datetime.now()
    reference_dt = reference_dt or datetime.now(IST)
    current_date = reference_dt.date()
    current_time = reference_dt.time()

    backfill_lecture_records_from_attendance()

    subjects = Subject.query.all()
    for subject in subjects:
        if subject.start_time is None or current_time < subject.start_time:
            continue
        ensure_subject_lecture(subject, current_date)

    auto_mark_absent_for_completed_lectures(reference_dt)

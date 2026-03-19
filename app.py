from flask import Flask
from flask_login import LoginManager
from sqlalchemy import inspect, text
from models import (
    Admin,
    Attendance,
    AttendanceSummary,
    Lecture,
    Subject,
    User,
    db,
    reconcile_lecture_attendance,
)
from routes.admin_routes import admin_bp
from routes.auth_routes import auth_bp
from routes.main_routes import main_bp
from routes.student_routes import student_bp
from routes.teacher_routes import teacher_bp

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Admin email and password are required to open the dashboard."

DEFAULT_ADMIN_EMAIL = "prateeksharma8958@gmail.com"
DEFAULT_ADMIN_PASSWORD = "7983394909"
DEFAULT_ADMIN_NAME = "System Admin"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "change-this-secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///attendance_system.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    login_manager.init_app(app)

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(teacher_bp, url_prefix="/teacher")
    app.register_blueprint(student_bp, url_prefix="/student")

    with app.app_context():
        db.create_all()
        ensure_schema_updates()
        reconcile_lecture_attendance()
        ensure_default_admin()

    app.jinja_env.filters["format_time"] = format_time
    app.jinja_env.filters["format_date"] = format_date

    return app


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def ensure_default_admin():
    user = User.query.filter_by(username=DEFAULT_ADMIN_EMAIL).first()
    if user is None:
        user = User(username=DEFAULT_ADMIN_EMAIL, role="admin")
        user.set_password(DEFAULT_ADMIN_PASSWORD)
        db.session.add(user)
        db.session.flush()
    else:
        user.role = "admin"
        user.set_password(DEFAULT_ADMIN_PASSWORD)

    admin = Admin.query.filter_by(user_id=user.id).first()
    if admin is None:
        db.session.add(Admin(user_id=user.id, full_name=DEFAULT_ADMIN_NAME))

    db.session.commit()


def ensure_schema_updates():
    inspector = inspect(db.engine)
    student_columns = {column["name"] for column in inspector.get_columns("students")}
    teacher_columns = {column["name"] for column in inspector.get_columns("teachers")}
    subject_columns = {column["name"] for column in inspector.get_columns("subjects")}
    lecture_columns = {column["name"] for column in inspector.get_columns("lectures")}
    association_table_exists = inspector.has_table("teacher_subjects")
    lecture_indexes = {index["name"] for index in inspector.get_indexes("lectures")}
    student_indexes = {index["name"] for index in inspector.get_indexes("students")}

    with db.engine.begin() as connection:
        if "is_approved" not in student_columns:
            connection.execute(
                text("ALTER TABLE students ADD COLUMN is_approved BOOLEAN NOT NULL DEFAULT 0")
            )
        if "roll_number" not in student_columns:
            connection.execute(
                text("ALTER TABLE students ADD COLUMN roll_number VARCHAR(30)")
            )
        if "is_rejected" not in student_columns:
            connection.execute(
                text("ALTER TABLE students ADD COLUMN is_rejected BOOLEAN NOT NULL DEFAULT 0")
            )
        if "is_active" not in teacher_columns:
            connection.execute(
                text("ALTER TABLE teachers ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1")
            )
        if "start_time" not in subject_columns:
            connection.execute(text("ALTER TABLE subjects ADD COLUMN start_time TIME"))
        if "end_time" not in subject_columns:
            connection.execute(text("ALTER TABLE subjects ADD COLUMN end_time TIME"))
        if "type" not in subject_columns:
            connection.execute(text("ALTER TABLE subjects ADD COLUMN type VARCHAR(20)"))
            connection.execute(text("UPDATE subjects SET type = 'theory' WHERE type IS NULL"))
        if "lecture_date" not in lecture_columns:
            connection.execute(text("ALTER TABLE lectures ADD COLUMN lecture_date DATE"))
        if "uq_lectures_subject_date" not in lecture_indexes:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_lectures_subject_date "
                    "ON lectures(subject_id, lecture_date)"
                )
            )
        missing_roll_numbers = connection.execute(
            text("SELECT id FROM students WHERE roll_number IS NULL OR TRIM(roll_number) = ''")
        ).fetchall()
        for student_id, in missing_roll_numbers:
            connection.execute(
                text("UPDATE students SET roll_number = :roll_number WHERE id = :student_id"),
                {"roll_number": f"RN{student_id:04d}", "student_id": student_id},
            )

        if "uq_students_roll_number" not in student_indexes:
            connection.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_students_roll_number "
                    "ON students(roll_number)"
                )
            )

        if association_table_exists:
            legacy_assignments = connection.execute(
                text("SELECT id, teacher_id FROM subjects WHERE teacher_id IS NOT NULL")
            ).fetchall()
            for subject_id, teacher_id in legacy_assignments:
                existing_assignment = connection.execute(
                    text(
                        "SELECT 1 FROM teacher_subjects "
                        "WHERE teacher_id = :teacher_id AND subject_id = :subject_id"
                    ),
                    {"teacher_id": teacher_id, "subject_id": subject_id},
                ).fetchone()
                if existing_assignment is None:
                    connection.execute(
                        text(
                            "INSERT INTO teacher_subjects (teacher_id, subject_id) "
                            "VALUES (:teacher_id, :subject_id)"
                        ),
                        {"teacher_id": teacher_id, "subject_id": subject_id},
                    )


def format_time(value):
    if value is None:
        return "Not applicable"
    return value.strftime("%I:%M %p").lstrip("0")


def format_date(value):
    if value is None:
        return ""
    return value.strftime("%d-%m-%Y")


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)

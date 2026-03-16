# Location Based Attendance Management System

## Stack
- Python Flask backend
- MySQL database
- HTML, CSS, JavaScript frontend

## Setup
1. Create a virtual environment and install dependencies with `pip install -r requirements.txt`.
2. Create the MySQL database using `database/schema.sql`.
3. Update the MySQL connection string in `app.py`.
4. Run the application with `python app.py`.

## Default Admin
Create an admin account once from a Flask shell:

```python
from app import app
from models import Admin, User, db
from werkzeug.security import generate_password_hash

with app.app_context():
    user = User(username="admin@example.com", role="admin")
    user.password_hash = generate_password_hash("admin123")
    db.session.add(user)
    db.session.flush()
    db.session.add(Admin(user_id=user.id, full_name="System Admin"))
    db.session.commit()
```

## Features
- Student self-registration with generated IDs like `STU1001`
- Role-based login for admin, teacher, and student
- Admin teacher and subject management with attendance reports
- Teacher approval workflow for pending attendance
- Student geolocation-based attendance marking
- Haversine distance check within 10 meter campus radius
- Lecture-time window enforcement and duplicate attendance prevention

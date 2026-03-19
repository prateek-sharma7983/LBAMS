from flask import Blueprint, render_template

from models import Teacher


main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def home():
    teachers = Teacher.query.filter_by(is_active=True).order_by(Teacher.full_name).all()
    return render_template("home.html", teachers=teachers)

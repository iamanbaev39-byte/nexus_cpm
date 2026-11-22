import os
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="admin")
    full_name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Course(db.Model):
    __tablename__ = "courses"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    monthly_fee = db.Column(db.Float, nullable=False, default=0.0)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    groups = db.relationship("StudyGroup", backref="course", lazy=True, cascade="all, delete-orphan")


class StudyGroup(db.Model):
    __tablename__ = "study_groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    schedule_info = db.Column(db.String(120), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=True)
    students = db.relationship("Student", backref="group", lazy=True)
    lessons = db.relationship("Lesson", backref="group", lazy=True, cascade="all, delete-orphan")


class Teacher(db.Model):
    __tablename__ = "teachers"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    subject = db.Column(db.String(120), nullable=False)
    salary_type = db.Column(db.String(30), nullable=False, default="fixed")
    salary_amount = db.Column(db.Float, nullable=False, default=0.0)
    employment_date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(20), nullable=False, default="active")
    groups = db.relationship("StudyGroup", backref="teacher", lazy=True)
    payrolls = db.relationship("SalaryRecord", backref="teacher", lazy=True, cascade="all, delete-orphan")


class Student(db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    parent_phone = db.Column(db.String(40), nullable=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey("study_groups.id"), nullable=True)
    registration_date = db.Column(db.Date, default=date.today)
    monthly_fee = db.Column(db.Float, nullable=False, default=0.0)
    payment_status = db.Column(db.String(20), nullable=False, default="unpaid")
    course = db.relationship("Course", backref="students")
    attendances = db.relationship("AttendanceRecord", backref="student", lazy=True, cascade="all, delete-orphan")


class Lesson(db.Model):
    __tablename__ = "lessons"
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey("study_groups.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=True)
    lesson_date = db.Column(db.Date, nullable=False, default=date.today)
    topic = db.Column(db.String(200), nullable=True)
    teacher = db.relationship("Teacher", foreign_keys=[teacher_id])
    attendances = db.relationship("AttendanceRecord", backref="lesson", lazy=True, cascade="all, delete-orphan")


class AttendanceRecord(db.Model):
    __tablename__ = "attendance_records"
    __table_args__ = (
        db.UniqueConstraint("student_id", "lesson_id", name="uq_student_lesson_attendance"),
    )
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    lesson_id = db.Column(db.Integer, db.ForeignKey("lessons.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="present")
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)


class SalaryRecord(db.Model):
    __tablename__ = "salary_records"
    __table_args__ = (
        db.UniqueConstraint("teacher_id", "month_key", name="uq_teacher_month_salary"),
    )
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("teachers.id"), nullable=False)
    month_key = db.Column(db.String(7), nullable=False)
    base_salary = db.Column(db.Float, nullable=False, default=0.0)
    bonus = db.Column(db.Float, nullable=False, default=0.0)
    deductions = db.Column(db.Float, nullable=False, default=0.0)
    total_payable = db.Column(db.Float, nullable=False, default=0.0)
    is_paid = db.Column(db.Boolean, default=False)
    paid_at = db.Column(db.DateTime, nullable=True)


class Expense(db.Model):
    __tablename__ = "expenses"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(80), nullable=False, default="General")
    amount = db.Column(db.Float, nullable=False, default=0.0)
    expense_date = db.Column(db.Date, nullable=False, default=date.today)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def seed_initial_data():
    if not User.query.filter_by(username="admin").first():
        admin = User(
            username=os.environ.get("ADMIN_USERNAME", "admin"),
            role="admin",
            full_name="NEXUS Administrator",
        )
        admin.set_password(os.environ.get("ADMIN_PASSWORD", "Admin123!"))
        db.session.add(admin)

    if Course.query.count() == 0:
        default_courses = [
            Course(name="Python Backend", monthly_fee=600000, description="Python, Django, REST API va PostgreSQL"),
            Course(name="Frontend", monthly_fee=550000, description="HTML, CSS, JavaScript va React"),
            Course(name="Graphic Design", monthly_fee=500000, description="Photoshop, Illustrator va Figma"),
            Course(name="Cybersecurity", monthly_fee=650000, description="Tarmoq xavfsizligi va tahlil"),
            Course(name="English", monthly_fee=450000, description="General va IT English"),
            Course(name="Computer Literacy", monthly_fee=350000, description="Kompyuter savodxonligi"),
        ]
        db.session.add_all(default_courses)

    db.session.commit()


def parse_nonnegative_float(value, field_name="Qiymat"):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} raqam bo‘lishi kerak.")
    if number < 0:
        raise ValueError(f"{field_name} manfiy bo‘lmasligi kerak.")
    return round(number, 2)


def calculate_teacher_month_salary(teacher, month_key, bonus=0.0, deductions=0.0):
    year, month = map(int, month_key.split("-"))
    lessons_count = (
        db.session.query(func.count(Lesson.id))
        .filter(
            Lesson.teacher_id == teacher.id,
            func.extract("year", Lesson.lesson_date) == year,
            func.extract("month", Lesson.lesson_date) == month,
        )
        .scalar()
        or 0
    )

    if teacher.salary_type == "per_lesson":
        base_salary = float(teacher.salary_amount) * float(lessons_count)
    else:
        base_salary = float(teacher.salary_amount)

    total = max(0.0, base_salary + float(bonus) - float(deductions))
    return round(base_salary, 2), round(total, 2), lessons_count


def register_routes(app):
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                flash(f"Xush kelibsiz, {user.full_name}!", "success")
                return redirect(url_for("dashboard"))
            flash("Login yoki parol noto‘g‘ri.", "danger")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Tizimdan chiqdingiz.", "info")
        return redirect(url_for("login"))

    @app.route("/")
    @login_required
    def dashboard():
        today = date.today()
        month_key = today.strftime("%Y-%m")

        total_students = Student.query.count()
        total_teachers = Teacher.query.filter_by(status="active").count()
        active_courses = Course.query.filter_by(is_active=True).count()

        new_registrations = (
            db.session.query(func.count(Student.id))
            .filter(
                func.extract("year", Student.registration_date) == today.year,
                func.extract("month", Student.registration_date) == today.month,
            )
            .scalar()
            or 0
        )

        today_records = (
            db.session.query(AttendanceRecord)
            .join(Lesson, AttendanceRecord.lesson_id == Lesson.id)
            .filter(Lesson.lesson_date == today)
            .all()
        )
        if today_records:
            present_like = sum(1 for r in today_records if r.status in ("present", "late"))
            attendance_pct = round((present_like / len(today_records)) * 100, 1)
        else:
            attendance_pct = 0.0

        monthly_income = (
            db.session.query(func.coalesce(func.sum(Student.monthly_fee), 0.0))
            .filter(Student.payment_status == "paid")
            .scalar()
        )

        total_salary_expenses = (
            db.session.query(func.coalesce(func.sum(SalaryRecord.total_payable), 0.0))
            .filter(SalaryRecord.month_key == month_key)
            .scalar()
        )

        other_expenses = (
            db.session.query(func.coalesce(func.sum(Expense.amount), 0.0))
            .filter(
                func.extract("year", Expense.expense_date) == today.year,
                func.extract("month", Expense.expense_date) == today.month,
            )
            .scalar()
        )

        monthly_expenses = round(float(total_salary_expenses) + float(other_expenses), 2)
        total_groups = StudyGroup.query.count()
        paid_students = Student.query.filter_by(payment_status="paid").count()
        unpaid_students = Student.query.filter_by(payment_status="unpaid").count()
        inactive_teachers = Teacher.query.filter_by(status="inactive").count()
        net_profit = round(float(monthly_income) - monthly_expenses, 2)

        course_rows = (
            db.session.query(Course.name, func.count(Student.id))
            .outerjoin(Student, Student.course_id == Course.id)
            .group_by(Course.id, Course.name)
            .order_by(func.count(Student.id).desc())
            .all()
        )
        course_labels = [row[0] for row in course_rows]
        course_values = [row[1] or 0 for row in course_rows]

        attendance_labels = []
        attendance_values = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            records = (
                db.session.query(AttendanceRecord)
                .join(Lesson, AttendanceRecord.lesson_id == Lesson.id)
                .filter(Lesson.lesson_date == day)
                .all()
            )
            if records:
                present_like = sum(1 for record in records if record.status in ("present", "late"))
                percentage = round(present_like * 100 / len(records), 1)
            else:
                percentage = 0.0
            attendance_labels.append(day.strftime("%d.%m"))
            attendance_values.append(percentage)

        return render_template(
            "dashboard.html",
            total_students=total_students,
            total_teachers=total_teachers,
            inactive_teachers=inactive_teachers,
            total_groups=total_groups,
            paid_students=paid_students,
            unpaid_students=unpaid_students,
            attendance_pct=attendance_pct,
            monthly_income=round(float(monthly_income), 2),
            monthly_expenses=monthly_expenses,
            total_salary_expenses=round(float(total_salary_expenses), 2),
            net_profit=net_profit,
            active_courses=active_courses,
            new_registrations=new_registrations,
            course_labels=course_labels,
            course_values=course_values,
            attendance_labels=attendance_labels,
            attendance_values=attendance_values,
        )

    @app.route("/teachers")
    @login_required
    def teachers_list():
        q = request.args.get("q", "").strip()
        query = Teacher.query
        if q:
            query = query.filter(
                (Teacher.full_name.ilike(f"%{q}%"))
                | (Teacher.subject.ilike(f"%{q}%"))
                | (Teacher.phone.ilike(f"%{q}%"))
            )
        teachers = query.order_by(Teacher.id.desc()).all()
        return render_template("teachers.html", teachers=teachers, q=q)

    @app.route("/teachers/new", methods=["GET", "POST"])
    @login_required
    @admin_required
    def teacher_create():
        if request.method == "POST":
            try:
                full_name = request.form.get("full_name", "").strip()
                phone = request.form.get("phone", "").strip()
                subject = request.form.get("subject", "").strip()
                if not full_name or not phone or not subject:
                    raise ValueError("Ism, telefon va fan maydonlari majburiy.")
                emp_str = request.form.get("employment_date", "")
                emp_date = datetime.strptime(emp_str, "%Y-%m-%d").date() if emp_str else date.today()
                salary_type = request.form.get("salary_type", "fixed")
                if salary_type not in ("fixed", "per_lesson"):
                    raise ValueError("Ish haqi turi noto‘g‘ri.")
                teacher = Teacher(
                    full_name=full_name,
                    phone=phone,
                    email=request.form.get("email", "").strip(),
                    subject=subject,
                    salary_type=salary_type,
                    salary_amount=parse_nonnegative_float(request.form.get("salary_amount"), "Ish haqi"),
                    employment_date=emp_date,
                    status=request.form.get("status", "active"),
                )
                db.session.add(teacher)
                db.session.commit()
                flash("O‘qituvchi muvaffaqiyatli qo‘shildi.", "success")
                return redirect(url_for("teachers_list"))
            except (ValueError, KeyError) as exc:
                db.session.rollback()
                flash(str(exc), "danger")
        return render_template("teacher_form.html", teacher=None)

    @app.route("/teachers/<int:teacher_id>/edit", methods=["GET", "POST"])
    @login_required
    @admin_required
    def teacher_edit(teacher_id):
        teacher = db.session.get(Teacher, teacher_id) or abort(404)
        if request.method == "POST":
            try:
                full_name = request.form.get("full_name", "").strip()
                phone = request.form.get("phone", "").strip()
                subject = request.form.get("subject", "").strip()
                if not full_name or not phone or not subject:
                    raise ValueError("Ism, telefon va fan maydonlari majburiy.")
                emp_str = request.form.get("employment_date", "")
                if emp_str:
                    teacher.employment_date = datetime.strptime(emp_str, "%Y-%m-%d").date()
                teacher.full_name = full_name
                teacher.phone = phone
                teacher.email = request.form.get("email", "").strip()
                teacher.subject = subject
                teacher.salary_type = request.form.get("salary_type", "fixed")
                if teacher.salary_type not in ("fixed", "per_lesson"):
                    raise ValueError("Ish haqi turi noto‘g‘ri.")
                teacher.salary_amount = parse_nonnegative_float(request.form.get("salary_amount"), "Ish haqi")
                teacher.status = request.form.get("status", "active")
                if teacher.status not in ("active", "inactive"):
                    raise ValueError("Holat noto‘g‘ri.")
                db.session.commit()
                flash("O‘qituvchi ma’lumotlari yangilandi.", "success")
                return redirect(url_for("teachers_list"))
            except (ValueError, KeyError) as exc:
                db.session.rollback()
                flash(str(exc), "danger")
        return render_template("teacher_form.html", teacher=teacher)

    @app.route("/teachers/<int:teacher_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def teacher_delete(teacher_id):
        teacher = db.session.get(Teacher, teacher_id) or abort(404)
        if teacher.groups or teacher.payrolls:
            flash("Bu o‘qituvchiga guruh yoki ish haqi yozuvi biriktirilgan.", "danger")
            return redirect(url_for("teachers_list"))
        db.session.delete(teacher)
        db.session.commit()
        flash("O‘qituvchi o‘chirildi.", "info")
        return redirect(url_for("teachers_list"))

    @app.route("/students")
    @login_required
    def students_list():
        q = request.args.get("q", "").strip()
        query = Student.query
        if q:
            query = query.filter(
                (Student.full_name.ilike(f"%{q}%"))
                | (Student.phone.ilike(f"%{q}%"))
                | (Student.parent_phone.ilike(f"%{q}%"))
            )
        students = query.order_by(Student.id.desc()).all()
        return render_template("students.html", students=students, q=q)

    @app.route("/students/new", methods=["GET", "POST"])
    @login_required
    def student_create():
        courses = Course.query.filter_by(is_active=True).all()
        groups = StudyGroup.query.all()
        if request.method == "POST":
            try:
                full_name = request.form.get("full_name", "").strip()
                phone = request.form.get("phone", "").strip()
                if not full_name or not phone:
                    raise ValueError("Ism va telefon maydonlari majburiy.")
                course_id = int(request.form["course_id"])
                course = db.session.get(Course, course_id) or abort(404)
                group_val = request.form.get("group_id")
                group_id = int(group_val) if group_val else None
                if group_id:
                    group = db.session.get(StudyGroup, group_id)
                    if not group or group.course_id != course_id:
                        raise ValueError("Guruh tanlangan kursga tegishli emas.")
                fee_raw = request.form.get("monthly_fee")
                monthly_fee = parse_nonnegative_float(fee_raw if fee_raw not in (None, "") else course.monthly_fee, "To‘lov")
                payment_status = request.form.get("payment_status", "unpaid")
                if payment_status not in ("paid", "unpaid"):
                    raise ValueError("To‘lov holati noto‘g‘ri.")
                student = Student(
                    full_name=full_name,
                    phone=phone,
                    parent_phone=request.form.get("parent_phone", "").strip(),
                    course_id=course_id,
                    group_id=group_id,
                    monthly_fee=monthly_fee,
                    payment_status=payment_status,
                )
                db.session.add(student)
                db.session.commit()
                flash("O‘quvchi ro‘yxatga olindi.", "success")
                return redirect(url_for("students_list"))
            except (ValueError, KeyError) as exc:
                db.session.rollback()
                flash(str(exc), "danger")
        return render_template("student_form.html", student=None, courses=courses, groups=groups)

    @app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
    @login_required
    def student_edit(student_id):
        student = db.session.get(Student, student_id) or abort(404)
        courses = Course.query.filter_by(is_active=True).all()
        groups = StudyGroup.query.all()
        if request.method == "POST":
            try:
                full_name = request.form.get("full_name", "").strip()
                phone = request.form.get("phone", "").strip()
                if not full_name or not phone:
                    raise ValueError("Ism va telefon maydonlari majburiy.")
                course_id = int(request.form["course_id"])
                course = db.session.get(Course, course_id)
                if not course:
                    raise ValueError("Kurs topilmadi.")
                group_val = request.form.get("group_id")
                group_id = int(group_val) if group_val else None
                if group_id:
                    group = db.session.get(StudyGroup, group_id)
                    if not group or group.course_id != course_id:
                        raise ValueError("Guruh tanlangan kursga tegishli emas.")
                payment_status = request.form.get("payment_status", "unpaid")
                if payment_status not in ("paid", "unpaid"):
                    raise ValueError("To‘lov holati noto‘g‘ri.")
                student.full_name = full_name
                student.phone = phone
                student.parent_phone = request.form.get("parent_phone", "").strip()
                student.course_id = course_id
                student.group_id = group_id
                student.monthly_fee = parse_nonnegative_float(request.form.get("monthly_fee"), "To‘lov")
                student.payment_status = payment_status
                db.session.commit()
                flash("O‘quvchi ma’lumotlari yangilandi.", "success")
                return redirect(url_for("students_list"))
            except (ValueError, KeyError) as exc:
                db.session.rollback()
                flash(str(exc), "danger")
        return render_template("student_form.html", student=student, courses=courses, groups=groups)

    @app.route("/students/<int:student_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def student_delete(student_id):
        student = db.session.get(Student, student_id) or abort(404)
        db.session.delete(student)
        db.session.commit()
        flash("O‘quvchi o‘chirildi.", "info")
        return redirect(url_for("students_list"))

    @app.route("/courses", methods=["GET", "POST"])
    @login_required
    def courses_view():
        teachers = Teacher.query.filter_by(status="active").all()
        if request.method == "POST":
            form_type = request.form.get("form_type")
            if form_type == "course":
                try:
                    name = request.form.get("name", "").strip()
                    if not name:
                        raise ValueError("Kurs nomi majburiy.")
                    if Course.query.filter(func.lower(Course.name) == name.lower()).first():
                        raise ValueError("Bunday nomli kurs mavjud.")
                    course = Course(
                        name=name,
                        monthly_fee=parse_nonnegative_float(request.form.get("monthly_fee"), "Kurs narxi"),
                        description=request.form.get("description", "").strip(),
                    )
                    db.session.add(course)
                    db.session.commit()
                    flash("Yangi kurs qo‘shildi.", "success")
                except (ValueError, KeyError) as exc:
                    db.session.rollback()
                    flash(str(exc), "danger")
            elif form_type == "group":
                try:
                    name = request.form.get("group_name", "").strip()
                    if not name:
                        raise ValueError("Guruh nomi majburiy.")
                    course_id = int(request.form["course_id"])
                    if not db.session.get(Course, course_id):
                        raise ValueError("Kurs topilmadi.")
                    teacher_val = request.form.get("teacher_id")
                    group = StudyGroup(
                        name=name,
                        schedule_info=request.form.get("schedule_info", "").strip(),
                        course_id=course_id,
                        teacher_id=int(teacher_val) if teacher_val else None,
                    )
                    db.session.add(group)
                    db.session.commit()
                    flash("Yangi guruh yaratildi.", "success")
                except (ValueError, KeyError) as exc:
                    db.session.rollback()
                    flash(str(exc), "danger")
            return redirect(url_for("courses_view"))

        courses = Course.query.order_by(Course.id.desc()).all()
        groups = StudyGroup.query.order_by(StudyGroup.id.desc()).all()
        return render_template("courses.html", courses=courses, groups=groups, teachers=teachers)

    @app.route("/courses/<int:course_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def course_delete(course_id):
        course = db.session.get(Course, course_id) or abort(404)
        if course.students or course.groups:
            flash("Bu kursda o‘quvchi yoki guruh bor, avval ularni o‘zgartiring.", "danger")
            return redirect(url_for("courses_view"))
        db.session.delete(course)
        db.session.commit()
        flash("Kurs o‘chirildi.", "info")
        return redirect(url_for("courses_view"))

    @app.route("/groups/<int:group_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def group_delete(group_id):
        group = db.session.get(StudyGroup, group_id) or abort(404)
        if group.students or group.lessons:
            flash("Bu guruhda o‘quvchi yoki darslar bor, avval ularni o‘zgartiring.", "danger")
            return redirect(url_for("courses_view"))
        db.session.delete(group)
        db.session.commit()
        flash("Guruh o‘chirildi.", "info")
        return redirect(url_for("courses_view"))

    @app.route("/attendance", methods=["GET", "POST"])
    @login_required
    def attendance_view():
        groups = StudyGroup.query.all()
        teachers = Teacher.query.filter_by(status="active").all()
        if request.method == "POST":
            try:
                group_id = int(request.form["group_id"])
                if not db.session.get(StudyGroup, group_id):
                    raise ValueError("Guruh topilmadi.")
                l_date_str = request.form.get("lesson_date", "")
                l_date = datetime.strptime(l_date_str, "%Y-%m-%d").date() if l_date_str else date.today()
                existing_lesson = Lesson.query.filter_by(group_id=group_id, lesson_date=l_date).first()
                if existing_lesson:
                    flash("Bu guruh uchun shu sana bo‘yicha dars allaqachon ochilgan.", "danger")
                    return redirect(url_for("mark_attendance", lesson_id=existing_lesson.id))
                t_val = request.form.get("teacher_id")
                lesson = Lesson(
                    group_id=group_id,
                    teacher_id=int(t_val) if t_val else None,
                    lesson_date=l_date,
                    topic=request.form.get("topic", "").strip(),
                )
                db.session.add(lesson)
                db.session.commit()
                flash("Dars ochildi, davomatni belgilashingiz mumkin.", "success")
                return redirect(url_for("mark_attendance", lesson_id=lesson.id))
            except (ValueError, KeyError) as exc:
                db.session.rollback()
                flash(str(exc) if isinstance(exc, ValueError) else "Dars ma’lumotlari noto‘g‘ri.", "danger")

        lessons = Lesson.query.order_by(Lesson.lesson_date.desc(), Lesson.id.desc()).all()
        return render_template(
            "attendance.html",
            groups=groups,
            teachers=teachers,
            lessons=lessons,
            now_date=date.today().strftime("%Y-%m-%d"),
        )

    @app.route("/attendance/lesson/<int:lesson_id>", methods=["GET", "POST"])
    @login_required
    def mark_attendance(lesson_id):
        lesson = db.session.get(Lesson, lesson_id) or abort(404)
        students = Student.query.filter_by(group_id=lesson.group_id).all()
        existing = {r.student_id: r for r in AttendanceRecord.query.filter_by(lesson_id=lesson.id).all()}

        if request.method == "POST":
            for st in students:
                status_val = request.form.get(f"status_{st.id}", "present")
                if status_val not in ("present", "late", "absent"):
                    status_val = "present"
                if st.id in existing:
                    existing[st.id].status = status_val
                    existing[st.id].recorded_at = datetime.utcnow()
                else:
                    rec = AttendanceRecord(student_id=st.id, lesson_id=lesson.id, status=status_val)
                    db.session.add(rec)
            db.session.commit()
            flash("Davomat saqlandi.", "success")
            return redirect(url_for("attendance_view"))

        return render_template("mark_attendance.html", lesson=lesson, students=students, existing=existing)

    @app.route("/attendance/lesson/<int:lesson_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def lesson_delete(lesson_id):
        lesson = db.session.get(Lesson, lesson_id) or abort(404)
        db.session.delete(lesson)
        db.session.commit()
        flash("Dars va unga bog‘liq davomat yozuvlari o‘chirildi.", "info")
        return redirect(url_for("attendance_view"))

    @app.route("/payroll", methods=["GET", "POST"])
    @login_required
    @admin_required
    def payroll_view():
        month_key = request.args.get("month") or request.form.get("month_key") or date.today().strftime("%Y-%m")
        teachers = Teacher.query.order_by(Teacher.full_name.asc()).all()

        if request.method == "POST":
            try:
                action = request.form.get("action", "calculate")
                teacher_id = int(request.form["teacher_id"])
                teacher = db.session.get(Teacher, teacher_id) or abort(404)
                bonus = parse_nonnegative_float(request.form.get("bonus"), "Bonus")
                deductions = parse_nonnegative_float(request.form.get("deductions"), "Jarima")

                base_salary, total_payable, _ = calculate_teacher_month_salary(
                    teacher, month_key, bonus=bonus, deductions=deductions
                )

                record = SalaryRecord.query.filter_by(teacher_id=teacher.id, month_key=month_key).first()
                if not record:
                    record = SalaryRecord(teacher_id=teacher.id, month_key=month_key)
                    db.session.add(record)

                record.base_salary = base_salary
                record.bonus = bonus
                record.deductions = deductions
                record.total_payable = total_payable

                if action == "mark_paid":
                    record.is_paid = True
                    record.paid_at = datetime.utcnow()
                    flash(f"{teacher.full_name} uchun oylik to‘langan deb belgilandi.", "success")
                else:
                    flash(f"{teacher.full_name} uchun oylik hisoblandi.", "success")

                db.session.commit()
                return redirect(url_for("payroll_view", month=month_key))
            except (ValueError, KeyError) as exc:
                db.session.rollback()
                flash(str(exc), "danger")

        records_map = {
            r.teacher_id: r for r in SalaryRecord.query.filter_by(month_key=month_key).all()
        }
        rows = []
        for t in teachers:
            base_calc, total_calc, lessons_cnt = calculate_teacher_month_salary(t, month_key)
            rec = records_map.get(t.id)
            rows.append({
                "teacher": t,
                "lessons_count": lessons_cnt,
                "base_salary": rec.base_salary if rec else base_calc,
                "bonus": rec.bonus if rec else 0.0,
                "deductions": rec.deductions if rec else 0.0,
                "total_payable": rec.total_payable if rec else total_calc,
                "is_paid": rec.is_paid if rec else False,
            })

        return render_template("payroll.html", rows=rows, month_key=month_key)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_template("errors/500.html"), 500


def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))
    instance_dir = os.path.join(basedir, "instance")
    os.makedirs(instance_dir, exist_ok=True)

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "nexus-dev-secret-key")
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        db_url = "sqlite:///" + os.path.join(instance_dir, "nexus.db")
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["BRAND_NAME"] = os.environ.get("BRAND_NAME", "NEXUS")

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "login"

    @app.context_processor
    def inject_globals():
        return {"brand_name": app.config["BRAND_NAME"], "current_year": datetime.utcnow().year}

    with app.app_context():
        db.create_all()
        seed_initial_data()

    register_routes(app)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
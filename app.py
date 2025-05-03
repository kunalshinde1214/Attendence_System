from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///attendance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'teacher' or 'student'
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    total_lectures = db.Column(db.Integer, default=0)
    attended_lectures = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create database
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def index():
    students = Student.query.all()
    
    # Calculate statistics for the index page
    total_students = len(students)
    total_lectures = sum(student.total_lectures for student in students)
    avg_attendance = (sum(student.attended_lectures for student in students) / total_lectures * 100) if total_lectures > 0 else 0
    
    # Calculate attendance distribution
    above_90 = sum(1 for student in students if student.total_lectures > 0 and (student.attended_lectures / student.total_lectures) >= 0.90)
    between_75_90 = sum(1 for student in students if student.total_lectures > 0 and 0.75 <= (student.attended_lectures / student.total_lectures) < 0.90)
    between_65_75 = sum(1 for student in students if student.total_lectures > 0 and 0.65 <= (student.attended_lectures / student.total_lectures) < 0.75)
    below_65 = sum(1 for student in students if student.total_lectures > 0 and (student.attended_lectures / student.total_lectures) < 0.65)
    defaulters = sum(1 for student in students if student.total_lectures > 0 and (student.attended_lectures / student.total_lectures) < 0.75)
    
    return render_template('index.html', 
                         students=students,
                         total_students=total_students,
                         total_lectures=total_lectures,
                         avg_attendance=round(avg_attendance, 1),
                         above_90=above_90,
                         between_75_90=between_75_90,
                         between_65_75=between_65_75,
                         below_65=below_65,
                         defaulters=defaulters)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            if user.role == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            return redirect(url_for('student_profile'))
        flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        name = request.form.get('name')
        role = request.form.get('role')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('signup'))
        
        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            name=name,
            role=role
        )
        db.session.add(user)
        db.session.commit()
        
        if role == 'student':
            student = Student(
                student_id=f"S{user.id:03d}",
                name=name,
                user_id=user.id
            )
            db.session.add(student)
            db.session.commit()
        
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out')
    return redirect(url_for('login'))

@app.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher':
        flash('Access denied')
        return redirect(url_for('index'))
    
    students = Student.query.all()
    return render_template('dashboard.html', students=students)

@app.route('/teacher/student/add', methods=['GET', 'POST'])
@login_required
def add_student():
    if current_user.role != 'teacher':
        flash('Access denied')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        student_id = request.form.get('student_id')
        name = request.form.get('name')
        total_lectures = request.form.get('total_lectures', 0)
        attended_lectures = request.form.get('attended_lectures', 0)
        
        if Student.query.filter_by(student_id=student_id).first():
            flash('Student ID already exists')
            return redirect(url_for('add_student'))
        
        student = Student(
            student_id=student_id,
            name=name,
            total_lectures=int(total_lectures),
            attended_lectures=int(attended_lectures)
        )
        db.session.add(student)
        db.session.commit()
        flash('Student added successfully')
        return redirect(url_for('teacher_dashboard'))
    
    return render_template('add_student.html')

@app.route('/teacher/student/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_student(id):
    if current_user.role != 'teacher':
        flash('Access denied')
        return redirect(url_for('index'))
    
    student = Student.query.get_or_404(id)
    
    if request.method == 'POST':
        student.student_id = request.form.get('student_id')
        student.name = request.form.get('name')
        student.total_lectures = int(request.form.get('total_lectures', 0))
        student.attended_lectures = int(request.form.get('attended_lectures', 0))
        db.session.commit()
        flash('Student updated successfully')
        return redirect(url_for('teacher_dashboard'))
    
    return render_template('edit_student.html', student=student)

@app.route('/teacher/student/delete/<int:id>', methods=['POST'])
@login_required
def delete_student(id):
    if current_user.role != 'teacher':
        flash('Access denied')
        return redirect(url_for('index'))
    
    student = Student.query.get_or_404(id)
    db.session.delete(student)
    db.session.commit()
    flash('Student deleted successfully')
    return redirect(url_for('teacher_dashboard'))

@app.route('/student/profile')
@login_required
def student_profile():
    if current_user.role != 'student':
        flash('Access denied')
        return redirect(url_for('index'))
    
    student = Student.query.filter_by(user_id=current_user.id).first()
    if not student:
        flash('Student profile not found')
        return redirect(url_for('index'))
    
    attendance_percentage = (student.attended_lectures / student.total_lectures * 100) if student.total_lectures > 0 else 0
    return render_template('student_profile.html', student=student, attendance_percentage=attendance_percentage)

@app.route('/api/calculate_attendance', methods=['POST'])
def calculate_attendance():
    data = request.get_json()
    total_lectures = int(data.get('total_lectures', 0))
    attended_lectures = int(data.get('attended_lectures', 0))
    
    if total_lectures <= 0 or attended_lectures > total_lectures:
        return jsonify({'error': 'Invalid input'}), 400
    
    percentage = (attended_lectures / total_lectures) * 100
    status = 'Good' if percentage >= 75 else 'Warning' if percentage >= 70 else 'Defaulter'
    
    if percentage < 75:
        required_lectures = int((75 * total_lectures - 100 * attended_lectures) / (100 - 75))
        message = f'You need to attend {required_lectures} more lectures to reach 75% attendance.'
    else:
        message = 'Your attendance is above the required threshold. Keep it up!'
    
    return jsonify({
        'percentage': round(percentage, 1),
        'status': status,
        'message': message
    })

@app.route('/api/student/<int:id>')
@login_required
def get_student(id):
    if current_user.role != 'teacher':
        return jsonify({'error': 'Access denied'}), 403
    student = Student.query.get_or_404(id)
    return jsonify({
        'id': student.id,
        'name': student.name,
        'total_lectures': student.total_lectures,
        'attended_lectures': student.attended_lectures
    })

if __name__ == '__main__':
    app.run(debug=True)
import os
import base64
import firebase_admin
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from database import Database
from firebase_admin import credentials, db as firebase_db, storage, auth
import cv2
import dlib
import numpy as np
from datetime import datetime

# Initialize the Flask application
app = Flask(__name__, template_folder='../templates', static_folder='../static')
app.secret_key = 'your_secret_key'  # Needed for session management

# Set the database path
DATABASE_PATH = os.path.join(os.path.dirname(__file__), '../database/face_data.db')
db_instance = Database(DATABASE_PATH)

# Initialize Firebase
cred = credentials.Certificate('attendancesystem-b5af6-firebase-adminsdk-6vbjl-adcc71533d.json')
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://attendancesystem-b5af6-default-rtdb.firebaseio.com/',
    'storageBucket': 'attendancesystem-b5af6.appspot.com'
})

# Define the path to save captured faces
CAPTURED_FACES_PATH = os.path.join(os.path.dirname(__file__), '../captured_faces')
os.makedirs(CAPTURED_FACES_PATH, exist_ok=True)

# Load Dlib's face detector and facial landmark predictor
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("models/shape_predictor_68_face_landmarks.dat")
face_encoder = dlib.face_recognition_model_v1("models/dlib_face_recognition_resnet_model_v1.dat")

# Set the allowed time frame for marking attendance (e.g., 10 minutes)
ALLOWED_ATTENDANCE_TIMEFRAME = 10 * 60  # in seconds

# This dictionary will store the last attendance marking time for each student
last_attendance_time = {}

@app.route('/')
def homepage():
    return render_template('homepage.html')

@app.route('/admin')
def admin():
    teacher_name = session.get('teacher_name', 'Guest')  # Default to 'Guest' if not logged in
    return render_template('admin.html', teacher_name=teacher_name)
 


@app.route('/teacherlogin', methods=['GET', 'POST'])
def teacher_login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        try:
            # Sign in the user with email and password
            user = auth.get_user_by_email(email)
            # TODO: Validate password with Firebase Authentication

            # Fetch teacher's details from Firebase
            teacher_ref = firebase_db.reference('teachers')
            teacher_info = teacher_ref.child(user.uid).get()

            if teacher_info:
                session['teacher_name'] = teacher_info['name']  # Store teacher's name in session
                flash('Login successful!')  # Flash a success message
                return redirect(url_for('admin'))

            flash('User details not found.')
            return render_template('teacherlogin.html')

        except Exception as e:
            flash('Invalid credentials or user not found.')
            return render_template('teacherlogin.html')

    return render_template('teacherlogin.html')



@app.route('/teacher_register', methods=['GET', 'POST'])
def teacher_register():
    if request.method == 'POST':
        # Get form data
        teacher_name = request.form.get('teacher_name')
        teacher_email = request.form.get('teacher_email')
        teacher_password = request.form.get('teacher_password')
        teacher_designation = request.form.get('teacher_designation')
        teacher_department = request.form.get('teacher_department')

        try:
            # Register new teacher in Firebase
            user = auth.create_user(
                email=teacher_email,
                password=teacher_password
            )

            # Save teacher info in Firebase Realtime Database
            ref = firebase_db.reference('teachers')
            ref.child(user.uid).set({
                'name': teacher_name,
                'email': teacher_email,
                'designation': teacher_designation,
                'department': teacher_department
            })

            flash('Registration successful! Please log in.')
            return redirect(url_for('teacher_login'))

        except Exception as e:
            flash(f"Error occurred: {e}")
            return render_template('teacherregister.html')

    return render_template('teacherregister.html')

@app.route('/new_student_registration', methods=['GET', 'POST'])
def new_student_registration():
    if request.method == 'POST':
        return redirect(url_for('admin'))
    return render_template('newstudentregistration.html')

@app.route('/upload_photo', methods=['POST'])
def upload_photo():
    try:
        data = request.get_json()
        photo_data = data['photo']
        usn = data['usn']
        
        filename = f"{usn}.png"
        file_path = os.path.join(CAPTURED_FACES_PATH, filename)

        header, encoded = photo_data.split(',', 1)
        with open(file_path, 'wb') as f:
            f.write(base64.b64decode(encoded))

        # Perform face detection and encoding
        img = cv2.imread(file_path)
        faces = detector(img)

        if len(faces) > 0:
            shape = predictor(img, faces[0])
            face_encoding = np.array(face_encoder.compute_face_descriptor(img, shape)).tolist()

            # Upload image to Firebase Storage
            bucket = storage.bucket()
            blob = bucket.blob(filename)
            blob.upload_from_filename(file_path)
            photo_url = blob.public_url

            student_info = {
                'name': data['name'],
                'year': data['year'],
                'branch': data['branch'],
                'photo_url': photo_url,
                'encoding': face_encoding
            }

            ref = firebase_db.reference('students')
            ref.child(usn).set(student_info)

            return jsonify(success=True)
        else:
            return jsonify(success=False, error="No face detected"), 400
    except Exception as e:
        return jsonify(success=False, error=str(e)), 500

@app.route('/attendance', methods=['GET', 'POST'])
def attendance():
    if request.method == 'POST':
        data = request.get_json()
        photo_data = data['photo']
        attendance_records = process_attendance(photo_data)
        return jsonify(attendance_records)

    return render_template('attendance.html')

def process_attendance(photo_data):
    header, encoded = photo_data.split(',', 1)
    img_data = base64.b64decode(encoded)
    np_arr = np.frombuffer(img_data, np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    faces = detector(frame)
    attendance_records = []

    for face in faces:
        shape = predictor(frame, face)
        face_encoding = np.array(face_encoder.compute_face_descriptor(frame, shape)).tolist()

        matched_student = match_face(face_encoding)
        if matched_student:
            usn = matched_student['usn']
            if mark_attendance(usn):
                attendance_records.append({
                    'name': matched_student['name'],
                    'usn': usn,
                    'year': matched_student['year'],
                    'branch': matched_student['branch'],
                    'status': 'Present'
                })
            else:
                attendance_records.append({
                    'name': matched_student['name'],
                    'usn': usn,
                    'year': matched_student['year'],
                    'branch': matched_student['branch'],
                    'status': 'Already Present'
                })

    return attendance_records

def match_face(face_encoding):
    ref = firebase_db.reference('students')
    students = ref.get()

    for usn, student in students.items():
        stored_encoding = student.get('encoding')
        if stored_encoding is not None:
            if np.linalg.norm(np.array(stored_encoding) - np.array(face_encoding)) < 0.6:
                return {
                    'name': student['name'],
                    'usn': usn,
                    'year': student['year'],
                    'branch': student['branch']
                }
    
    return None

def mark_attendance(usn):
    current_time = datetime.now().timestamp()
    
    if usn in last_attendance_time:
        time_since_last_mark = current_time - last_attendance_time[usn]
        if time_since_last_mark < ALLOWED_ATTENDANCE_TIMEFRAME:
            return False  # Already marked within the timeframe

    last_attendance_time[usn] = current_time

    # Record attendance in Firebase Realtime Database
    attendance_ref = firebase_db.reference('attendance')
    attendance_ref.child(usn).push({
        'timestamp': datetime.now().isoformat()
    })

    return True

@app.route('/attendance_report', methods=['GET'])
def attendance_report():
    # Retrieve attendance data from Firebase
    attendance_ref = firebase_db.reference('attendance')
    attendance_data = attendance_ref.get()  # This should return a dictionary

    report = []

    # Retrieve student information from Firebase
    students_ref = firebase_db.reference('students')
    students_data = students_ref.get()  # This should also return a dictionary

    if attendance_data and students_data:
        for usn, records in attendance_data.items():
            # Ensure records is iterable (like a list)
            if isinstance(records, dict):
                for record_key, record in records.items():
                    # Assuming record contains a timestamp field
                    if isinstance(record, dict) and 'timestamp' in record:
                        student_info = students_data.get(usn, {})
                        timestamp = record['timestamp']
                        report.append({
                            'usn': usn,
                            'name': student_info.get('name', 'Unknown'),
                            'year': student_info.get('year', 'Unknown'),
                            'branch': student_info.get('branch', 'Unknown'),
                            'date': timestamp.split("T")[0],  # Format date
                            'time': timestamp.split("T")[1].split(".")[0],  # Format time
                            'status': 'Present'  # Or whatever your logic dictates
                        })

    return render_template('attendancereport.html', attendance_records=report)

@app.route('/logout')
def logout():
    # Here, clear the session or perform any other logout operations
    session.clear()  # Clear the session
    return render_template('teacherlogin.html')  # Redirect to the login page


@app.route('/student_details', methods=['GET'])
def student_details():
    student_data = []
    ref = firebase_db.reference('students')  # Adjust the path according to your Firebase structure
    records = ref.get()

    if records:
        for usn, details in records.items():
            student_data.append({
                'usn': usn,
                'name': details.get('name', 'N/A'),
                'branch': details.get('branch', 'N/A'),
                'year': details.get('year', 'N/A')
            })

    return render_template('studentdetails.html', students=student_data)


if __name__ == '__main__':
    app.run(debug=True)  
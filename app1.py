from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import cv2
from ultralytics import YOLO
from datetime import datetime
import winsound
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Secret key for session management
DATABASE = 'users.db'

# Load the pre-trained YOLO model
model = YOLO('best (5).pt')
cap = cv2.VideoCapture(0)

# Thresholds for crowd detection
crowd_thresholds = {
    "normal": 5,
    "medium": 15,
    "hard": 50
}
last_person_count = 0
current_counts = {"people": 0, "cars": 0, "motorcycles": 0, "crowd_level": "normal"}

def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Initialize the database and default users if not exist
def init_db():
    if not os.path.exists(DATABASE):
        with sqlite3.connect(DATABASE) as conn:
            conn.execute('''CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)''')
    
    with sqlite3.connect(DATABASE) as conn:
        admin_exists = conn.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
        if not admin_exists:
            conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                         ('admin', generate_password_hash('admin123'), 'admin'))

        staf_exists = conn.execute("SELECT * FROM users WHERE username = 'staf'").fetchone()
        if not staf_exists:
            conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                         ('staf', generate_password_hash('staf1234'), 'staf'))

init_db()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        role = 'mahasiswa'  # Default role for new users
        try:
            with sqlite3.connect(DATABASE) as conn:
                conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, role))
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists. Try another one.')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect(DATABASE) as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            if session['role'] in ['admin', 'staf']:
                return redirect(url_for('index'))
            else:
                return redirect(url_for('index_user'))  # Redirect to index_user.html for other roles
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))  # Redirect to login if not logged in
    if session['role'] in ['admin', 'staf']:
        return render_template('index.html')  # Render index.html for admin/staf
    else:
        return redirect(url_for('index_user'))  # Redirect to index_user.html for other roles

@app.route('/index_user')
def index_user():
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))
    return render_template('index_user.html')  # Render index_user.html for mahasiswa

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))
    elif session['role'] not in ['admin', 'staf']:
        flash('Access denied: Admins and Staff only.')
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/laporan')
def laporan():
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))
    return render_template('laporan.html')

@app.route('/laporan_user')
def laporan_user():
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))
    return render_template('laporan_user.html')  # Render laporan_user.html for mahasiswa

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/data')
def data():
    return jsonify(current_counts)

def gen_frames():
    global last_person_count, current_counts
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Apply YOLO detection on the frame
        results = model(frame)
        orang_count, mobil_count, motor_count = 0, 0, 0

        for result in results:
            for detection in result.boxes.data:
                label = result.names[int(detection[5])]
                if label == "ORANG":
                    orang_count += 1
                elif label == "MOBIL":
                    mobil_count += 1
                elif label == "MOTOR":
                    motor_count += 1

            annotated_frame = result.plot()

        current_counts["people"] = orang_count
        current_counts["cars"] = mobil_count
        current_counts["motorcycles"] = motor_count

        if orang_count <= crowd_thresholds["normal"]:
            current_counts["crowd_level"] = "normal"
        elif orang_count <= crowd_thresholds["medium"]:
            current_counts["crowd_level"] = "medium"
        else:
            current_counts["crowd_level"] = "hard"

        if orang_count > last_person_count:
            winsound.Beep(1000, 200)

        last_person_count = orang_count
        current_time = get_current_time()

        cv2.putText(annotated_frame, f"Jumlah Orang: {orang_count}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f"Jumlah Mobil: {mobil_count}", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f"Jumlah Motor: {motor_count}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(annotated_frame, f"Waktu: {current_time}", (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        cv2.putText(annotated_frame, f"Tingkat Keramaian: {current_counts['crowd_level']}", (10, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        if current_counts["crowd_level"] == "hard":
            cv2.putText(annotated_frame, "Kerumunan Terdeteksi!", (10, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

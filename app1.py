import logging
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

# Set up logging
logging.basicConfig(level=logging.DEBUG)  # Logs all levels of messages (DEBUG, INFO, WARNING, ERROR)

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
# Database initialization function
def init_db():
    if not os.path.exists(DATABASE):
        with sqlite3.connect(DATABASE) as conn:
            # Create the users table with a nim column
            conn.execute('''CREATE TABLE users (
                                id INTEGER PRIMARY KEY,
                                nim TEXT UNIQUE,
                                username TEXT UNIQUE,
                                password TEXT,
                                role TEXT
                            )''')
            logging.info("Database created with NIM field.")

    with sqlite3.connect(DATABASE) as conn:
        try:
            # Check if admin user exists
            admin_exists = conn.execute("SELECT * FROM users WHERE username = 'admin'").fetchone()
            if not admin_exists:
                conn.execute("INSERT INTO users (nim, username, password, role) VALUES (?, ?, ?, ?)", 
                             ('00000001', 'admin', generate_password_hash('admin123'), 'admin'))
                logging.info("Admin user created.")

            # Check if staf user exists
            staf_exists = conn.execute("SELECT * FROM users WHERE username = 'staf'").fetchone()
            if not staf_exists:
                conn.execute("INSERT INTO users (nim, username, password, role) VALUES (?, ?, ?, ?)", 
                             ('00000002', 'staf', generate_password_hash('staf1234'), 'staf'))
                logging.info("Staff user created.")

        except sqlite3.DatabaseError as e:
            logging.error(f"Database error during initialization: {e}")
            raise

# Run the initialization
init_db()

# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nim = request.form['nim']  # Capture the NIM from the form
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        role = 'mahasiswa'  # Default role for new users
        
        try:
            with sqlite3.connect(DATABASE) as conn:
                conn.execute("INSERT INTO users (nim, username, password, role) VALUES (?, ?, ?, ?)", (nim, username, password, role))
                logging.info(f"New user registered: {username} with NIM {nim}")
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError as e:
            flash('Username or NIM already exists. Try another one.')
            logging.error(f"Registration error: {e}")
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            with sqlite3.connect(DATABASE) as conn:
                user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if user and check_password_hash(user[3], password):
                session['user_id'] = user[0]
                session['username'] = user[2]
                session['role'] = user[4]
                logging.info(f"User {username} logged in successfully.")
                if session['role'] in ['admin', 'staf']:
                    return redirect(url_for('index'))
                else:
                    return redirect(url_for('index_user'))  # Redirect to index_user.html for other roles
            else:
                flash('Invalid username or password')
                logging.warning(f"Failed login attempt for username: {username}")
        except Exception as e:
            flash('An error occurred while processing your login.')
            logging.error(f"Login error: {e}")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    logging.info(f"User {session.get('username', 'unknown')} logged out.")
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

@app.route('/view_users')
def view_users():
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))

    if session['role'] not in ['admin', 'staf']:  # Only allow admin and staff to view users
        flash('Access denied: Admins and Staff only.')
        return redirect(url_for('index'))  # Redirect to the index for other roles

    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")  # Fetch all users
            users = cursor.fetchall()  # Get all results
            logging.info("Fetched user data successfully.")
    except Exception as e:
        logging.error(f"Error fetching user data: {e}")
        flash('An error occurred while fetching data.')

    return render_template('view_users.html', users=users)

@app.route('/edit_user/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))

    if session['role'] not in ['admin', 'staf']:
        flash('Access denied: Admins and Staff only.')
        return redirect(url_for('index'))

    try:
        with sqlite3.connect(DATABASE) as conn:
            if request.method == 'POST':
                nim = request.form['nim']
                username = request.form['username']
                password = generate_password_hash(request.form['password'])
                role = request.form['role']

                conn.execute("UPDATE users SET nim = ?, username = ?, password = ?, role = ? WHERE id = ?",
                             (nim, username, password, role, id))
                logging.info(f"User with ID {id} updated successfully.")
                flash('User updated successfully!')
                return redirect(url_for('view_users'))

            user = conn.execute("SELECT * FROM users WHERE id = ?", (id,)).fetchone()
            if user is None:
                flash('User not found.')
                return redirect(url_for('view_users'))

    except Exception as e:
        logging.error(f"Error editing user: {e}")
        flash('An error occurred while editing the user.')

    return render_template('edit_user.html', user=user)

@app.route('/delete_user/<int:id>', methods=['POST'])
def delete_user(id):
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))

    if session['role'] not in ['admin', 'staf']:
        flash('Access denied: Admins and Staff only.')
        return redirect(url_for('index'))

    try:
        with sqlite3.connect(DATABASE) as conn:
            conn.execute("DELETE FROM users WHERE id = ?", (id,))
            logging.info(f"User with ID {id} deleted successfully.")
            flash('User deleted successfully!')
    except Exception as e:
        logging.error(f"Error deleting user: {e}")
        flash('An error occurred while deleting the user.')

    return redirect(url_for('view_users'))

def gen_frames():
    global last_person_count, current_counts
    while True:
        ret, frame = cap.read()
        if not ret:
            logging.error("Failed to capture frame from video feed.")
            break

        try:
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
        except Exception as e:
            logging.error(f"Error in video stream processing: {e}")
            break

if __name__ == "__main__":
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
        logging.info("Flask app is running.")
    except Exception as e:
        logging.error(f"Error starting the Flask app: {e}")

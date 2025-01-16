import logging
from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import cv2
from ultralytics import YOLO
from datetime import datetime
import winsound
import os
import threading
import time
from flask import send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Secret key for session management
DATABASE = 'keramaian.db'

# Set up logging
logging.basicConfig(level=logging.DEBUG)  # Logs all levels of messages (DEBUG, INFO, WARNING, ERROR)

# Load the pre-trained YOLO model
model = YOLO('best (8).pt')
# Model Camera Laptop   
 # IP dari aplikasi kamera HP
cap = cv2.VideoCapture(0)
# cap.set(cv2.CAP_PROP_FPS, 10)


# cap = cv2.VideoCapture(0)
# cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
# cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

#  Model Camera CCTV
# cap = cv2.VideoCapture('rtsp://admin:admin@10.3.1.210:8554/Streaming/Channels/102')
cap.set(cv2.CAP_PROP_FPS, 10)


# Thresholds for crowd detection
crowd_thresholds = {
    "normal": 1,
    "medium": 2,
    "hard": 3
}
last_person_count = 0
current_counts = {"orang": 0, "mobil": 0, "motor": 0, "tingkat_keramaian": "normal"}

def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
# Database initialization function
def init_db():
    # Ensure the database file exists before inserting any data
    if not os.path.exists(DATABASE):
        with sqlite3.connect(DATABASE) as conn:
            try:
                # Create the 'users' and 'deteksi' tables
                conn.execute('''CREATE TABLE users (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    nim TEXT UNIQUE,
                                    username TEXT UNIQUE,
                                    password TEXT,
                                    role TEXT
                                )''')
                conn.execute('''CREATE TABLE deteksi (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    orang INTEGER,
                                    mobil INTEGER,
                                    motor INTEGER,
                                    gambar TEXT,
                                    waktu TEXT,
                                    tingkat_keramaian TEXT
                                )''')
                logging.info("Database created with 'users' and 'deteksi' tables.")
            except sqlite3.DatabaseError as e:
                logging.error(f"Error creating tables: {e}")
                raise
        
def insert_detection_data(orang_count, mobil_count, motor_count, gambar, timestamp, crowd_level):
    try:
        with sqlite3.connect(DATABASE) as conn:
            conn.execute('''INSERT INTO deteksi (orang, mobil, motor, gambar, waktu, tingkat_keramaian) 
                            VALUES (?, ?, ?, ?, ?, ?)''', 
                         (orang_count, mobil_count, motor_count, gambar, timestamp, crowd_level))
            logging.info("Detection data inserted into the database.")
    except sqlite3.DatabaseError as e:
        logging.error(f"Error inserting detection data: {e}")



    # Now insert default data if the tables exist
    with sqlite3.connect(DATABASE) as conn:
        try:
            # Verify that the 'users' table exists
            admin_exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';").fetchone()
            if admin_exists:
                # Insert default admin user if not present
                if not conn.execute("SELECT * FROM users WHERE username = 'admin'").fetchone():
                    conn.execute("INSERT INTO users (nim, username, password, role) VALUES (?, ?, ?, ?)", 
                                 ('00000001', 'admin', generate_password_hash('admin123'), 'admin'))
                    logging.info("Admin user created.")

                # Insert default staff user if not present
                if not conn.execute("SELECT * FROM users WHERE username = 'staf'").fetchone():
                    conn.execute("INSERT INTO users (nim, username, password, role) VALUES (?, ?, ?, ?)", 
                                 ('00000002', 'staf', generate_password_hash('staf1234'), 'staf'))
                    logging.info("Staff user created.")
            else:
                logging.error("Table 'users' does not exist.")
        except sqlite3.DatabaseError as e:
            logging.error(f"Error inserting default users: {e}")
            raise


if __name__ == '__main__':
    init_db()
    logging.info("Database initialized.")
    
#BACKEND
def gen_frames_and_save_periodically():
    global last_person_count, current_counts, last_save_time, frame_count
    cap = cv2.VideoCapture(0)  # Assuming video capture device (camera)

    if not cap.isOpened():
        logging.error("Failed to open video capture.")
        return

    last_save_time = time.time()  # Waktu terakhir data disimpan
    frame_count = 0  # Hitung jumlah frame

    while True:
        ret, frame = cap.read()
        if not ret:
            logging.error("Failed to capture frame from video feed.")
            break

        frame_count += 1
        if frame_count % 5 != 0:  # Process every 5 frames
            continue

        try:
            # Process YOLO (detection)
            results = model(frame)
            orang_count, mobil_count, motor_count = 0, 0, 0
            annotated_frame = frame  # Default to the original frame

            # Detect objects in the frame
            for result in results:
                for detection in result.boxes.data:
                    label = result.names[int(detection[5])]
                    if label == "ORANG":
                        orang_count += 1
                    elif label == "MOBIL":
                        mobil_count += 1
                    elif label == "MOTOR":
                        motor_count += 1

                annotated_frame = result.plot()  # Annotate the frame

            # Determine crowd level
            crowd_level = "normal"
            if orang_count <= crowd_thresholds["normal"]:
                crowd_level = "normal"
            elif orang_count <= crowd_thresholds["medium"]:
                crowd_level = "medium"
            else:
                crowd_level = "hard"

            # Update current counts
            current_counts["orang"] = orang_count
            current_counts["mobil"] = mobil_count
            current_counts["motor"] = motor_count
            current_counts["tingkat_keramaian"] = crowd_level
            current_time = get_current_time()

            # Notifications if the count exceeds threshold
            if orang_count > 1:
                logging.warning(f"Keramaian Terdeteksi: {orang_count} orang.")
                cv2.putText(annotated_frame, f"Notif: {orang_count} Orang Terdeteksi!", (10, 280), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                winsound.Beep(2000, 500)

            if mobil_count > 2:
                logging.warning(f"Keramaian Terdeteksi: {mobil_count} mobil.")
                cv2.putText(annotated_frame, f"Notif: {mobil_count} Mobil Terdeteksi!", (10, 320), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)
                winsound.Beep(1500, 500)

            if motor_count > 2:
                logging.warning(f"Keramaian Terdeteksi: {motor_count} motor.")
                cv2.putText(annotated_frame, f"Notif: {motor_count} Motor Terdeteksi!", (10, 360), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                winsound.Beep(1000, 500)

            # Save data every 30 seconds
            if time.time() - last_save_time >= 30:
                gambar = save_detected_image(annotated_frame)
                insert_detection_data(orang_count, mobil_count, motor_count, gambar, current_time, crowd_level)
                last_save_time = time.time()
                logging.info(f"Data saved at {current_time}")

            # Sound alert if the person count increases
            if orang_count > last_person_count:
                winsound.Beep(1000, 200)

            last_person_count = orang_count

            # Annotate the frame with detected counts and time
            cv2.putText(annotated_frame, f"Jumlah Orang: {orang_count}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(annotated_frame, f"Jumlah Mobil: {mobil_count}", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(annotated_frame, f"Jumlah Motor: {motor_count}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(annotated_frame, f"Waktu: {current_time}", (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.putText(annotated_frame, f"Tingkat Keramaian: {crowd_level}", (10, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

            # Encode the frame for streaming
            ret, buffer = cv2.imencode('.jpg', annotated_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if not ret:
                logging.error("Failed to encode frame.")
                break

            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        except Exception as e:
            logging.error(f"Error in video stream processing: {e}")
            break

    cap.release()


# if crowd_level == "medium":
            #     cv2.putText(annotated_frame, "Kerumunan Terdeteksi!", (10, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
def save_detected_image(frame):
    # Generate timestamp untuk nama file unik
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f'detection_{timestamp}.jpg'
    save_path = os.path.join('static', 'img', filename)

    # Pastikan folder 'static/img/' ada
    if not os.path.exists(os.path.dirname(save_path)):
        os.makedirs(os.path.dirname(save_path))

    # Simpan gambar
    cv2.imwrite(save_path, frame)
    logging.info(f"Image saved at {save_path}")
    return filename  # Hanya kembalikan nama file




# Misalkan ini adalah fungsi yang mengembalikan data
def get_data_from_db():
    # Kode untuk mengambil data dari database
    return [
        # Contoh data
        [1, 50, 10, "image1.jpg", datetime.now(), "2024-11-17 12:00", "Ramah"],
        [2, 30, 5, "image2.jpg", datetime.now(), "2024-11-17 12:01", "Ramah"],
        # Tambahkan lebih banyak entri sesuai kebutuhan
    ]

# Ambil data dari fungsi
data = get_data_from_db()

# Sekarang Anda bisa mengurutkan dan memanipulasi data
data.sort(key=lambda entry: entry[5], reverse=True)  # Mengurutkan berdasarkan waktu

# Pagination
items_per_page = 10
total_items = len(data)
total_pages = (total_items + items_per_page - 1) // items_per_page

# Ambil halaman yang diminta (misal dari query string)
current_page = 1  # Misalnya ini dari parameter URL
start_index = (current_page - 1) * items_per_page
end_index = start_index + items_per_page

# Ambil data untuk halaman saat ini
paged_data = data[start_index:end_index]

# Render data pada template
for entry in paged_data:
    print(entry)  # Ganti dengan cara Anda menampilkan data di template


# Data Setiap 30 detik dan dihitung setiap 2 menit



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
            # Open a connection to the database
            with sqlite3.connect(DATABASE) as conn:
                user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            
            if user and check_password_hash(user[3], password):  # Assuming the password is at index 3
                session['user_id'] = user[0]  # Storing user_id in session
                session['username'] = user[2]  # Storing username in session
                session['role'] = user[4]  # Storing role in session
                logging.info(f"User {username} logged in successfully.")
                
                # Flash success message
                flash('Login successful! Welcome back.', 'success')
                
                # Redirect based on role
                if session['role'] in ['admin', 'staf']:
                    return redirect(url_for('index'))  # Redirect to admin/staff index page
                else:
                    return redirect(url_for('index_user'))  # Redirect to user-specific page for other roles
            else:
                flash('Invalid username or password', 'danger')  # Error flash for invalid login
                logging.warning(f"Failed login attempt for username: {username}")
        except Exception as e:
            flash('An error occurred while processing your login.', 'danger')  # Error handling with flash
            logging.error(f"Login error: {e}")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah keluar.')
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

@app.route('/user')
def user_page():
    return render_template('user.html')

@app.route('/about')
def about_page():
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))
    return render_template('about.html')

@app.route('/contact')
def contact_page():
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))
    return render_template('contact.html')

# @app.route('/laporan1')
# def laporan_user1_page():
#     return render_template('laporan_user1.html')

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
    
    # Check if the user has the correct role
    elif session['role'] not in ['admin', 'staf']:
        flash('Access denied: Admins and Staff only.')
        return redirect(url_for('index'))

    try:
        per_page = 10  # Number of items per page
        current_page = int(request.args.get('page', 1))  # Get the current page from query parameter
        
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM deteksi")  # Count total data
            total_data = cursor.fetchone()[0]

            total_pages = (total_data + per_page - 1) // per_page  # Calculate total pages
            offset = (current_page - 1) * per_page  # Calculate the offset for the current page

            # Fetch data for the current page, ordered by id (newest first)
            cursor.execute(
                "SELECT * FROM deteksi ORDER BY id DESC LIMIT ? OFFSET ?", 
                (per_page, offset)
            )
            data = cursor.fetchall()

            # Update the image path
            for i in range(len(data)):
                data[i] = list(data[i])  # Convert tuple to list
                data[i][4] = f"/static/img/{data[i][4].split('/')[-1]}"  # Update image path

            logging.info("Fetched detection data successfully.")
        
        # Calculate the starting number for pagination
        start_number = (current_page - 1) * per_page + 1
    except Exception as e:
        logging.error(f"Error fetching detection data: {e}")
        flash('An error occurred while fetching data.')
        data = []
        total_pages = 0
        current_page = 1
        start_number = 1

    return render_template(
        'laporan.html',
        data=data,
        total_pages=total_pages,
        current_page=current_page,
        start_number=start_number  # Pass the starting number to the template
    )




@app.route('/laporan_user')
def laporan_user():
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))
    
    try:
        per_page = 10  # Number of items per page
        current_page = int(request.args.get('page', 1))  # Get the current page from query parameter
        
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM deteksi")  # Count total data
            total_data = cursor.fetchone()[0]

            total_pages = (total_data + per_page - 1) // per_page  # Calculate total pages
            offset = (current_page - 1) * per_page  # Calculate the offset for the current page

            # Fetch data for the current page, ordered by id (newest first)
            cursor.execute(
                "SELECT * FROM deteksi ORDER BY id DESC LIMIT ? OFFSET ?", 
                (per_page, offset)
            )
            data = cursor.fetchall()

            # Update the image path
            for i in range(len(data)):
                data[i] = list(data[i])  # Convert tuple to list
                data[i][4] = f"/static/img/{data[i][4].split('/')[-1]}"  # Update image path

            logging.info("Fetched detection data successfully.")
        
        # Calculate the starting number for pagination
        start_number = (current_page - 1) * per_page + 1
    except Exception as e:
        logging.error(f"Error fetching detection data: {e}")
        flash('An error occurred while fetching data.')
        data = []
        total_pages = 0
        current_page = 1
        start_number = 1

    return render_template(
        'laporan_user.html',
        data=data,
        total_pages=total_pages,
        current_page=current_page,
        start_number=start_number  # Pass the starting number to the template
    ) # Render laporan_user.html for ma  hasiswa

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames_and_save_periodically(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/data')
def data():
    # Periksa jika kondisi keramaian terpenuhi untuk masing-masing kategori
    is_alert_orang = current_counts["orang"] > 1  # True jika lebih dari 2 orang terdeteksi
    is_alert_mobil = current_counts["mobil"] > 2  # True jika lebih dari 2 mobil terdeteksi
    is_alert_motor = current_counts["motor"] > 2  # True jika lebih dari 2 motor terdeteksi

    # Tambahkan status alert ke data respons
    response = {
        "orang": current_counts["orang"],
        "mobil": current_counts["mobil"],
        "motor": current_counts["motor"],
        "tingkat_keramaian": current_counts["tingkat_keramaian"],
        "is_alert_orang": is_alert_orang,  # True jika lebih dari 2 orang
        "is_alert_mobil": is_alert_mobil,  # True jika lebih dari 2 mobil
        "is_alert_motor": is_alert_motor  # True jika lebih dari 2 motor
    }
    return jsonify(response)


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
@app.route('/tambah_data', methods=['GET', 'POST'])
def tambah_data():
    # Periksa apakah pengguna sudah login
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))
    
    # Periksa apakah peran pengguna adalah admin atau staf
    if session['role'] not in ['admin', 'staf']:
        flash('Access denied: Admins and Staff only.')
        return redirect(url_for('index'))  # Redirect ke halaman index jika peran tidak sesuai

    if request.method == 'POST':
        nim = request.form['nim']  # Ambil NIM dari form
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        role = request.form.get('role')  # Ambil role dari form
        
        # Validasi role
        if role not in ['admin', 'staf', 'mahasiswa']:
            flash('Invalid role selected.')
            return redirect(url_for('tambah_data'))

        try:
            with sqlite3.connect(DATABASE) as conn:
                conn.execute("INSERT INTO users (nim, username, password, role) VALUES (?, ?, ?, ?)", (nim, username, password, role))
                logging.info(f"New user registered: {username} with NIM {nim} and Role {role}")
            flash('Registration successful!')
            return redirect(url_for('view_users'))  # Arahkan kembali ke halaman view_users
        except sqlite3.IntegrityError as e:
            flash('Username or NIM already exists. Try another one.')
            logging.error(f"Tambah data error: {e}")
    
    return render_template('tambah_data.html')


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

from flask import request, jsonify

# Rute untuk menghapus semua data
@app.route('/delete_all', methods=['POST'])
def delete_all():
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))

    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM deteksi")  # Hapus semua data
            conn.commit()
        logging.info("All entries deleted successfully.")
        flash("Semua entri berhasil dihapus.")
    except Exception as e:
        logging.error(f"Error deleting all entries: {e}")
        flash("Terjadi kesalahan saat menghapus semua entri.")
    return redirect(url_for('laporan'))


# Rute untuk menghapus satu entri berdasarkan ID
@app.route('/delete/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    if 'user_id' not in session:
        flash('Please log in to access this page.')
        return redirect(url_for('login'))

    try:
        with sqlite3.connect(DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM deteksi WHERE id = ?", (entry_id,))  # Hapus data berdasarkan ID
            conn.commit()
        logging.info(f"Entry with ID {entry_id} deleted successfully.")
        flash(f"Entri dengan ID {entry_id} berhasil dihapus.")
    except Exception as e:
        logging.error(f"Error deleting entry {entry_id}: {e}")
        flash("Terjadi kesalahan saat menghapus entri.")
    return redirect(url_for('laporan'))

@app.route('/download_pdf/<int:entry_id>', methods=['GET'])
def download_pdf(entry_id):
    # Ambil data dari database berdasarkan entry_id
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM deteksi WHERE id = ?", (entry_id,))
        entry = cursor.fetchone()

    if entry is None:
        flash("Data tidak ditemukan.")
        return redirect(url_for('laporan'))

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    elements = []

    # Header tabel
    data = [["Kolom", "Detail"]]

    # Gambar
    image_path = os.path.join("static", "img", entry[4].split("/")[-1])
    if os.path.exists(image_path):
        img = Image(image_path, width=100, height=100)  # Atur ukuran gambar
    else:
        img = "Gambar Tidak Ditemukan"

    # Tambahkan data ke tabel
    data.extend([
        ["ID", str(entry[0])],
        ["Jumlah Orang", str(entry[1])],
        ["Jumlah Mobil", str(entry[2])],
        ["Jumlah Motor", str(entry[3])],
        ["Gambar", img],
        ["Waktu", str(entry[5])],
        ["Tingkat Keramaian", str(entry[6])]
    ])

    # Buat objek tabel
    table = Table(data, colWidths=[150, 300])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.blue),  # Header background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  # Header text color
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Center align all text
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Header font
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  # Padding for header
        ('GRID', (0, 0), (-1, -1), 1, colors.black),  # Add grid lines
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),  # Row background
    ]))

    elements.append(table)

    # Build PDF
    doc.build(elements)
    pdf_buffer.seek(0)

    # Kirim PDF ke pengguna
    return send_file(pdf_buffer, as_attachment=True, download_name=f'laporan_{entry_id}.pdf', mimetype='application/pdf')


@app.route('/download_all_pdf', methods=['POST'])
def download_all_pdf():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM deteksi")
        entries = cursor.fetchall()

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    elements = []

    # Header tabel
    data = [["No", "Jumlah Orang", "Jumlah Mobil", "Jumlah Motor", "Gambar", "Waktu", "Tingkat Keramaian"]]

    # Tambahkan data ke tabel
    for index, entry in enumerate(entries):
        # Ambil path gambar
        image_path = os.path.join("static", "img", entry[4].split("/")[-1])
        if os.path.exists(image_path):
            img = Image(image_path, width=50, height=50)  # Atur ukuran gambar
        else:
            img = "Gambar Tidak Ditemukan"

        data.append([
            str(index + 1),  # No
            str(entry[1]),   # Jumlah Orang
            str(entry[2]),   # Jumlah Mobil
            str(entry[3]),   # Jumlah Motor
            img,             # Gambar
            str(entry[5]),   # Waktu
            str(entry[6])    # Tingkat Keramaian
        ])

    # Buat objek tabel
    table = Table(data, colWidths=[30, 70, 70, 70, 70, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.blue),  # Header background
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  # Header text color
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Center align all text
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Header font
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),  # Padding for header
        ('GRID', (0, 0), (-1, -1), 1, colors.black),  # Add grid lines
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),  # Row background
    ]))

    elements.append(table)

    # Build PDF
    doc.build(elements)
    pdf_buffer.seek(0)

    return send_file(pdf_buffer, as_attachment=True, download_name='laporan_semua_data.pdf', mimetype='application/pdf')



if __name__ == "__main__":
    try:
        # Jalankan thread untuk menyimpan data setiap 30 detik
        threading.Thread(target=gen_frames_and_save_periodically, daemon=True).start()
        
        # Jalankan aplikasi Flask
        app.run(debug=True, host='0.0.0.0', port=5000)
        logging.info("Flask app is running.")
    except Exception as e:
        logging.error(f"Error starting the Flask app: {e}")

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
DATABASE = 'keramaian.db'

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

            # Loop through the detection results
            for result in results:
                for detection in result.boxes.data:
                    label = result.names[int(detection[5])]
                    if label == "ORANG":
                        orang_count += 1
                    elif label == "MOBIL":
                        mobil_count += 1
                    elif label == "MOTOR":
                        motor_count += 1

                # Ensure annotated_frame is assigned correctly
                annotated_frame = result.plot()

            # Save detected image
            gambar = save_detected_image(annotated_frame)

            # Get the current timestamp
            current_time = get_current_time()

            # Set the crowd level based on the number of people detected
            if orang_count <= crowd_thresholds["normal"]:
                crowd_level = "normal"
            elif orang_count <= crowd_thresholds["medium"]:
                crowd_level = "medium"
            else:
                crowd_level = "hard"

            # Insert detection data into the database
            insert_detection_data(orang_count, mobil_count, motor_count, gambar, current_time, crowd_level)

            # Update current counts
            current_counts["orang"] = orang_count
            current_counts["mobil"] = mobil_count
            current_counts["motor"] = motor_count
            current_counts["tingkat_keramaian"] = crowd_level

            # Sound alert if the number of people increases
            if orang_count > last_person_count:
                winsound.Beep(1000, 200)

            # Update the last person count
            last_person_count = orang_count

            # Add text annotations to the frame
            cv2.putText(annotated_frame, f"Jumlah Orang: {orang_count}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(annotated_frame, f"Jumlah Mobil: {mobil_count}", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(annotated_frame, f"Jumlah Motor: {motor_count}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(annotated_frame, f"Waktu: {current_time}", (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
            cv2.putText(annotated_frame, f"Tingkat Keramaian: {crowd_level}", (10, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

            if crowd_level == "hard":
                cv2.putText(annotated_frame, "Kerumunan Terdeteksi!", (10, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # Encode frame to bytes for streaming
            ret, buffer = cv2.imencode('.jpg', annotated_frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        except Exception as e:
            logging.error(f"Error in video stream processing: {e}")
            break

# def save_detected_image(frame):
#     # Generate timestamp untuk nama file unik
#     timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
#     filename = f'detection_{timestamp}.jpg'
#     save_path = os.path.join('static', 'img', filename)

#     # Pastikan folder 'static/img/' ada
#     if not os.path.exists(os.path.dirname(save_path)):
#         os.makedirs(os.path.dirname(save_path))

#     # Simpan gambar
#     cv2.imwrite(save_path, frame)
#     logging.info(f"Image saved at {save_path}")
#     return filename  # Hanya kembalikan nama file




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



if __name__ == "__main__":
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
        logging.info("Flask app is running.")
    except Exception as e:
        logging.error(f"Error starting the Flask app: {e}")

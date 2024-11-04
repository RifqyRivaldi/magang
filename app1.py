from flask import Flask, render_template, Response, jsonify
import cv2
from ultralytics import YOLO
from datetime import datetime
import winsound  # Import for sound (Windows)

app = Flask(__name__)

# Load the pre-trained YOLO model
model = YOLO('best (5).pt')

# Open video stream from the default camera
cap = cv2.VideoCapture(0)

# Thresholds for crowd detection
crowd_thresholds = {
    "normal": 5,
    "medium": 15,
    "hard": 50
}
last_person_count = 0  # To store the last person count
current_counts = {"people": 0, "cars": 0, "motorcycles": 0, "crowd_level": "normal"}

def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def gen_frames():
    global last_person_count, current_counts
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Apply YOLO detection on the frame
        results = model(frame)

        orang_count = 0
        mobil_count = 0
        motor_count = 0

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

        # Update current counts
        current_counts["people"] = orang_count
        current_counts["cars"] = mobil_count
        current_counts["motorcycles"] = motor_count

        # Check crowd level
        if orang_count <= crowd_thresholds["normal"]:
            current_counts["crowd_level"] = "normal"
        elif orang_count <= crowd_thresholds["medium"]:
            current_counts["crowd_level"] = "medium"
        else:
            current_counts["crowd_level"] = "hard"

        # Check if there are new people detected
        if orang_count > last_person_count:
            winsound.Beep(1000, 200)

        last_person_count = orang_count

        current_time = get_current_time()

        # Display counts and current time on the frame
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/laporan')
def laporan():
    return render_template('laporan.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/data')
def data():
    # Return the current counts as JSON
    return jsonify(current_counts)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
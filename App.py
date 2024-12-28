
import cv2
import time
from ultralytics import YOLO
from datetime import datetime
import winsound  # Import for sound (Windows)

# Load the pre-trained YOLO model (make sure the model path is correct)
model = YOLO('best (2).pt')

# Open video stream from the default camera
cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Unable to open video stream from the camera.")
    exit()

# Threshold for detecting a crowd (e.g., more than 5 people considered a crowd)
crowd_threshold = 5
last_person_count = 0  # To store the last person count
last_vehicle_count = 0  # To store the last vehicle count (car + motorbike)

# Function to get the current time in a nice format
def get_current_time():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Create a named window and set it to resizable
cv2.namedWindow('Absensi & Deteksi Kerumunan', cv2.WINDOW_NORMAL)

# Variable to track fullscreen mode
fullscreen = False

while True:
    ret, frame = cap.read()
    if not ret:
        print("Error: Unable to read from the camera.")
        break

    # Apply YOLO detection on the frame
    results = model(frame)

    # Initialize ORANG, MOBIL, and MOTOR counts
    orang_count = 0
    mobil_count = 0
    motor_count = 0

    # Process each result
    for result in results:
        # Loop through detected boxes and check the label
        for detection in result.boxes.data:
            label = result.names[int(detection[5])]  # Extract label based on the class index

            # Check for 'ORANG', 'MOBIL', and 'MOTOR' classes by their custom labels
            if label == "ORANG":
                orang_count += 1
            elif label == "MOBIL":
                mobil_count += 1
            elif label == "MOTOR":
                motor_count += 1

        # Render results on the frame
        annotated_frame = result.plot()

    # Get total vehicle count (MOBIL + MOTOR)
    vehicle_count = mobil_count + motor_count

    # Check if there are new people detected
    if orang_count > last_person_count:
        winsound.Beep(1000, 200)  # Beep sound: 1000 Hz for 200 ms

    # Update last person and vehicle count
    last_person_count = orang_count
    last_vehicle_count = vehicle_count

    # Get the current time
    current_time = get_current_time()

    # Display counts and current time on the frame
    cv2.putText(annotated_frame, f"Jumlah Orang: {orang_count}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(annotated_frame, f"Jumlah Mobil: {mobil_count}", (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(annotated_frame, f"Jumlah Motor: {motor_count}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(annotated_frame, f"Waktu: {current_time}", (10, 160), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

    # Check for crowd detection (people count)
    if orang_count > crowd_threshold:
        cv2.putText(annotated_frame, "Kerumunan Terdeteksi!", (10, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    # Display the annotated frame
    cv2.imshow('Absensi & Deteksi Kerumunan', annotated_frame)
    
    # Keyboard controls for window size
    key = cv2.waitKey(1) & 0xFF
    if key == ord('f'):  # Press 'f' to toggle fullscreen
        fullscreen = not fullscreen
        if fullscreen:
            cv2.setWindowProperty('Absensi & Deteksi Kerumunan', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        else:
            cv2.setWindowProperty('Absensi & Deteksi Kerumunan', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)

    if key == ord('q'):  # Press 'q' to exit
        break

# Release the camera and close all open windows
cap.release()
cv2.destroyAllWindows()

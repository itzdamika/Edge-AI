# rpi_http_backend.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import time, threading
import board
import adafruit_dht
import cv2
import base64
from gpiozero import MotionSensor, Button

app = FastAPI()

# --- Enable CORS so that your React dashboard (running on another host/port) can access the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your dashboard domain.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Sensor Initialization -----
# DHT22 on GPIO27 (avoid conflicts on GPIO4)
dhtDevice = adafruit_dht.DHT22(board.D27)

# MQ‑135 digital output (assumed wired to GPIO18)
air_quality_sensor = Button(18)

# HC‑SR501 Motion Sensor (wired to GPIO17)
motion_sensor = MotionSensor(17)

def get_camera_image():
    """Capture one frame from the USB webcam, resize to 320x240, encode as JPEG, and return a base64 string."""
    cap = cv2.VideoCapture(0)  # Use default USB webcam
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    # Resize for smaller payload
    frame = cv2.resize(frame, (320, 240))
    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        return None
    return base64.b64encode(buffer).decode('utf-8')

def read_sensors():
    """Read sensor data and return as a dictionary."""
    data = {}
    # Read DHT22 sensor
    try:
        data['temperature'] = dhtDevice.temperature
        data['humidity'] = dhtDevice.humidity
    except Exception as e:
        print("DHT22 error:", e)
        data['temperature'] = None
        data['humidity'] = None

    # Read MQ‑135 digital output: assume HIGH (pressed) means "Poor"
    try:
        data['air_quality'] = "Poor" if air_quality_sensor.is_pressed else "Good"
    except Exception as e:
        print("Air quality sensor error:", e)
        data['air_quality'] = None

    # Read HC‑SR501 motion sensor
    try:
        data['motion'] = motion_sensor.motion_detected
    except Exception as e:
        print("Motion sensor error:", e)
        data['motion'] = None

    # Capture camera image
    try:
        data['camera_image'] = get_camera_image()
    except Exception as e:
        print("Camera error:", e)
        data['camera_image'] = None

    data['timestamp'] = time.time()
    return data

# Global variable to hold the latest sensor data.
latest_data = {}

def sensor_updater():
    """Periodically update sensor data."""
    global latest_data
    while True:
        latest_data = read_sensors()
        time.sleep(10)  # Update every 10 seconds

# Start background sensor updater
threading.Thread(target=sensor_updater, daemon=True).start()

@app.get("/sensors")
def get_sensor_data():
    """Return the latest sensor data as JSON."""
    return latest_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

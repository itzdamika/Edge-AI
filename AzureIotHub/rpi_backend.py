# rpi_http_backend_pigpio.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import time, threading
import board
import adafruit_dht
import cv2
import base64
import pigpio  # Use pigpio directly for digital I/O

app = FastAPI()

# Enable CORS so that external clients (like your React dashboard) can access the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your trusted domains.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Sensor Initialization -----
# Initialize DHT22 sensor on GPIO27 (to avoid conflicts with GPIO4)
dhtDevice = adafruit_dht.DHT22(board.D27)

# Initialize pigpio (make sure the pigpio daemon is running)
pi = pigpio.pi()
if not pi.connected:
    raise SystemExit("Could not connect to pigpio daemon. Please start it with 'sudo systemctl start pigpiod'.")

# Define GPIO pins for digital sensors
AIR_QUALITY_PIN = 18    # MQ‑135 digital output pin
MOTION_SENSOR_PIN = 17  # HC‑SR501 motion sensor pin

# Set up digital sensor pins with pull-down resistors (adjust if your hardware requires pull-up)
pi.set_mode(AIR_QUALITY_PIN, pigpio.INPUT)
pi.set_pull_up_down(AIR_QUALITY_PIN, pigpio.PUD_DOWN)

pi.set_mode(MOTION_SENSOR_PIN, pigpio.INPUT)
pi.set_pull_up_down(MOTION_SENSOR_PIN, pigpio.PUD_DOWN)

def read_sensors():
    """Read sensor data and return it as a dictionary."""
    data = {}
    # Read DHT22 temperature and humidity
    try:
        data['temperature'] = dhtDevice.temperature
        data['humidity'] = dhtDevice.humidity
    except Exception as e:
        print("DHT22 error:", e)
        data['temperature'] = None
        data['humidity'] = None

    # Read MQ‑135 digital output using pigpio:
    try:
        # pi.read returns 1 if HIGH, 0 if LOW.
        # Assume HIGH means "Poor" air quality.
        aq_val = pi.read(AIR_QUALITY_PIN)
        data['air_quality'] = "Poor" if aq_val == 1 else "Good"
    except Exception as e:
        print("Air quality sensor error:", e)
        data['air_quality'] = None

    # Read HC‑SR501 motion sensor using pigpio:
    try:
        motion_val = pi.read(MOTION_SENSOR_PIN)
        data['motion'] = True if motion_val == 1 else False
    except Exception as e:
        print("Motion sensor error:", e)
        data['motion'] = None

    data['timestamp'] = time.time()
    return data

# Global variable to cache the latest sensor data
latest_data = {}

def sensor_updater():
    """Update sensor data periodically."""
    global latest_data
    while True:
        latest_data = read_sensors()
        time.sleep(2)  # Update every 10 seconds

# Start the background thread to update sensor data
threading.Thread(target=sensor_updater, daemon=True).start()

@app.get("/sensors")
def get_sensor_data():
    """HTTP endpoint to return the latest sensor data."""
    return latest_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
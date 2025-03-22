# rpi_backend.py
from fastapi import FastAPI
import time, json, threading
import board
import adafruit_dht
import cv2
import base64
import paho.mqtt.client as mqtt
import pigpio  # Using pigpio for digital I/O

app = FastAPI()

# ----- Initialize pigpio and check connection -----
pi = pigpio.pi()
if not pi.connected:
    print("Error: Could not connect to pigpio daemon.")
    exit()

# ----- Sensor Initialization -----
# Use GPIO27 for DHT22 (avoid conflicts on GPIO4)
dhtDevice = adafruit_dht.DHT22(board.D27)

# Define pins for digital sensors
AIR_QUALITY_PIN = 18   # MQ‑135 digital output pin
MOTION_SENSOR_PIN = 17  # HC‑SR501 motion sensor pin

# Configure these pins as inputs with a pull-down resistor.
pi.set_mode(AIR_QUALITY_PIN, pigpio.INPUT)
pi.set_pull_up_down(AIR_QUALITY_PIN, pigpio.PUD_DOWN)
pi.set_mode(MOTION_SENSOR_PIN, pigpio.INPUT)
pi.set_pull_up_down(MOTION_SENSOR_PIN, pigpio.PUD_DOWN)

def get_camera_image():
    """Capture one frame from the USB webcam, resize, encode as JPEG, and return as a base64 string."""
    cap = cv2.VideoCapture(0)  # default USB camera
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    # Resize for smaller data size (320x240)
    frame = cv2.resize(frame, (320, 240))
    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        return None
    return base64.b64encode(buffer).decode('utf-8')

def read_sensors():
    """Collect sensor data into a dictionary."""
    data = {}
    # Read temperature and humidity from DHT22
    try:
        data['temperature'] = dhtDevice.temperature
        data['humidity'] = dhtDevice.humidity
    except Exception as e:
        print("DHT22 error:", e)
        data['temperature'] = None
        data['humidity'] = None

    # Read air quality from MQ‑135 using pigpio
    try:
        air_quality_val = pi.read(AIR_QUALITY_PIN)
        # Assume that a HIGH (1) means "Poor" air quality, LOW (0) means "Good"
        data['air_quality'] = "Poor" if air_quality_val == 1 else "Good"
    except Exception as e:
        print("Air quality sensor error:", e)
        data['air_quality'] = None

    # Read motion sensor state from HC‑SR501 using pigpio
    try:
        motion_val = pi.read(MOTION_SENSOR_PIN)
        data['motion'] = True if motion_val == 1 else False
    except Exception as e:
        print("Motion sensor error:", e)
        data['motion'] = None

    # Read camera image
    try:
        data['camera_image'] = get_camera_image()
    except Exception as e:
        print("Camera error:", e)
        data['camera_image'] = None

    data['timestamp'] = time.time()
    return data

# ----- MQTT Publisher Setup -----
MQTT_BROKER = "localhost"  # Use your broker address here (or the Pi's IP if needed)
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/data"

mqtt_client = mqtt.Client()
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

def sensor_publisher():
    """Read sensors periodically and publish the data via MQTT."""
    while True:
        sensor_data = read_sensors()
        payload = json.dumps(sensor_data)
        mqtt_client.publish(MQTT_TOPIC, payload)
        print("Published sensor data:", payload)
        time.sleep(10)  # Publish every 10 seconds

# Start the publisher in a background thread.
threading.Thread(target=sensor_publisher, daemon=True).start()

# Optional: Expose an HTTP endpoint to get sensor data directly.
@app.get("/sensors")
def get_sensor_data():
    return read_sensors()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

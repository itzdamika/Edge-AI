# rpi_backend.py
from fastapi import FastAPI
import time, json, threading
import board
import adafruit_dht
from gpiozero import MotionSensor, Button
import cv2
import base64
import paho.mqtt.client as mqtt

app = FastAPI()

# ----- Sensor Initialization -----
# Use GPIO27 for DHT22 (avoid conflicts on GPIO4)
dhtDevice = adafruit_dht.DHT22(board.D27)

# MQ‑135 digital output (assumed wired to GPIO18)
air_quality_sensor = Button(18)

# HC‑SR501 Motion sensor (wired to GPIO17)
motion_sensor = MotionSensor(17)

def get_camera_image():
    """Capture one frame from the USB webcam, resize, encode as JPEG, and return as base64."""
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
    try:
        data['temperature'] = dhtDevice.temperature
        data['humidity'] = dhtDevice.humidity
    except Exception as e:
        print("DHT22 error:", e)
        data['temperature'] = None
        data['humidity'] = None

    try:
        data['air_quality'] = "Poor" if air_quality_sensor.is_pressed else "Good"
    except Exception as e:
        print("Air quality sensor error:", e)
        data['air_quality'] = None

    try:
        data['motion'] = motion_sensor.motion_detected
    except Exception as e:
        print("Motion sensor error:", e)
        data['motion'] = None

    try:
        data['camera_image'] = get_camera_image()
    except Exception as e:
        print("Camera error:", e)
        data['camera_image'] = None

    data['timestamp'] = time.time()
    return data

# ----- MQTT Publisher Setup -----
MQTT_BROKER = "localhost"  # Use your broker address here
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

# Start the publisher in a background thread
threading.Thread(target=sensor_publisher, daemon=True).start()

# Optional: Expose an HTTP endpoint to get sensor data directly.
@app.get("/sensors")
def get_sensor_data():
    return read_sensors()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

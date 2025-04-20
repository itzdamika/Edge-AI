# Use pigpio's pin factory so we can run without sudo
from gpiozero import Device
from gpiozero.pins.pigpio import PiGPIOFactory
Device.pin_factory = PiGPIOFactory()

import time
import board
import adafruit_dht
from gpiozero import MotionSensor, Button
from azure.iot.device import IoTHubDeviceClient, Message
import cv2
import base64

# Replace with your Azure IoT Hub device connection string
CONNECTION_STRING = "HostName=edgeAI-hub.azure-devices.net;DeviceId=edge-voice-test-device;SharedAccessKey=YOUR_KEY_HERE"

# ---------------------------
# 1. DHT22 Sensor (Temperature & Humidity)
# ---------------------------
# Updated: Connected to GPIO27 (using board.D27) instead of GPIO4.
# Update your wiring: connect DHT22 data line to GPIO27.
dhtDevice = adafruit_dht.DHT22(board.D27)

# ---------------------------
# 2. MQ‑135 Sensor (Air Quality) using Digital Output
# ---------------------------
# Assumes your MQ‑135 module provides a digital output (DO) that you wire to GPIO18.
air_quality_sensor = Button(18)

# ---------------------------
# 3. HC‑SR501 Motion Sensor
# ---------------------------
# Using gpiozero's MotionSensor on GPIO17.
motion_sensor = MotionSensor(17)

# ---------------------------
# 4. USB Webcam (via OpenCV)
# ---------------------------
def get_camera_image():
    """Capture one frame from the USB webcam, resize, encode as JPEG and return a base64 string."""
    cap = cv2.VideoCapture(0)  # Open default camera
    ret, frame = cap.read()
    cap.release()
    if not ret:
        print("Failed to capture image")
        return None
    # Optionally resize (e.g., 320x240) to reduce message size
    frame = cv2.resize(frame, (320, 240))
    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        print("Failed to encode image")
        return None
    return base64.b64encode(buffer).decode('utf-8')

# ---------------------------
# Azure IoT Hub Client Initialization
# ---------------------------
client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)

def get_sensor_data():
    data = {}

    # DHT22: Temperature & Humidity
    try:
        temperature = dhtDevice.temperature
        humidity = dhtDevice.humidity
        data['temperature'] = temperature
        data['humidity'] = humidity
    except Exception as e:
        print("DHT22 error:", e)
        data['temperature'] = None
        data['humidity'] = None

    # MQ‑135: Air Quality (Digital Output)
    try:
        if air_quality_sensor.is_pressed:
            data['air_quality'] = "Poor"
        else:
            data['air_quality'] = "Good"
    except Exception as e:
        print("Air quality sensor error:", e)
        data['air_quality'] = None

    # HC‑SR501: Motion
    try:
        data['motion'] = motion_sensor.motion_detected
    except Exception as e:
        print("Motion sensor error:", e)
        data['motion'] = None

    # USB Webcam: Capture snapshot
    try:
        camera_image = get_camera_image()
        data['camera_image'] = camera_image
    except Exception as e:
        print("Camera error:", e)
        data['camera_image'] = None

    return data

def send_data_to_azure(data):
    try:
        message = Message(str(data))
        client.send_message(message)
        print("Data sent to Azure IoT Hub:", data)
    except Exception as e:
        print("Error sending data to Azure IoT Hub:", e)

def main():
    while True:
        sensor_data = get_sensor_data()
        send_data_to_azure(sensor_data)
        time.sleep(10)  # Wait 10 seconds between readings

if __name__ == "__main__":
    main()

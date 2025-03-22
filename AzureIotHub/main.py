import time
import board
import adafruit_dht
from gpiozero import MotionSensor, Button
from azure.iot.device import IoTHubDeviceClient, Message

# Replace with your Azure IoT Hub device connection string
CONNECTION_STRING = "HostName=edgeAI-hub.azure-devices.net;DeviceId=edge-voice-test-device;SharedAccessKey=YOUR_KEY_HERE"

# ---------------------------
# 1. DHT22 Sensor (Temperature & Humidity)
# ---------------------------
# Connected to GPIO4 (using board.D4)
dhtDevice = adafruit_dht.DHT22(board.D4)

# ---------------------------
# 2. MQ‑135 Sensor (Air Quality) using Digital Output
# ---------------------------
# For a digital sensor output, we use a Button from gpiozero.
# Connect the MQ‑135 module's digital output (DO) to GPIO18.
air_quality_sensor = Button(18)

# ---------------------------
# 3. HC‑SR501 Motion Sensor
# ---------------------------
# Using gpiozero's MotionSensor on GPIO17.
motion_sensor = MotionSensor(17)

# ---------------------------
# Azure IoT Hub Client Initialization
# ---------------------------
client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)

def get_sensor_data():
    data = {}

    # Read temperature and humidity from DHT22 sensor
    try:
        temperature = dhtDevice.temperature
        humidity = dhtDevice.humidity
        data['temperature'] = temperature
        data['humidity'] = humidity
    except Exception as e:
        print("DHT22 error:", e)
        data['temperature'] = None
        data['humidity'] = None

    # Read air quality from MQ‑135 digital output
    try:
        # If the digital output is active (button "pressed"), assume air quality is "Poor".
        if air_quality_sensor.is_pressed:
            data['air_quality'] = "Poor"
        else:
            data['air_quality'] = "Good"
    except Exception as e:
        print("Air quality sensor error:", e)
        data['air_quality'] = None

    # Read motion detection from HC‑SR501 sensor
    try:
        data['motion'] = motion_sensor.motion_detected
    except Exception as e:
        print("Motion sensor error:", e)
        data['motion'] = None

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

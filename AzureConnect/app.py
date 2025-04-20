import time
import Adafruit_DHT
import random
from azure.iot.device import IoTHubDeviceClient, Message

# Replace with your IoT Hub device connection string
CONNECTION_STRING = "HostName=edgeAI-hub.azure-devices.net;DeviceId=edge-voice-test-device;SharedAccessKey=INEQ7VrEqAEyrUW3JYTXeFGgprHut4kCLqq7RHTwFGE="

# Define sensor type and GPIO pin where the sensor's data pin is connected
dht_sensor = Adafruit_DHT.DHT22
dht_pin = 4  # GPIO4 is used here

# Initialize Azure IoT client
client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)

def get_sensor_data():
    # Read temperature and humidity from DHT sensor
    humidity, temperature = Adafruit_DHT.read_retry(dht_sensor, dht_pin)
    if humidity is not None and temperature is not None:
        # Simulate additional sensor data
        air_quality = random.uniform(20.0, 50.0)  # Example simulated value
        motion_detected = random.choice([True, False])  # Simulated motion data
        return {
            'temperature': temperature,
            'humidity': humidity,
            'air_quality': air_quality,
            'motion': motion_detected
        }
    else:
        print("Failed to retrieve data from sensor")
        return None

def send_data_to_azure(data):
    if data:
        # Convert data to string format and create a Message
        message = Message(str(data))
        client.send_message(message)
        print("Data sent to Azure IoT Hub")

def main():
    while True:
        data = get_sensor_data()
        send_data_to_azure(data)
        time.sleep(10)  # Wait 10 seconds before reading again

if _name_ == "_main_":
    main()
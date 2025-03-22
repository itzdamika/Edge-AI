import time
import random
import Adafruit_DHT
import Adafruit_DHT.raspberrypi as rpi_platform  # Import the Raspberry Pi module
from azure.iot.device import IoTHubDeviceClient, Message

# Force the library to use the Raspberry Pi platform
Adafruit_DHT.get_platform = lambda: rpi_platform

# Replace with your IoT Hub device connection string
CONNECTION_STRING = "HostName=edgeAI-hub.azure-devices.net;DeviceId=edge-voice-test-device;SharedAccessKey=INEQ7VrEqAEyrUW3JYTXeFGgprHut4kCLqq7RHTwFGE="

# Define sensor type and the GPIO pin where the sensor's data pin is connected
dht_sensor = Adafruit_DHT.DHT22
dht_pin = 4  # Data pin connected to GPIO4

# Initialize Azure IoT client
client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)

def get_sensor_data():
    # Read temperature and humidity from the DHT sensor
    humidity, temperature = Adafruit_DHT.read_retry(dht_sensor, dht_pin)
    if humidity is not None and temperature is not None:
        # Simulate additional sensor data
        air_quality = random.uniform(20.0, 50.0)
        motion_detected = random.choice([True, False])
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
        message = Message(str(data))
        client.send_message(message)
        print("Data sent to Azure IoT Hub")

def main():
    while True:
        data = get_sensor_data()
        send_data_to_azure(data)
        time.sleep(10)  # Wait 10 seconds before next reading

if __name__ == "__main__":
    main()

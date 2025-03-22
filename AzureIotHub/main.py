import time
import board
import adafruit_dht
import random
from azure.iot.device import IoTHubDeviceClient, Message

# Replace with your IoT Hub device connection string
CONNECTION_STRING = "HostName=edgeAI-hub.azure-devices.net;DeviceId=edge-voice-test-device;SharedAccessKey=INEQ7VrEqAEyrUW3JYTXeFGgprHut4kCLqq7RHTwFGE="

# Initialize the DHT22 sensor, data connected to GPIO4
dhtDevice = adafruit_dht.DHT22(board.D4)

# Initialize Azure IoT client
client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)

def get_sensor_data():
    try:
        # Get sensor readings
        temperature = dhtDevice.temperature
        humidity = dhtDevice.humidity
        if temperature is not None and humidity is not None:
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
    except Exception as e:
        print("Sensor error:", e)
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
        time.sleep(10)  # Wait 10 seconds before the next reading

if __name__ == "__main__":
    main()

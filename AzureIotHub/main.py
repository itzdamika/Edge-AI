from azure.iot.device import IoTHubDeviceClient, Message
import time

CONNECTION_STRING = "HostName=edgeAI-hub.azure-devices.net;DeviceId=edge-voice-test-device;SharedAccessKey=F+e7lE4RkFXxdwUqJvK11aHeYUhLf2eeEw1fhXw3UBQ="

def iothub_client_init():
    client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)
    client.connect()
    return client

def send_test_message(client):
    try:
        message = Message("Test message from device")
        print("Sending test message to Azure IoT Hub...")
        client.send_message(message=message)
        print("Message successfully sent")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    client = iothub_client_init()
    while True:
        iothub_message = Message("Hello from Raspberry Pi - Test Message")
        print(f"Sending message: {iothub_message}")
        client.send_message(iothub_message)
        print("Message successfully sent!")
        time.sleep(5)

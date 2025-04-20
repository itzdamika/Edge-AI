from azure.iot.device import IoTHubDeviceClient, Message

CONNECTION_STRING = "HostName=edgeAI-hub.azure-devices.net;DeviceId=edge-voice-test-device;SharedAccessKey=F+e7lE4RkFXxdwUqJvK11aHeYUhLf2eeEw1fhXw3UBQ="


device_client = IoTHubDeviceClient.create_from_connection_string(CONNECTION_STRING)

try:
    device_client.connect()

    data = {
        "temperature": 25.5,
        "humidity": 55
    }

    message = Message(str(data))
    device_client.send_message(message)
    print("Message sent:", data)

finally:
    device_client.shutdown()

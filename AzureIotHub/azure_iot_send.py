import time
import json
from azure.iot.device import ProvisioningDeviceClient, IoTHubDeviceClient, Message

# Device Provisioning Info (replace if needed)
id_scope = "0ne00E9E05C"
registration_id = "2isw66qw5v0"
symmetric_key = "BkjAyIdzHSOLbmISjirKg9cWHS06un0dvxoZtr4mXmU="
provisioning_host = "global.azure-devices-provisioning.net"

# Create the provisioning client
provisioning_client = ProvisioningDeviceClient.create_from_symmetric_key(
    provisioning_host=provisioning_host,
    registration_id=registration_id,
    id_scope=id_scope,
    symmetric_key=symmetric_key
)

# Register the device with DPS
registration_result = provisioning_client.register()

if registration_result.status != "assigned":
    raise RuntimeError(f"Could not register device. Status: {registration_result.status}")

# Connect to the IoT Hub
device_client = IoTHubDeviceClient.create_from_symmetric_key(
    symmetric_key=symmetric_key,
    hostname=registration_result.registration_state.assigned_hub,
    device_id=registration_id
)

device_client.connect()

try:
    # Send one full telemetry message with all fields
    initial_telemetry = {
        "Temperature": 25.5,
        "Humidity": 60.0,
        "Motion": True,
        "FaceDetection": False,
        "AirQuality": 0.82
    }

    msg = Message(json.dumps(initial_telemetry))
    msg.content_type = "application/json"
    msg.content_encoding = "utf-8"

    print("🔁 Sending initial telemetry to register schema...")
    device_client.send_message(msg)
    print("✅ Telemetry sent successfully.")

    time.sleep(2)

except Exception as e:
    print("❌ Error:", e)

finally:
    device_client.disconnect()
    print("🔌 Disconnected from IoT Hub.")
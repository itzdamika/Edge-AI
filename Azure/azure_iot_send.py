import time
import random
import json
from azure.iot.device import ProvisioningDeviceClient, IoTHubDeviceClient, Message

id_scope = "0ne00E9E05C"
registration_id = "4p4h03etwy"
symmetric_key = "MZfVRBR3sjtujB3uT4SnLgDV10ArlfY7U8BirdL9ZFA="

provisioning_host = "global.azure-devices-provisioning.net"
provisioning_client = ProvisioningDeviceClient.create_from_symmetric_key(
    provisioning_host=provisioning_host,
    registration_id=registration_id,
    id_scope=id_scope,
    symmetric_key=symmetric_key
)

registration_result = provisioning_client.register()

if registration_result.status != "assigned":
    raise RuntimeError("Could not register device. Status: {}".format(registration_result.status))

device_client = IoTHubDeviceClient.create_from_symmetric_key(
    symmetric_key=symmetric_key,
    hostname=registration_result.registration_state.assigned_hub,
    device_id=registration_id
)

device_client.connect()

try:
    while True:
        temperature = round(random.uniform(20.0, 30.0), 2)
        humidity = round(random.uniform(30.0, 70.0), 2)
        motion = random.choice([True, False])
        air_quality = random.choice(["Good", "Poor"])
        fan_speed = random.choice([1, 2, 3])
        ac_temperature = round(random.uniform(18.0, 26.0), 1)

        telemetry = {
            "Temperature": temperature,
            "Humidity": humidity,
            "Motion": motion,
            "AirQuality": air_quality,
            "FanSpeed": fan_speed,
            "ACTemperature": ac_temperature
        }

        msg = Message(json.dumps(telemetry))
        msg.content_type = "application/json"
        msg.content_encoding = "utf-8"

        print(f"Sending message: {telemetry}")
        device_client.send_message(msg)
        time.sleep(5)

except KeyboardInterrupt:
    print("Stopped by user.")

finally:
    device_client.disconnect()

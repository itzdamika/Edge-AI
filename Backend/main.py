# cloud_backend.py
from fastapi import FastAPI
import threading, json
import paho.mqtt.client as mqtt

app = FastAPI()

# Global variable to hold the latest sensor data.
latest_sensor_data = {}

MQTT_BROKER = "192.168.1.13"  # Use your broker address; adjust if not running on the same machine.
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/data"

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with result code", rc)
    client.subscribe(MQTT_TOPIC)

def on_message(client, userdata, msg):
    global latest_sensor_data
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
        latest_sensor_data = data
        print("Received sensor data:", data)
    except Exception as e:
        print("Error processing MQTT message:", e)

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

def mqtt_loop():
    mqtt_client.loop_forever()

threading.Thread(target=mqtt_loop, daemon=True).start()

@app.get("/latest")
def get_latest_data():
    return latest_sensor_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

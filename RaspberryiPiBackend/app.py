import RPi.GPIO as GPIO
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import paho.mqtt.client as mqtt

# --- GPIO Setup ---
GPIO.setmode(GPIO.BCM)

# Define GPIO pins for each device (adjust as necessary)
AC_PIN = 17
FAN_PIN = 27
LIGHT_PIN = 22

# Set up the GPIO pins as outputs
GPIO.setup(AC_PIN, GPIO.OUT)
GPIO.setup(FAN_PIN, GPIO.OUT)
GPIO.setup(LIGHT_PIN, GPIO.OUT)

# --- MQTT Setup ---
MQTT_BROKER = "localhost"   # Assumes Mosquitto (or other broker) is running on the Pi
MQTT_PORT = 1883

mqtt_client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with result code", rc)
    # Subscribe to control topics for all devices
    client.subscribe("devices/+/control")

def on_message(client, userdata, msg):
    topic = msg.topic  # e.g., "devices/ac/control"
    payload = msg.payload.decode().lower()  # expecting "on" or "off"
    parts = topic.split('/')
    if len(parts) != 3:
        return
    device = parts[1]
    print(f"Received MQTT command for {device}: {payload}")
    if device == "ac":
        pin = AC_PIN
    elif device == "fan":
        pin = FAN_PIN
    elif device == "light":
        pin = LIGHT_PIN
    else:
        return

    if payload == "on":
        GPIO.output(pin, GPIO.HIGH)
    elif payload == "off":
        GPIO.output(pin, GPIO.LOW)
    else:
        print("Invalid command payload")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Connect to the MQTT broker and start a background network loop.
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# --- FastAPI Setup ---
app = FastAPI()

# Enable CORS to allow access from other devices/PCs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/control/{device}")
async def control_device(device: str, state: str):
    """
    Endpoint to control a device via MQTT.
    - **device**: one of "ac", "fan", or "light"
    - **state**: "on" or "off"
    
    Example URL: http://<RaspberryPi_IP>:8000/control/ac?state=on
    """
    device = device.lower()
    state = state.lower()
    
    if device not in {"ac", "fan", "light"}:
        raise HTTPException(status_code=404, detail="Device not found")
    if state not in {"on", "off"}:
        raise HTTPException(status_code=400, detail="Invalid state. Use 'on' or 'off'")
    
    topic = f"devices/{device}/control"
    mqtt_client.publish(topic, state)
    return {"device": device, "state": state, "message": "Command published via MQTT"}

@app.on_event("shutdown")
def shutdown_event():
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    GPIO.cleanup()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

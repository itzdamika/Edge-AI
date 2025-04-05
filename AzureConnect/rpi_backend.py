from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import time, threading
import board
import adafruit_dht
import cv2
import base64
import pigpio
import busio
import adafruit_ssd1306

app = FastAPI()

# Enable CORS for external clients (like your React dashboard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your trusted domains.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Sensor Initialization -----
# DHT22 sensor on GPIO27
dhtDevice = adafruit_dht.DHT22(board.D27)

# Initialize pigpio (ensure pigpiod is running)
pi = pigpio.pi()
if not pi.connected:
    raise SystemExit("Could not connect to pigpio daemon. Start it with 'sudo systemctl start pigpiod'.")

# Digital sensor pins (MQ‑135 and HC‑SR501)
AIR_QUALITY_PIN = 18    # MQ‑135 digital output
MOTION_SENSOR_PIN = 17  # HC‑SR501 motion sensor

# Set up digital sensor pins with pull-down resistors
pi.set_mode(AIR_QUALITY_PIN, pigpio.INPUT)
pi.set_pull_up_down(AIR_QUALITY_PIN, pigpio.PUD_DOWN)

pi.set_mode(MOTION_SENSOR_PIN, pigpio.INPUT)
pi.set_pull_up_down(MOTION_SENSOR_PIN, pigpio.PUD_DOWN)

# ----- Light Control Initialization -----
# Define light control pins
KITCHEN_LIGHT_PIN = 22
LIVINGROOM_AC_PIN = 23
BEDROOM_FAN_PIN = 24

# Configure light control pins as outputs and set to off (0)
for pin in [KITCHEN_LIGHT_PIN, LIVINGROOM_AC_PIN, BEDROOM_FAN_PIN]:
    pi.set_mode(pin, pigpio.OUTPUT)
    pi.write(pin, 0)

# Global variables for light states (store "on" or "off")
kitchen_state = "off"
livingroom_state = "off"
bedroom_state = "off"

# ----- OLED Display Initialization -----
i2c = busio.I2C(board.SCL, board.SDA)
display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
# Clear display initially
display.fill(0)
display.show()

def update_display():
    """Update the OLED display with the current light states."""
    display.fill(0)
    # Display each light's state on a separate line
    display.text(f"Ammo: {kitchen_state.upper()}", 0, 0, 1)
    display.text(f"Gay: {livingroom_state.upper()}", 0, 10, 1)
    display.text(f"Sex: {bedroom_state.upper()}", 0, 20, 1)
    display.show()

def read_sensors():
    """Read sensor data and return it as a dictionary."""
    data = {}
    # DHT22: Temperature & Humidity
    try:
        data['temperature'] = dhtDevice.temperature
        data['humidity'] = dhtDevice.humidity
    except Exception as e:
        print("DHT22 error:", e)
        data['temperature'] = None
        data['humidity'] = None

    # MQ‑135: Digital output; assume HIGH means "Poor" air quality
    try:
        aq_val = pi.read(AIR_QUALITY_PIN)
        data['air_quality'] = "Poor" if aq_val == 1 else "Good"
    except Exception as e:
        print("Air quality sensor error:", e)
        data['air_quality'] = None

    # HC‑SR501: Motion sensor
    try:
        motion_val = pi.read(MOTION_SENSOR_PIN)
        data['motion'] = True if motion_val == 1 else False
    except Exception as e:
        print("Motion sensor error:", e)
        data['motion'] = None

    data['timestamp'] = time.time()
    return data

# Global variable to cache the latest sensor data
latest_data = {}

def sensor_updater():
    """Periodically update sensor data."""
    global latest_data
    while True:
        latest_data = read_sensors()
        time.sleep(10)

threading.Thread(target=sensor_updater, daemon=True).start()

@app.get("/sensors")
def get_sensor_data():
    """Return the latest sensor data as JSON."""
    return latest_data

# ----- Live Video Streaming Endpoint -----
def generate_frames():
    """Continuously capture frames from the USB camera and yield as an MJPEG stream."""
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(0.1)
    cap.release()

@app.get("/video_feed")
def video_feed():
    """Stream a live MJPEG video from the USB camera."""
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# ----- Light Control Endpoints -----
def set_light_state(pin: int, state: str):
    """Set the specified GPIO output for a light with debug logging."""
    print(f"[DEBUG] Setting pin {pin} to state '{state}'")
    if state.lower() == "on":
        pi.write(pin, 1)
    elif state.lower() == "off":
        pi.write(pin, 0)
    else:
        raise ValueError("Invalid state; use 'on' or 'off'.")
    print(f"[DEBUG] Pin {pin} set to {'HIGH' if state.lower()=='on' else 'LOW'}")

@app.get("/light/kitchen")
def control_kitchen_light(state: str = Query(..., description="Light state: 'on' or 'off'")):
    global kitchen_state
    try:
        set_light_state(KITCHEN_LIGHT_PIN, state)
        kitchen_state = state.lower()
        update_display()
        return {"light": "kitchen", "state": kitchen_state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/light/livingroom")
def control_livingroom_ac(state: str = Query(..., description="Light state: 'on' or 'off'")):
    global livingroom_state
    try:
        set_light_state(LIVINGROOM_AC_PIN, state)
        livingroom_state = state.lower()
        update_display()
        return {"light": "livingroom_ac", "state": livingroom_state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/light/bedroom")
def control_bedroom_fan(state: str = Query(..., description="Light state: 'on' or 'off'")):
    global bedroom_state
    try:
        set_light_state(BEDROOM_FAN_PIN, state)
        bedroom_state = state.lower()
        update_display()
        return {"light": "bedroom_fan", "state": bedroom_state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if _name_ == "_main_":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
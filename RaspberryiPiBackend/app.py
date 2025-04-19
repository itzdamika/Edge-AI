import asyncio 
import threading
import time
import datetime
import board
import adafruit_dht
import adafruit_ssd1306
import busio
import json
import cv2
import base64
import pigpio
import speech_recognition as sr
import azure.cognitiveservices.speech as speechsdk
import sys, logging, structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import BaseModel
import numpy as np
import smtplib
from email.message import EmailMessage


def send_email_notification():
    # Email credentials and recipient
    email_sender = "contact.smartaura@gmail.com"
    email_password = "wcxn qqis eioe lkbx"  # your Gmail app password
    email_receiver = "damikaudantha@gmail.com"
    
    subject = "Unknown face detected warning"
    body = "Warning: An unknown face has been detected by SmartAura."
    
    # Create the email message
    em = EmailMessage()
    em['From'] = email_sender
    em['To'] = email_receiver
    em['Subject'] = subject
    em.set_content(body)
    
    try:
        # Connect to the Gmail SMTP server using TLS
        with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(email_sender, email_password)
            smtp.send_message(em)
            logging.info("Email sent successfully to %s", email_receiver)
    except Exception as e:
        logging.error("Failed to send email notification: %s", e)


# ---------------------------
# Face Recognition Imports & Setup
# ---------------------------
import torch
from facenet_pytorch import MTCNN, InceptionResnetV1
from torchvision import transforms
from scipy.spatial.distance import cosine
import os
import gc
import queue

embeddings_dir = "face_embeddings"  # Folder containing saved .npy embeddings
threshold = 0.5  # Cosine similarity threshold

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
mtcnn = MTCNN(keep_all=True, device=device)
model = InceptionResnetV1(pretrained='vggface2').eval().to(device)
preprocess = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((160, 160)),
    transforms.ToTensor(),
    transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
])

# Load saved embeddings into a dictionary {name: embedding}
saved_embeddings = {}
if os.path.exists(embeddings_dir):
    for filename in os.listdir(embeddings_dir):
        if filename.endswith('.npy'):
            name = os.path.splitext(filename)[0]
            path = os.path.join(embeddings_dir, filename)
            saved_embeddings[name] = np.load(path)
logging.info(f"Loaded {len(saved_embeddings)} face embeddings.")

def preprocess_face(face_crop):
    face_resized = cv2.resize(face_crop, (160, 160))
    face_tensor = preprocess(face_resized).unsqueeze(0)
    return face_tensor

def recognize_known_face():
    """
    Capture one frame from the webcam, detect faces via MTCNN,
    compute embeddings via InceptionResnetV1, and compare with saved embeddings.
    Returns (recognized_name, distance); if none is below threshold, returns ("Unknown", distance).
    """
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return "Unknown", None
    boxes, probs = mtcnn.detect(frame, landmarks=False)
    if boxes is None or len(boxes) == 0:
        return "Unknown", None
    recognized_name = "Unknown"
    min_distance = float('inf')
    for box in boxes:
        x1, y1, x2, y2 = [int(coord) for coord in box]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
        if x1 < x2 and y1 < y2:
            face_crop = frame[y1:y2, x1:x2]
            if face_crop.size > 0:
                try:
                    face_tensor = preprocess_face(face_crop)
                    with torch.no_grad():
                        embedding = model(face_tensor.to(device)).detach().cpu().numpy().flatten()
                    for name, saved_embedding in saved_embeddings.items():
                        distance = cosine(embedding, saved_embedding.flatten())
                        if distance < min_distance:
                            min_distance = distance
                            recognized_name = name
                except Exception as e:
                    logging.error(f"Error in face recognition: {e}")
    if min_distance < threshold:
        return recognized_name, min_distance
    else:
        return "Unknown", min_distance

# ---------------------------
# Pydantic Model & Config
# ---------------------------
class LoginRequest(BaseModel):
    username: str
    password: str

# ---------------------------
# Logging Configuration
# ---------------------------
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()

# ---------------------------
# Configuration Using pydantic_settings (.env file)
# ---------------------------
class Config(BaseSettings):
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_DEPLOYMENT_ID: str
    AZURE_ENDPOINT: str
    SPEECH_KEY: str
    SERVICE_REGION: str
    TTS_ENDPOINT: str
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

config = Config()

# ---------------------------
# FastAPI Initialization & CORS
# ---------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Sensor & Light Control Initialization
# ---------------------------
dhtDevice = adafruit_dht.DHT22(board.D27)
pi = pigpio.pi()
if not pi.connected:
    raise SystemExit("Could not connect to pigpio daemon. Start it with 'sudo systemctl start pigpiod'.")
AIR_QUALITY_PIN = 18
MOTION_SENSOR_PIN = 17
pi.set_mode(AIR_QUALITY_PIN, pigpio.INPUT)
pi.set_pull_up_down(AIR_QUALITY_PIN, pigpio.PUD_DOWN)
pi.set_mode(MOTION_SENSOR_PIN, pigpio.INPUT)
pi.set_pull_up_down(MOTION_SENSOR_PIN, pigpio.PUD_DOWN)
KITCHEN_LIGHT_PIN = 22
LIVINGROOM_AC_PIN = 23
BEDROOM_FAN_PIN = 24
for pin in [KITCHEN_LIGHT_PIN, LIVINGROOM_AC_PIN, BEDROOM_FAN_PIN]:
    pi.set_mode(pin, pigpio.OUTPUT)
    pi.write(pin, 0)

kitchen_state = "off"
livingroom_state = "off"
bedroom_state = "off"
livingroom_ac_temp = 24
bedroom_fan_speed = 1

# NEW: Global flag to indicate system automation is active
system_automation_started = False

# ---------------------------
# Indicator LED (Jumbo Light) Pin Configuration
# ---------------------------
INDICATOR_RED_PIN = 25
INDICATOR_GREEN_PIN = 26
pi.set_mode(INDICATOR_RED_PIN, pigpio.OUTPUT)
pi.write(INDICATOR_RED_PIN, 0)
pi.set_mode(INDICATOR_GREEN_PIN, pigpio.OUTPUT)
pi.write(INDICATOR_GREEN_PIN, 0)

def blink_indicator(color: str, duration: float = 3.0):
    """
    Light the indicator LED in the specified color for the specified duration.
    Color can be "red" or "green".
    """
    if color.lower() == "red":
        pi.write(INDICATOR_RED_PIN, 1)
        time.sleep(duration)
        pi.write(INDICATOR_RED_PIN, 0)
    elif color.lower() == "green":
        pi.write(INDICATOR_GREEN_PIN, 1)
        time.sleep(duration)
        pi.write(INDICATOR_GREEN_PIN, 0)
    else:
        logging.error("Invalid indicator color specified.")

# ---------------------------
# I2C and OLED Initialization
# ---------------------------
i2c = busio.I2C(board.SCL, board.SDA)
display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
display.fill(0)
display.show()

def show_welcome_message():
    display.fill(0)
    welcome_text = "SMART AURA"
    display.text(welcome_text, 34, 12, 1)
    display.show()
    time.sleep(5)
    update_display()

def update_display():
    display.fill(0)
    display.text(f"Light: {kitchen_state.upper()}", 0, 0, 1)
    if livingroom_state.lower() == "on":
        display.text(f"AC: {livingroom_ac_temp}C", 0, 10, 1)
    else:
        display.text("AC: OFF", 0, 10, 1)
    if bedroom_state.lower() == "on":
        display.text(f"Fan: Lvl {bedroom_fan_speed}", 0, 20, 1)
    else:
        display.text("Fan: OFF", 0, 20, 1)
    display.show()

threading.Thread(target=show_welcome_message, daemon=True).start()

# ---------------------------
# TFLite Occupant Detection Model Initialization
# ---------------------------
import tflite_runtime.interpreter as tflite
occupant_interpreter = tflite.Interpreter(model_path="best_float16.tflite")
occupant_interpreter.allocate_tensors()
occupant_input_details = occupant_interpreter.get_input_details()
occupant_output_details = occupant_interpreter.get_output_details()
occupant_input_shape = occupant_input_details[0]['shape'][1:3]

def detect_person():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return False
    resized = cv2.resize(frame, tuple(occupant_input_shape))
    input_tensor = resized.astype(np.float32) / 255.0
    input_tensor = np.expand_dims(input_tensor, axis=0)
    occupant_interpreter.set_tensor(occupant_input_details[0]['index'], input_tensor)
    occupant_interpreter.invoke()
    output_data = occupant_interpreter.get_tensor(occupant_output_details[0]['index'])[0]
    try:
        confs = output_data[4]
        if np.any(confs > 0.5):
            return True
    except Exception:
        if np.max(output_data) > 0.5:
            return True
    return False

# ---------------------------
# Log Persistence
# ---------------------------
systemLogs = []
voiceLogs = []

def log_system(message: str):
    log_entry = {"timestamp": time.time(), "message": message}
    systemLogs.append(log_entry)
    if len(systemLogs) > 200:
        systemLogs.pop(0)
    with open("system_logs.txt", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

def log_voice(user: str, assistant: str):
    log_entry = {"timestamp": time.time(), "user": user, "assistant": assistant}
    voiceLogs.append(log_entry)
    if len(voiceLogs) > 200:
        voiceLogs.pop(0)
    with open("voice_logs.txt", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

@app.get("/logs")
def get_logs():
    all_logs = []
    try:
        with open("system_logs.txt", "r") as f:
            for line in f:
                if line.strip():
                    all_logs.append(json.loads(line))
    except FileNotFoundError:
        all_logs = systemLogs
    return all_logs

@app.get("/voicelogs")
def get_voice_logs():
    all_logs = []
    try:
        with open("voice_logs.txt", "r") as f:
            for line in f:
                if line.strip():
                    all_logs.append(json.loads(line))
    except FileNotFoundError:
        all_logs = voiceLogs
    return all_logs

@app.get("/lights")
def get_light_states():
    return {
        "kitchen": kitchen_state,
        "livingroom": livingroom_state,
        "bedroom": bedroom_state,
        "ac_temp": livingroom_ac_temp,
        "fan_speed": bedroom_fan_speed
    }

# ---------------------------
# Sensor Reading Function
# ---------------------------
def read_sensors():
    data = {}
    try:
        temp = dhtDevice.temperature
        hum = dhtDevice.humidity
        if temp is not None and hum is not None:
            data['temperature'] = temp
            data['humidity'] = hum
        else:
            logger.warning("DHT22 read returned None; ignoring this cycle.")
            data['temperature'] = None
            data['humidity'] = None
    except Exception as e:
        err_str = str(e).lower()
        if "a full buffer was not returned" in err_str:
            logger.warning("DHT22: A full buffer was not returned. Skipping this cycle.")
            data['temperature'] = None
            data['humidity'] = None
        else:
            logger.error("DHT22 error", error=str(e))
            data['temperature'] = None
            data['humidity'] = None
    try:
        aq_val = pi.read(AIR_QUALITY_PIN)
        data['air_quality'] = "Poor" if aq_val == 1 else "Good"
    except Exception as e:
        logger.error("Air quality sensor error", error=str(e))
        data['air_quality'] = None
    try:
        motion_val = pi.read(MOTION_SENSOR_PIN)
        data['motion'] = True if motion_val == 1 else False
    except Exception as e:
        logger.error("Motion sensor error", error=str(e))
        data['motion'] = None
    data['timestamp'] = time.time()
    return data

latest_data = {}
def sensor_updater():
    global latest_data
    while True:
        latest_data = read_sensors()
        time.sleep(10)
threading.Thread(target=sensor_updater, daemon=True).start()

@app.get("/sensors")
def get_sensor_data():
    return latest_data

# ---------------------------
# Live Video Streaming Endpoint
# ---------------------------
def generate_frames():
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
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# ---------------------------
# Light Control Endpoints
# ---------------------------
def set_light_state(pin: int, state: str):
    logger.info(f"[DEBUG] Setting pin {pin} to state '{state}'")
    if state.lower() == "on":
        pi.write(pin, 1)
    elif state.lower() == "off":
        pi.write(pin, 0)
    else:
        raise ValueError("Invalid state; use 'on' or 'off'.")
    logger.info(f"[DEBUG] Pin {pin} set to {'HIGH' if state.lower()=='on' else 'LOW'}")

@app.get("/light/kitchen")
def control_kitchen_light(state: str = Query(..., description="Light state: 'on' or 'off'")):
    global kitchen_state
    try:
        set_light_state(KITCHEN_LIGHT_PIN, state)
        kitchen_state = state.lower()
        update_display()
        log_system(f"Light turned {kitchen_state.upper()}")
        return {"light": "kitchen", "state": kitchen_state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/light/livingroom")
def control_livingroom_ac(state: str = Query(..., description="Light state: 'on' or 'off'")):
    global livingroom_state, livingroom_ac_temp
    try:
        set_light_state(LIVINGROOM_AC_PIN, state)
        if state.lower() == "on":
            livingroom_state = "on"
            livingroom_ac_temp = 16
        else:
            livingroom_state = "off"
        update_display()
        log_system(f"AC turned {livingroom_state.upper()}")
        return {"light": "livingroom_ac", "state": livingroom_state, "ac_temp": livingroom_ac_temp}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/light/bedroom")
def control_bedroom_fan(state: str = Query(..., description="Light state: 'on' or 'off'")):
    global bedroom_state, bedroom_fan_speed
    try:
        set_light_state(BEDROOM_FAN_PIN, state)
        if state.lower() == "on":
            bedroom_state = "on"
            bedroom_fan_speed = 1
        else:
            bedroom_state = "off"
        update_display()
        log_system(f"Fan turned {bedroom_state.upper()}")
        return {"light": "bedroom_fan", "state": bedroom_state, "fan_speed": bedroom_fan_speed}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/login")
def login(request: LoginRequest):
    if request.username == "admin" and request.password == "admin123":
        return {"id": "1", "username": "admin", "password": "admin123", "role": "admin"}
    elif request.username == "guest" and request.password == "guest123":
        return {"id": "2", "username": "guest", "password": "guest123", "role": "guest"}
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

# ---------------------------
# New Endpoints for AC Temperature and Fan Speed Control
# ---------------------------
@app.get("/ac/temp")
def control_ac_temp(value: int = Query(..., description="AC temperature between 16 and 32")):
    global livingroom_ac_temp
    if value < 16 or value > 32:
        raise HTTPException(status_code=400, detail="AC temperature must be between 16 and 32")
    livingroom_ac_temp = value
    update_display()
    log_system(f"AC temperature set to {value}C")
    return {"ac_temp": value}

@app.get("/fan/speed")
def control_fan_speed(level: int = Query(..., description="Fan speed level between 1 and 3")):
    global bedroom_fan_speed
    if level < 1 or level > 3:
        raise HTTPException(status_code=400, detail="Fan speed must be between 1 and 3")
    bedroom_fan_speed = level
    update_display()
    log_system(f"Fan speed set to level {level}")
    return {"fan_speed": level}

# ---------------------------
# Temperature Prediction Module
# ---------------------------
# Global variables for temperature prediction
temperature_history = []           # Last 5 hourly temperature readings in Celsius
latest_temperature_prediction = [] # Predicted next 5 hours temperatures in Celsius

def predict_temperature(model_path: str, input_temps: list) -> list:
    """
    Predict the next 5 hours of temperature given the last 5 hourly readings (in Celsius).
    Uses a TFLite model with built-in MinMax scaling.
    """
    # Load the TFLite model
    interpreter = tflite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    
    # Get input and output tensor details
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()
    
    # Hardcoded scaling parameters (from training data with MinMaxScaler with feature_range=(0, 1))
    scale_min = 273.0   # Minimum temperature (in Kelvin)
    scale_max = 293.1   # Maximum temperature (in Kelvin)
    
    # Prepare input: convert list to numpy array (float32)
    input_data = np.array(input_temps, dtype=np.float32)
    # Convert Celsius to Kelvin
    input_kelvin = input_data + 273.15
    # Scale the data
    input_scaled = (input_kelvin - scale_min) / (scale_max - scale_min)
    # Reshape for model input: [1, 5, 1]
    input_reshaped = input_scaled.reshape(1, 5, 1).astype(np.float32)
    
    # Set tensor and invoke
    interpreter.set_tensor(input_details[0]['index'], input_reshaped)
    interpreter.invoke()
    
    # Get and process the output
    prediction_scaled = interpreter.get_tensor(output_details[0]['index'])
    prediction_reshaped = prediction_scaled.reshape(-1)
    prediction_kelvin = prediction_reshaped * (scale_max - scale_min) + scale_min
    prediction_celsius = prediction_kelvin - 273.15
    
    return prediction_celsius.tolist()

def temperature_prediction_updater():
    """
    Every hour, update the temperature history (if less than 5 readings, fill with current value)
    and run the TFLite model to predict the next five hours of temperature.
    """
    global temperature_history, latest_temperature_prediction, latest_data
    while True:
        # Get the current temperature reading from sensor data.
        current_temp = latest_data.get("temperature")
        # If current sensor reading is None, use the last valid reading or a default value.
        if current_temp is None:
            if temperature_history and temperature_history[-1] is not None:
                current_temp = temperature_history[-1]
            else:
                current_temp = 20.0  # default value if no previous valid reading exists

        # Ensure that we have a full history of valid values.
        if len(temperature_history) < 5:
            temperature_history = [current_temp] * 5
        else:
            temperature_history.pop(0)
            temperature_history.append(current_temp)
        try:
            latest_temperature_prediction = predict_temperature("temperature_model_new.tflite", temperature_history)
            logger.info("Temperature prediction updated", prediction=latest_temperature_prediction)
        except Exception as e:
            logger.error("Temperature prediction error", error=str(e))
            latest_temperature_prediction = []
        # Sleep for 1 hour (3600 seconds); adjust the interval for testing if needed.
        time.sleep(3600)


threading.Thread(target=temperature_prediction_updater, daemon=True).start()

@app.get("/temperature_prediction")
def get_temperature_prediction():
    """
    Returns the last 5 hourly temperature history and predicted next 5 hours temperatures.
    """
    return {
        "temperature_history": temperature_history,
        "temperature_prediction": latest_temperature_prediction
    }

# ---------------------------
# GPT & Voice Assistant Components
# ---------------------------
intent_prompt = """
Analyze the user’s message and classify its intent into one of the following categories:

1. *command-query*: Commands related to controlling devices in the home.
   Examples:
   - "On the lights"
   - "Turn on the lights"
   - "Off the lights"
   - "On the AC"
   - "Off the AC"
   - "Turn on the fan"

2. *general-query*: All other types of general questions or statements unrelated to home device control.

*Instructions:*
- Respond with only one of the following intents: *command-query* or *general-query*.
- Ensure that the intent is classified accurately based on the user’s message.
"""

general_prompt = """
You are a SmartAura Smart Home Assistant. Keep answers short and direct.
"""

command_prompt = """
You are responsible for controlling devices in the house:

1) Kitchen Light: 'kitchen-on' / 'kitchen-off'
2) Living Room AC: 'ac-on' / 'ac-off' or 'ac-temp-XX' where XX is a value between 16 and 32.
3) Bedroom Fan: 'fan-on' / 'fan-off' or 'fan-speed-X' where X is 1, 2, or 3.
Additionally, if the user says "I'm leaving", turn off all devices.

*Guidelines:*
- Respond only with one of the following actions: 
  kitchen-on, kitchen-off, 
  ac-on, ac-off, ac-temp-XX,
  fan-on, fan-off, fan-speed-X,
  or the special command "im leaving" for turning off all devices.
- If the request does not match any valid action, respond with "error".
"""

async def _create_completion(messages: list, **kwargs) -> str:
    default_kwargs = {
        "model": config.AZURE_OPENAI_DEPLOYMENT_ID,
        "max_tokens": 100,
        "temperature": 0.7,
        "top_p": 0.95,
    }
    default_kwargs.update(kwargs)
    response = await asyncio.to_thread(
        lambda: openai_client.chat.completions.create(messages=messages, **default_kwargs)
    )
    return response.choices[0].message.content.strip()

async def handle_commands(user_message: str) -> str:
    global kitchen_state, livingroom_state, bedroom_state, livingroom_ac_temp, bedroom_fan_speed, system_automation_started
    lowered = user_message.lower()
    if "i'm leaving" in lowered or "i am leaving" in lowered or "im leaving" in lowered:
        set_light_state(KITCHEN_LIGHT_PIN, "off")
        set_light_state(LIVINGROOM_AC_PIN, "off")
        set_light_state(BEDROOM_FAN_PIN, "off")
        kitchen_state = "off"
        livingroom_state = "off"
        bedroom_state = "off"
        update_display()
        log_system("User command: I'm leaving. All devices turned OFF.")
        system_automation_started = False
        return "Turning off all devices."
    messages = [
        {"role": "system", "content": command_prompt},
        {"role": "user", "content": user_message}
    ]
    command = await _create_completion(messages)
    logger.info("Detected Command", intent=command)
    if command == "kitchen-on":
        set_light_state(KITCHEN_LIGHT_PIN, "on")
        kitchen_state = "on"
        update_display()
        log_system("Light turned ON")
        return "Turning on the light."
    elif command == "kitchen-off":
        set_light_state(KITCHEN_LIGHT_PIN, "off")
        kitchen_state = "off"
        update_display()
        log_system("Light turned OFF")
        return "Turning off the light."
    elif command == "ac-on":
        set_light_state(LIVINGROOM_AC_PIN, "on")
        livingroom_state = "on"
        livingroom_ac_temp = 16
        update_display()
        log_system("AC turned ON with default temperature 16°C")
        return "Turning on the AC with default temperature 16°C."
    elif command == "ac-off":
        set_light_state(LIVINGROOM_AC_PIN, "off")
        livingroom_state = "off"
        update_display()
        log_system("AC turned OFF")
        return "Turning off the AC."
    elif command.startswith("ac-temp-"):
        try:
            temp_value = int(command.split("ac-temp-")[1])
            if temp_value < 16 or temp_value > 32:
                return "AC temperature out of range."
            livingroom_ac_temp = temp_value
            update_display()
            log_system(f"AC temperature set to {temp_value}C")
            return f"Setting AC temperature to {temp_value} degrees."
        except Exception:
            return "Invalid AC temperature value."
    elif command == "fan-on":
        set_light_state(BEDROOM_FAN_PIN, "on")
        bedroom_state = "on"
        bedroom_fan_speed = 1
        update_display()
        log_system("Fan turned ON with default speed 1")
        return "Turning on the fan with default speed 1."
    elif command == "fan-off":
        set_light_state(BEDROOM_FAN_PIN, "off")
        bedroom_state = "off"
        update_display()
        log_system("Fan turned OFF")
        return "Turning off the fan."
    elif command.startswith("fan-speed-"):
        try:
            speed_value = int(command.split("fan-speed-")[1])
            if speed_value < 1 or speed_value > 3:
                return "Fan speed out of range."
            bedroom_fan_speed = speed_value
            update_display()
            log_system(f"Fan speed set to {speed_value}")
            return f"Setting fan speed to {speed_value}."
        except Exception:
            return "Invalid fan speed value."
    else:
        return "Sorry, I didn't understand your request."

async def handle_general(user_message: str) -> str:
    messages = [
        {"role": "system", "content": general_prompt},
        {"role": "user", "content": user_message}
    ]
    return await _create_completion(messages)

async def process_user_query(user_message: str):
    try:
        messages = [
            {"role": "system", "content": intent_prompt},
            {"role": "user", "content": user_message},
        ]
        detected_intent = (await _create_completion(messages)).lower().strip()
        logger.info("Detected Intent", intent=detected_intent)
        response_text = ""
        if detected_intent == "command-query":
            response_text = await handle_commands(user_message)
        elif detected_intent == "general-query":
            response_text = await handle_general(user_message)
        else:
            response_text = "I'm not sure what you're asking."
        log_voice(user_message, response_text)
        return response_text
    except Exception as e:
        logger.error("Error in process_user_query", error=str(e))
        return "An error occurred while processing your request."

class DeviceStateManager:
    def init(self) -> None:
        self.state = {"kitchen": "off", "ac": "off", "fan": "off"}

device_state_manager = DeviceStateManager()

from openai import AzureOpenAI
openai_client = AzureOpenAI(
    api_key=config.AZURE_OPENAI_API_KEY,
    api_version="2024-05-01-preview",
    azure_endpoint=config.AZURE_ENDPOINT,
)

speech_config = speechsdk.SpeechConfig(subscription=config.SPEECH_KEY, region=config.SERVICE_REGION)
speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_Endpoint, config.TTS_ENDPOINT)
speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

def recognize_speech(timeout=8):
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=timeout)
            text = recognizer.recognize_google(audio)
            logger.info("Recognized speech", text=text)
            return text
        except Exception as e:
            logger.error("Speech recognition error", error=str(e))
            return None

def speak_text(text: str):
    print(f"Speaking: {text}")
    result = speech_synthesizer.speak_text_async(text).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech synthesized successfully.")
    else:
        print("Speech synthesis error:", result.cancellation_details)

async def voice_assistant_loop():
    """
    Continuously listen for voice commands.
    Always check for 'leaving' command even when idle.
    Also check for 'hello assistant' to activate commands.
    """
    state = "idle"
    last_command_time = time.time()
    while True:
        user_text = recognize_speech(timeout=5)
        if user_text:
            lowered = user_text.lower()
            if ("i'm leaving" in lowered or "i am leaving" in lowered or "im leaving" in lowered):
                response = await handle_commands(user_text)
                speak_text(response)
                state = "idle"
                last_command_time = time.time()
            elif state == "idle" and "hello assistant" in lowered:
                speak_text("Hello, how can I help you?")
                state = "active"
                last_command_time = time.time()
            elif state == "active":
                last_command_time = time.time()
                response = await process_user_query(user_text)
                speak_text(response)
            if state == "active" and (time.time() - last_command_time > 30):
                speak_text("Going idle.")
                state = "idle"
        await asyncio.sleep(1)

def start_voice_assistant():
    asyncio.run(voice_assistant_loop())

threading.Thread(target=start_voice_assistant, daemon=True).start()

# ---------------------------
# Automation Controller
# ---------------------------
def automation_controller():
    """
    When the PIR sensor indicates occupancy and the camera-based occupant detection
    confirms a person is present, run face recognition.
    Only if a known face is detected will the system automation run.
    Otherwise, log "Unknown face detected" and send an email notification.
    Additionally, once the system is automatically started, the automation
    will be disabled until the user says "I'm leaving".

    Logic:
      - If current time is after 6 PM or before 6 AM, turn on the kitchen light.
      - Based on ambient temperature:
          > 28°C: Turn AC on (set to 22°C) and fan on at speed 3.
          24°C < Temp <= 28°C: Turn AC on (set to 24°C) and fan on at speed 2.
          <= 24°C: Turn AC and fan off.
    """
    global kitchen_state, livingroom_state, bedroom_state, livingroom_ac_temp, bedroom_fan_speed, system_automation_started
    while True:
        motion = latest_data.get('motion', False)
        # Only run face recognition if both the PIR sensor detects motion
        # and the camera occupant detection model confirms occupancy.
        if motion and detect_person() and not system_automation_started:
            log_system("Occupant detected by PIR and camera.")
            name, dist = recognize_known_face()
            if name != "Unknown":
                blink_indicator("green", 3)
                log_system(f"{name} is detected.")
                now = datetime.datetime.now()
                if now.hour >= 18 or now.hour < 6:
                    if kitchen_state.lower() != "on":
                        set_light_state(KITCHEN_LIGHT_PIN, "on")
                        kitchen_state = "on"
                        log_system("Automated: Kitchen Light turned ON (nighttime occupancy).")
                current_temp = latest_data.get('temperature')
                if current_temp is not None:
                    if current_temp > 28:
                        if livingroom_state.lower() != "on":
                            set_light_state(LIVINGROOM_AC_PIN, "on")
                            livingroom_state = "on"
                        livingroom_ac_temp = 22
                        if bedroom_state.lower() != "on":
                            set_light_state(BEDROOM_FAN_PIN, "on")
                            bedroom_state = "on"
                        bedroom_fan_speed = 3
                        log_system("Automated: High temperature detected. AC set to 22°C, Fan speed to 3.")
                    elif current_temp > 24:
                        if livingroom_state.lower() != "on":
                            set_light_state(LIVINGROOM_AC_PIN, "on")
                            livingroom_state = "on"
                        livingroom_ac_temp = 24
                        if bedroom_state.lower() != "on":
                            set_light_state(BEDROOM_FAN_PIN, "on")
                            bedroom_state = "on"
                        bedroom_fan_speed = 2
                        log_system("Automated: Moderate temperature detected. AC set to 24°C, Fan speed to 2.")
                    else:
                        if livingroom_state.lower() != "off":
                            set_light_state(LIVINGROOM_AC_PIN, "off")
                            livingroom_state = "off"
                        if bedroom_state.lower() != "off":
                            set_light_state(BEDROOM_FAN_PIN, "off")
                            bedroom_state = "off"
                        log_system("Automated: Comfortable temperature detected. AC and Fan turned OFF.")
                    update_display()
                system_automation_started = True
                time.sleep(20)
            else:
                # If face recognition returns "Unknown", signal via red indicator and send email.
                blink_indicator("red", 3)
                log_system("Unknown face detected.")
                send_email_notification()
                time.sleep(5)
        else:
            # If either PIR or camera detection fails, simply sleep a bit before checking again.
            time.sleep(2)

threading.Thread(target=automation_controller, daemon=True).start()

# ---------------------------
# Azure IoT Hub Telemetry Sender
# ---------------------------
from azure.iot.device import ProvisioningDeviceClient, IoTHubDeviceClient, Message

def iot_telemetry_sender():
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
            telemetry = {
                "Temperature": latest_data.get("temperature"),
                "Humidity": latest_data.get("humidity"),
                "AirQuality": latest_data.get("air_quality"),
                "Motion": latest_data.get("motion"),
                "ACTemperature": livingroom_ac_temp,
                "FanSpeed": bedroom_fan_speed,
                "Timestamp": time.time()
            }
            msg = Message(json.dumps(telemetry))
            msg.content_type = "application/json"
            msg.content_encoding = "utf-8"
            print(f"Sending telemetry: {telemetry}")
            device_client.send_message(msg)
            time.sleep(5)
    except KeyboardInterrupt:
        print("Telemetry sender stopped by user.")
    finally:
        device_client.disconnect()

threading.Thread(target=iot_telemetry_sender, daemon=True).start()

if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        pi.stop()

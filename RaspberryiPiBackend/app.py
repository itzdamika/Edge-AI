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
# DHT22 sensor on GPIO27
dhtDevice = adafruit_dht.DHT22(board.D27)

# Initialize pigpio (ensure pigpiod is running)
pi = pigpio.pi()
if not pi.connected:
    raise SystemExit("Could not connect to pigpio daemon. Start it with 'sudo systemctl start pigpiod'.")

# Digital sensor pins
AIR_QUALITY_PIN = 18
MOTION_SENSOR_PIN = 17

pi.set_mode(AIR_QUALITY_PIN, pigpio.INPUT)
pi.set_pull_up_down(AIR_QUALITY_PIN, pigpio.PUD_DOWN)
pi.set_mode(MOTION_SENSOR_PIN, pigpio.INPUT)
pi.set_pull_up_down(MOTION_SENSOR_PIN, pigpio.PUD_DOWN)

# Light control pins
KITCHEN_LIGHT_PIN = 22
LIVINGROOM_AC_PIN = 23
BEDROOM_FAN_PIN = 24

for pin in [KITCHEN_LIGHT_PIN, LIVINGROOM_AC_PIN, BEDROOM_FAN_PIN]:
    pi.set_mode(pin, pigpio.OUTPUT)
    pi.write(pin, 0)

# Global state variables for on/off
kitchen_state = "off"
livingroom_state = "off"  # for AC on/off
bedroom_state = "off"     # for Fan on/off

# NEW: AC Temperature and Fan Speed variables
livingroom_ac_temp = 24   # will be reset to 16 when AC is turned ON
bedroom_fan_speed = 1     # will be reset to 1 when Fan is turned ON

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
    # Center the text approximately; adjust as needed for your OLED
    display.text(welcome_text, 34, 12, 1)
    display.show()
    time.sleep(5)
    update_display()

def update_display():
    """Update the OLED display with the current states of Light, AC, and Fan."""
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

# Start welcome message in a separate thread
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
    """
    Capture a frame from the webcam, run the tflite model,
    and return True if a person is detected (confidence > 0.5).
    """
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
# Log Persistence (System and Voice Logs)
# ---------------------------
systemLogs = []
voiceLogs = []

def log_system(message: str):
    """Store a system log entry and append it to file."""
    log_entry = {
        "timestamp": time.time(),
        "message": message
    }
    systemLogs.append(log_entry)
    if len(systemLogs) > 200:
        systemLogs.pop(0)
    with open("system_logs.txt", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

def log_voice(user: str, assistant: str):
    """Store a voice log entry and append it to file."""
    log_entry = {
        "timestamp": time.time(),
        "user": user,
        "assistant": assistant
    }
    voiceLogs.append(log_entry)
    if len(voiceLogs) > 200:
        voiceLogs.pop(0)
    with open("voice_logs.txt", "a") as f:
        f.write(json.dumps(log_entry) + "\n")

@app.get("/logs")
def get_logs():
    """Return all system logs (live & past) from the persisted file."""
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
    """Return all voice logs (live & past) from the persisted file."""
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
        yield (
            b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n'
        )
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
            livingroom_ac_temp = 16  # default when AC is turned on
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
            bedroom_fan_speed = 1  # default when Fan is turned on
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
        return {
            "id": "1",
            "username": "admin",
            "password": "admin123",
            "role": "admin"
        }
    elif request.username == "guest" and request.password == "guest123":
        return {
            "id": "2",
            "username": "guest",
            "password": "guest123",
            "role": "guest"
        }
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
# GPT & Voice Assistant Components
# ---------------------------
intent_prompt = """
Analyze the user’s message and classify its intent into one of the following categories:

1. **command-query**: Commands related to controlling devices in the home.
   Examples:
   - "On the lights"
   - "Turn on the lights"
   - "Off the lights"
   - "On the AC"
   - "Off the AC"
   - "Turn on the fan"

2. **general-query**: All other types of general questions or statements unrelated to home device control.

**Instructions:**
- Respond with only one of the following intents: **command-query** or **general-query**.
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

**Guidelines:**
- Respond only with one of the following actions: 
  kitchen-on, kitchen-off, 
  ac-on, ac-off, ac-temp-XX,
  fan-on, fan-off, fan-speed-X,
  or the special command "im leaving" for turning off all devices.
- If the request does not match any valid action, respond with "error".

**Examples of valid commands:**
- "Lights on" => 'kitchen-on'
- "Turn on the lights" => 'kitchen-on'
- "Lights off" => 'kitchen-off'
- "Turn off the lights" => 'kitchen-off'
- "Turn on the AC" => 'ac-on'
- "Turn off the AC" => 'ac-off'
- "Set AC to 26 degrees" => 'ac-temp-26'
- "Turn on the fan" => 'fan-on'
- "Turn off the fan" => 'fan-off'
- "Set fan speed to 2" => 'fan-speed-2'
- "I'm leaving" => special command to turn everything off

**Important Notes:**
- No additional text or explanation is required. Only respond with the action corresponding to the command or "error" if there is no match.
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
    global kitchen_state, livingroom_state, bedroom_state, livingroom_ac_temp, bedroom_fan_speed
    # Special check for "I'm leaving" command:
    if "i'm leaving" in user_message.lower() or "im leaving" in user_message.lower():
        set_light_state(KITCHEN_LIGHT_PIN, "off")
        set_light_state(LIVINGROOM_AC_PIN, "off")
        set_light_state(BEDROOM_FAN_PIN, "off")
        kitchen_state = "off"
        livingroom_state = "off"
        bedroom_state = "off"
        update_display()
        log_system("User command: I'm leaving. All devices turned OFF.")
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
        livingroom_ac_temp = 16  # default when turning on
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
        bedroom_fan_speed = 1  # default when turning on
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
        self.state = {
            "kitchen": "off",
            "ac": "off",
            "fan": "off"
        }

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
    state = "idle"
    last_command_time = None
    while True:
        if state == "idle":
            print("Voice assistant in idle mode. Waiting for 'Hello Assistant'...")
            user_text = recognize_speech(timeout=5)
            if user_text and "hello assistant" in user_text.lower():
                speak_text("Hello, how can I help you?")
                state = "active"
                last_command_time = time.time()
            await asyncio.sleep(1)
        elif state == "active":
            user_text = recognize_speech(timeout=5)
            if user_text:
                last_command_time = time.time()
                response = await process_user_query(user_text)
                logger.info("Assistant Response", response=response)
                speak_text(response)
            else:
                if time.time() - last_command_time > 30:
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
    When the PIR sensor indicates occupancy, run the TFLite occupant detection model.
    If both the motion sensor and the model detect a person, automatically adjust devices.
    Logic:
      - If current time is after 6 PM or before 6 AM, turn on the kitchen light.
      - Based on ambient temperature:
          > 28°C: Turn AC on (set to 22°C) and fan on at speed 3.
          24°C < Temp <= 28°C: Turn AC on (set to 24°C) and fan on at speed 2.
          <= 24°C: Turn AC and fan off.
    """
    global kitchen_state, livingroom_state, bedroom_state, livingroom_ac_temp, bedroom_fan_speed
    while True:
        motion = latest_data.get('motion', False)
        if motion:
            if detect_person():
                now = datetime.datetime.now()
                # Turn on kitchen light at nighttime
                if now.hour >= 18 or now.hour < 6:
                    if kitchen_state.lower() != "on":
                        set_light_state(KITCHEN_LIGHT_PIN, "on")
                        kitchen_state = "on"
                        log_system("Automated: Kitchen Light turned ON (nighttime occupancy).")
                # Automation for AC/Fan based on ambient temperature
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
                time.sleep(60)
            else:
                time.sleep(5)
        else:
            time.sleep(5)

threading.Thread(target=automation_controller, daemon=True).start()

if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        pi.stop()

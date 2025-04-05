import asyncio
import threading
import time
import datetime
import board
import adafruit_dht
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

# DHT22 sensor on GPIO27
dhtDevice = adafruit_dht.DHT22(board.D27)

# Initialize pigpio (ensure pigpiod is running)
pi = pigpio.pi()
if not pi.connected:
    raise SystemExit("Could not connect to pigpio daemon. Start it with 'sudo systemctl start pigpiod'.")

# Digital sensor pins
AIR_QUALITY_PIN = 18    # MQ‑135 digital output
MOTION_SENSOR_PIN = 17  # HC‑SR501 motion sensor

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

# Global light state variables (simple, no locks)
kitchen_state = "off"
livingroom_state = "off"
bedroom_state = "off"

# ---------------------------
# Sensor Reading Function (with DHT exception handling)
# ---------------------------
def read_sensors():
    data = {}
    try:
        # Attempt reading DHT22
        temp = dhtDevice.temperature
        hum = dhtDevice.humidity
        # If the read fails, we might get None or raise an exception
        if temp is not None and hum is not None:
            data['temperature'] = temp
            data['humidity'] = hum
        else:
            # We'll just log a warning and keep them as None
            logger.warning("DHT22 read returned None; ignoring this cycle.")
            data['temperature'] = None
            data['humidity'] = None
    except Exception as e:
        # Specifically ignore 'A full buffer was not returned. Try again.' or handle
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
# Light Control Endpoints (Simplified)
# ---------------------------
def set_light_state(pin: int, state: str):
    logger.info(f"[DEBUG] Setting pin {pin} to state '{state}'")
    if state.lower() == "on":
        pi.write(pin, 1)
    elif state.lower() == "off":
        pi.write(pin, 0)
    else:
        raise ValueError("Invalid state; use 'on' or 'off'.")
    logger.info(
        f"[DEBUG] Pin {pin} set to {'HIGH' if state.lower()=='on' else 'LOW'}"
    )

@app.get("/light/kitchen")
def control_kitchen_light(state: str = Query(..., description="Light state: 'on' or 'off'")):
    global kitchen_state
    try:
        set_light_state(KITCHEN_LIGHT_PIN, state)
        kitchen_state = state.lower()
        return {"light": "kitchen", "state": kitchen_state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/light/livingroom")
def control_livingroom_ac(state: str = Query(..., description="Light state: 'on' or 'off'")):
    global livingroom_state
    try:
        set_light_state(LIVINGROOM_AC_PIN, state)
        livingroom_state = state.lower()
        return {"light": "livingroom_ac", "state": livingroom_state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/light/bedroom")
def control_bedroom_fan(state: str = Query(..., description="Light state: 'on' or 'off'")):
    global bedroom_state
    try:
        set_light_state(BEDROOM_FAN_PIN, state)
        bedroom_state = state.lower()
        return {"light": "bedroom_fan", "state": bedroom_state}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------------------------
# GPT & Voice Assistant Components
# ---------------------------
from openai import AzureOpenAI
openai_client = AzureOpenAI(
    api_key=config.AZURE_OPENAI_API_KEY,
    api_version="2024-05-01-preview",
    azure_endpoint=config.AZURE_ENDPOINT,
)

intent_prompt = """
Analyze the user message and classify its intent into one of the predefined categories:
Categories:
1. command-query: The user wants to control the items in his home.
2. general-query: The user is asking a general question.

Instructions:
Reply with only "command-query" or "general-query". No extra text.
"""

general_prompt = """
You are a SmartAura Smart Home Assistant. Keep answers short and direct.
"""

# FINAL: We updated the command_prompt so "lights on" => "kitchen-on", "lights off" => "kitchen-off", etc.
command_prompt = """
We only have three devices:
1) Kitchen Light => "kitchen-on"/"kitchen-off"
2) Living Room AC => "ac-on"/"ac-off"
3) Bedroom Fan => "fan-on"/"fan-off"

Examples:
- "Lights on" => "kitchen-on"
- "Turn on the lights" => "kitchen-on"
- "Lights off" => "kitchen-off"
- "Turn off the lights" => "kitchen-off"
- "Turn on the AC" => "ac-on"
- "Turn off the AC" => "ac-off"
- "Turn on the fan" => "fan-on"
- "Turn off the fan" => "fan-off"

If no match, respond with "error" only.
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
    # We use the updated command_prompt
    messages = [
        {"role": "system", "content": command_prompt},
        {"role": "user", "content": user_message}
    ]
    command = await _create_completion(messages)
    logger.info("Detected Command", intent=command)

    # Now only these six:
    if command == "kitchen-on":
        set_light_state(KITCHEN_LIGHT_PIN, "on")
        return "Turning on the kitchen light."
    elif command == "kitchen-off":
        set_light_state(KITCHEN_LIGHT_PIN, "off")
        return "Turning off the kitchen light."
    elif command == "ac-on":
        set_light_state(LIVINGROOM_AC_PIN, "on")
        return "Turning on the AC (living room light)."
    elif command == "ac-off":
        set_light_state(LIVINGROOM_AC_PIN, "off")
        return "Turning off the AC."
    elif command == "fan-on":
        set_light_state(BEDROOM_FAN_PIN, "on")
        return "Turning on the bedroom fan."
    elif command == "fan-off":
        set_light_state(BEDROOM_FAN_PIN, "off")
        return "Turning off the bedroom fan."
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
        # Decide if it's command-query or general-query
        messages = [
            {"role": "system", "content": intent_prompt},
            {"role": "user", "content": user_message},
        ]
        detected_intent = (await _create_completion(messages)).lower().strip()
        logger.info("Detected Intent", intent=detected_intent)

        if detected_intent == "command-query":
            response_text = await handle_commands(user_message)
        elif detected_intent == "general-query":
            response_text = await handle_general(user_message)
        else:
            response_text = "I'm not sure what you're asking."
        return response_text
    except Exception as e:
        logger.error("Error in process_user_query", error=str(e))
        return "An error occurred while processing your request."

# Minimal device state manager if you want it, but not essential for physically toggling pins
class DeviceStateManager:
    def _init_(self) -> None:
        self.state = {
            "kitchen": "off",
            "ac": "off",
            "fan": "off"
        }

    def set_kitchen_on(self):
        self.state["kitchen"] = "on"
    def set_kitchen_off(self):
        self.state["kitchen"] = "off"
    def set_ac_on(self):
        self.state["ac"] = "on"
    def set_ac_off(self):
        self.state["ac"] = "off"
    def set_fan_on(self):
        self.state["fan"] = "on"
    def set_fan_off(self):
        self.state["fan"] = "off"

device_state_manager = DeviceStateManager()

# ---------------------------
# Azure Speech Service Configuration for TTS
# ---------------------------
speech_config = speechsdk.SpeechConfig(subscription=config.SPEECH_KEY, region=config.SERVICE_REGION)
speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_Endpoint, config.TTS_ENDPOINT)
speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

def recognize_speech(timeout=5):
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
    while True:
        print("Voice assistant waiting for input...")
        user_text = recognize_speech(timeout=5)
        if user_text:
            response = await process_user_query(user_text)
            logger.info("Assistant Response", response=response)
            speak_text(response)
        await asyncio.sleep(1)

def start_voice_assistant():
    asyncio.run(voice_assistant_loop())

threading.Thread(target=start_voice_assistant, daemon=True).start()

# ---------------------------
# Run FastAPI Server
# ---------------------------
if _name_ == "_main_":
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        pi.stop()
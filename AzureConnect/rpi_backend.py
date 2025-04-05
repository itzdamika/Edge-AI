import asyncio
import threading
import time
import datetime
import board
import adafruit_dht
import cv2
import base64
import pigpio
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import speech_recognition as sr
import azure.cognitiveservices.speech as speechsdk
import sys, logging, structlog

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
# FastAPI Initialization & CORS
# ---------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your dashboard domain.
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

# Light Control pins
KITCHEN_LIGHT_PIN = 22
LIVINGROOM_AC_PIN = 23
BEDROOM_FAN_PIN = 24

for pin in [KITCHEN_LIGHT_PIN, LIVINGROOM_AC_PIN, BEDROOM_FAN_PIN]:
    pi.set_mode(pin, pigpio.OUTPUT)
    pi.write(pin, 0)

# ---------------------------
# Sensor Reading Function
# ---------------------------
def read_sensors():
    data = {}
    try:
        data['temperature'] = dhtDevice.temperature
        data['humidity'] = dhtDevice.humidity
    except Exception as e:
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
    logger.info(f"Setting pin {pin} to state '{state}'")
    if state.lower() == "on":
        pi.write(pin, 1)
    elif state.lower() == "off":
        pi.write(pin, 0)
    else:
        raise ValueError("Invalid state; use 'on' or 'off'.")
    logger.info(f"Pin {pin} set to {'HIGH' if state.lower()=='on' else 'LOW'}")

@app.get("/light/kitchen")
def control_kitchen_light(state: str = Query(..., description="Light state: 'on' or 'off'")):
    try:
        set_light_state(KITCHEN_LIGHT_PIN, state)
        return {"light": "kitchen", "state": state.lower()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/light/livingroom")
def control_livingroom_ac(state: str = Query(..., description="Light state: 'on' or 'off'")):
    try:
        set_light_state(LIVINGROOM_AC_PIN, state)
        return {"light": "livingroom_ac", "state": state.lower()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/light/bedroom")
def control_bedroom_fan(state: str = Query(..., description="Light state: 'on' or 'off'")):
    try:
        set_light_state(BEDROOM_FAN_PIN, state)
        return {"light": "bedroom_fan", "state": state.lower()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------------------------
# Voice Assistant Configuration
# ---------------------------
SPEECH_KEY = "AmewBM3Olz7oZeVnhVp2tqAdQ6wbuHGFIhTUcO1GFNP2CmAYLOn9JQQJ99BCACqBBLyXJ3w3AAAYACOGeDlD"
SERVICE_REGION =  "southeastasia"
TTS_ENDPOINT = "https://southeastasia.tts.speech.microsoft.com/cognitiveservices/v1"

speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SERVICE_REGION)
speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_Endpoint, TTS_ENDPOINT)
speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

def recognize_speech(timeout=5):
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        r.adjust_for_ambient_noise(source)
        try:
            audio = r.listen(source, timeout=timeout)
            text = r.recognize_google(audio)
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
            response = f"You said: {user_text}"
            speak_text(response)
        await asyncio.sleep(1)

def start_voice_assistant():
    asyncio.run(voice_assistant_loop())

# Start voice assistant in a background thread
threading.Thread(target=start_voice_assistant, daemon=True).start()

if __name__ == "__main__":
    try:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        pi.stop()
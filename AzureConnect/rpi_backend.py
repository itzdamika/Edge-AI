import asyncio
import threading
import time
import datetime
import board
import adafruit_dht
import adafruit_ssd1306
import busio
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
import adafruit_dht
dhtDevice = adafruit_dht.DHT22(board.D27)

# Initialize pigpio (ensure pigpiod is running)
import pigpio
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

# Lights
KITCHEN_LIGHT_PIN = 22
LIVINGROOM_AC_PIN = 23
BEDROOM_FAN_PIN = 24
for pin in [KITCHEN_LIGHT_PIN, LIVINGROOM_AC_PIN, BEDROOM_FAN_PIN]:
    pi.set_mode(pin, pigpio.OUTPUT)
    pi.write(pin, 0)

# Global states
kitchen_state = "off"
livingroom_state = "off"
bedroom_state = "off"

# (OLED code if needed)
import busio
import adafruit_ssd1306
i2c = busio.I2C(board.SCL, board.SDA)
display = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)
display.fill(0)
display.show()

def update_oled():
    """Minimal function to show states."""
    display.fill(0)
    display.text(f"Light:{kitchen_state.upper()}", 0, 0, 1)
    display.text(f"AC:{livingroom_state.upper()}", 0, 10, 1)
    display.text(f"Fan:{bedroom_state.upper()}", 0, 20, 1)
    display.show()

# ---------------------------
# Minimal Logging
# ---------------------------
systemLogs = []    # store toggles ("Light turned on", etc.)
voiceLogs = []     # store user queries + responses

def log_system(msg: str):
    entry = {
        "timestamp": time.time(),
        "message": msg
    }
    systemLogs.append(entry)
    # keep small
    if len(systemLogs) > 200:
        systemLogs.pop(0)

def log_voice(user: str, response: str):
    entry = {
        "timestamp": time.time(),
        "user_message": user,
        "assistant_response": response
    }
    voiceLogs.append(entry)
    if len(voiceLogs) > 200:
        voiceLogs.pop(0)

@app.get("/logs")
def get_logs():
    # return system logs
    return systemLogs

@app.get("/voicelogs")
def get_voicelogs():
    return voiceLogs

# Provide a minimal /lights endpoint returning the on/off states
@app.get("/lights")
def get_lights():
    return {
        "kitchen": kitchen_state,
        "livingroom": livingroom_state,
        "bedroom": bedroom_state
    }

# ---------------------------
# DHT Reading
# ---------------------------
def read_sensors():
    data = {}
    try:
        val_t = dhtDevice.temperature
        val_h = dhtDevice.humidity
        if val_t is not None and val_h is not None:
            data['temperature'] = val_t
            data['humidity'] = val_h
        else:
            logger.warning("DHT22 read returned None.")
            data['temperature'] = None
            data['humidity'] = None
    except Exception as e:
        err = str(e).lower()
        if "full buffer was not returned" in err:
            logger.warning("DHT partial read.")
        else:
            logger.error("DHT Error", error=str(e))
        data['temperature'] = None
        data['humidity'] = None

    # MQ-135
    try:
        val_aq = pi.read(AIR_QUALITY_PIN)
        data['air_quality'] = "Poor" if val_aq==1 else "Good"
    except:
        data['air_quality'] = None

    # motion
    try:
        val_mot = pi.read(MOTION_SENSOR_PIN)
        data['motion'] = True if val_mot==1 else False
    except:
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
def get_sensors():
    return latest_data

# ---------------------------
# Video feed
# ---------------------------
import cv2
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
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.1)
    cap.release()

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# ---------------------------
# Light Endpoints
# ---------------------------
def set_light_state(pin: int, st: str):
    pi.write(pin, 1 if st=='on' else 0)
    logger.info(f"Pin {pin} => {st}")

@app.get("/light/kitchen")
def control_kitchen_light(state: str):
    global kitchen_state
    if state not in ("on","off"):
        raise HTTPException(400, "Invalid state")
    set_light_state(KITCHEN_LIGHT_PIN, state)
    kitchen_state = state
    update_oled()
    log_system(f"Kitchen Light turned {state.upper()}")
    return {"light":"kitchen", "state":state}

@app.get("/light/livingroom")
def control_livingroom_ac(state: str):
    global livingroom_state
    if state not in ("on","off"):
        raise HTTPException(400, "Invalid state")
    set_light_state(LIVINGROOM_AC_PIN, state)
    livingroom_state = state
    update_oled()
    log_system(f"Living Room AC turned {state.upper()}")
    return {"light":"livingroom_ac","state":state}

@app.get("/light/bedroom")
def control_bedroom_fan(state: str):
    global bedroom_state
    if state not in ("on","off"):
        raise HTTPException(400, "Invalid state")
    set_light_state(BEDROOM_FAN_PIN, state)
    bedroom_state = state
    update_oled()
    log_system(f"Bedroom Fan turned {state.upper()}")
    return {"light":"bedroom_fan","state":state}

# ---------------------------
# GPT & Voice Assistant
# ---------------------------
from openai import AzureOpenAI
openai_client = AzureOpenAI(
    api_key=config.AZURE_OPENAI_API_KEY,
    api_version="2024-05-01-preview",
    azure_endpoint=config.AZURE_ENDPOINT
)

intent_prompt = """
Analyze the user message and classify its intent into one of the predefined categories:
1. command-query: controlling the home
2. general-query: general question
Reply with only 'command-query' or 'general-query'.
"""

general_prompt = """
You are a SmartAura Smart Home Assistant. Keep answers short and direct.
"""

command_prompt = """
We only have three devices:
1) Kitchen Light => 'kitchen-on'/'kitchen-off'
2) Living Room AC => 'ac-on'/'ac-off'
3) Bedroom Fan => 'fan-on'/'fan-off'

Examples:
- 'Lights on' => 'kitchen-on'
- 'Turn on the lights' => 'kitchen-on'
- 'Lights off' => 'kitchen-off'
- 'Turn off the lights' => 'kitchen-off'
- 'Turn on the AC' => 'ac-on'
- 'Turn off the AC' => 'ac-off'
- 'Turn on the fan' => 'fan-on'
- 'Turn off the fan' => 'fan-off'

If no match, respond with 'error' only.
"""

async def _create_completion(msgs):
    resp = await asyncio.to_thread(lambda: openai_client.chat.completions.create(
        messages=msgs, model=config.AZURE_OPENAI_API_KEY, max_tokens=100
    ))
    return resp.choices[0].message.content.strip()

async def handle_commands(usr:str)->str:
    # minimal
    msgs=[
        {"role":"system","content":command_prompt},
        {"role":"user","content":usr}
    ]
    cmd=await _create_completion(msgs)
    logger.info("Detected Command", intent=cmd)
    if cmd=="kitchen-on":
        set_light_state(KITCHEN_LIGHT_PIN,"on")
        global kitchen_state
        kitchen_state="on"
        update_oled()
        log_system("Kitchen Light turned ON")
        return "Turning on the kitchen light."
    # etc. for other commands ...
    return "Sorry, not recognized"

async def handle_general(usr:str)->str:
    msgs=[
        {"role":"system","content":general_prompt},
        {"role":"user","content":usr}
    ]
    ret=await _create_completion(msgs)
    return ret

async def process_user_query(usr:str):
    # which intent
    msgs=[
        {"role":"system","content":intent_prompt},
        {"role":"user","content":usr}
    ]
    got=await _create_completion(msgs)
    got=got.lower()
    if got=="command-query":
        ans=await handle_commands(usr)
    else:
        ans=await handle_general(usr)
    log_voice(usr,ans) # store in voice logs
    return ans

voiceLogs=[]

def log_voice(user_msg,assistant_rsp):
    voiceLogs.append({
        "timestamp":time.time(),
        "user": user_msg,
        "response":assistant_rsp
    })
    if len(voiceLogs)>200:voiceLogs.pop(0)

@app.get("/logs")
def get_logs():
    return systemLogs

@app.get("/voicelogs")
def get_voicelogs():
    return voiceLogs

speech_config = speechsdk.SpeechConfig(subscription=config.SPEECH_KEY, region=config.SERVICE_REGION)
speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_Endpoint, config.TTS_ENDPOINT)
speech_config.speech_synthesis_voice_name="en-US-JennyNeural"
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
speech_synthesizer=speechsdk.SpeechSynthesizer(speech_config, audio_config)

def recognize_speech(timeout=5):
    rec=sr.Recognizer()
    with sr.Microphone() as src:
        print("Listening...")
        rec.adjust_for_ambient_noise(src)
        try:
            audio=rec.listen(src,timeout=timeout)
            text=rec.recognize_google(audio)
            logger.info("Recognized speech", text=text)
            return text
        except:
            return None

def speak_text(txt:str):
    print(f"Speaking: {txt}")
    ret=speech_synthesizer.speak_text_async(txt).get()
    if ret.reason==speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech done.")
    else:
        print("Speech error.")

async def voice_loop():
    while True:
        print("Voice assistant waiting for input...")
        user_text=recognize_speech(5)
        if user_text:
            ans=await process_user_query(user_text)
            speak_text(ans)
        await asyncio.sleep(1)

def start_voice_assistant():
    asyncio.run(voice_loop())

threading.Thread(target=start_voice_assistant,daemon=True).start()

# ---------------------------
# Run
# ---------------------------
if __name__=="__main__":
    import uvicorn
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        pi.stop()
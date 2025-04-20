import speech_recognition as sr
import asyncio
from pydantic_settings import BaseSettings, SettingsConfigDict
from openai import AzureOpenAI
import structlog
import sys
import logging
import threading
import datetime
import azure.cognitiveservices.speech as speechsdk
from prompts import (
    intent_prompt, 
    general_prompt, 
    command_prompt
)

# ---------------------------------------------------------------------------
# Structured Logging Configuration
# ---------------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(message)s"
)

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

# ---------------------------------------------------------------------------
# Configuration Management with pydantic_settings (for Azure OpenAI)
# ---------------------------------------------------------------------------
class Config(BaseSettings):
    """
    Application configuration using pydantic_settings.
    Loads environment variables from a .env file.
    """
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_DEPLOYMENT_ID: str
    AZURE_ENDPOINT: str
    SPEECH_KEY: str
    SERVICE_REGION: str
    TTS_ENDPOINT: str
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

# Load config
config = Config()

# Initialize Azure OpenAI client
openai_client = AzureOpenAI(
    api_key=config.AZURE_OPENAI_API_KEY,
    api_version="2024-05-01-preview",
    azure_endpoint=config.AZURE_ENDPOINT,
)

# -----------------------------------------------------------------------------
# Conversation Graph with Thread Safety
# -----------------------------------------------------------------------------
class ConversationGraph:
    """
    A thread-safe graph structure to manage conversation context.
    """
    def __init__(self) -> None:
        self.nodes = []
        self.lock = threading.Lock()

    def add_message(self, message: str, role: str) -> None:
        with self.lock:
            self.nodes.append({
                "message": message,
                "role": role,
                "timestamp": datetime.datetime.now(datetime.timezone.utc)
            })

    def get_relevant_context(self, query: str, top_n: int = 3) -> str:
        with self.lock:
            relevant_nodes = self.nodes[-top_n:]
            return "\n".join([f"{node['role']}: {node['message']}" for node in relevant_nodes])
    
    def clear_history(self) -> None:
        """
        Clears the conversation history.
        """
        with self.lock:
            self.nodes.clear()
            logger.info("Conversation history cleared.")

conversation_graph = ConversationGraph()

# -----------------------------------------------------------------------------
# Device State Manager for Saving Commands
# -----------------------------------------------------------------------------
class DeviceStateManager:
    """
    A thread-safe manager to store and update the state of devices.
    """
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.state = {
            "ac": {"status": "off", "temperature": None},
            "fan": {"status": "off", "speed": None},
            "light": {"status": "off"}
        }
    
    def set_ac_on(self) -> bool:
        with self.lock:
            if self.state["ac"]["status"] == "on":
                return False
            self.state["ac"]["status"] = "on"
            return True

    def set_ac_off(self) -> bool:
        with self.lock:
            if self.state["ac"]["status"] == "off":
                return False
            self.state["ac"]["status"] = "off"
            self.state["ac"]["temperature"] = None
            return True

    def set_ac_temperature(self, temp: int) -> (bool, str): # type: ignore
        with self.lock:
            if self.state["ac"]["status"] != "on":
                # If AC is off, turn it on with the given temperature.
                self.state["ac"]["status"] = "on"
                self.state["ac"]["temperature"] = temp
                return True, f"Turning on the AC and setting temperature to {temp}°C."
            if self.state["ac"]["temperature"] == temp:
                return False, f"AC is already set to {temp}°C."
            self.state["ac"]["temperature"] = temp
            return True, f"Setting the AC temperature to {temp}°C."

    def set_fan_on(self) -> bool:
        with self.lock:
            if self.state["fan"]["status"] == "on":
                return False
            self.state["fan"]["status"] = "on"
            return True

    def set_fan_off(self) -> bool:
        with self.lock:
            if self.state["fan"]["status"] == "off":
                return False
            self.state["fan"]["status"] = "off"
            self.state["fan"]["speed"] = None
            return True

    def set_fan_speed(self, speed: int) -> (bool, str): # type: ignore
        with self.lock:
            if self.state["fan"]["status"] != "on":
                return False, "Fan is not on."
            if self.state["fan"]["speed"] == speed:
                return False, f"Fan is already set to speed {speed}."
            self.state["fan"]["speed"] = speed
            return True, f"Setting the fan speed to {speed}."

    def set_light_on(self) -> bool:
        with self.lock:
            if self.state["light"]["status"] == "on":
                return False
            self.state["light"]["status"] = "on"
            return True

    def set_light_off(self) -> bool:
        with self.lock:
            if self.state["light"]["status"] == "off":
                return False
            self.state["light"]["status"] = "off"
            return True

# Global device state manager instance.
device_state_manager = DeviceStateManager()

# ---------------------------------------------------------------------------
# Azure Speech Service Configuration for Natural Neural Voice
# ---------------------------------------------------------------------------
speech_config = speechsdk.SpeechConfig(subscription=config.SPEECH_KEY, region=config.SERVICE_REGION)
speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_Endpoint, config.TTS_ENDPOINT)
speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
audio_config = speechsdk.audio.AudioOutputConfig(use_default_speaker=True)
speech_synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

# ---------------------------------------------------------------------------
# Speech Recognition Function
# ---------------------------------------------------------------------------
def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source, timeout=5)
            text = recognizer.recognize_google(audio)
            logger.info("User Message", text=text)
            return text
        except sr.UnknownValueError:
            logger.error("Could not understand the audio")
            return None
        except sr.RequestError:
            logger.error("Could not request results, check your internet connection")
            return None

# ---------------------------------------------------------------------------
# OpenAI Completion Helper
# ---------------------------------------------------------------------------
async def _create_completion(messages: list, **kwargs) -> str:
    """
    Helper function to reduce repetitive code for calling the OpenAI API.
    Runs the API call in a thread.
    """
    default_kwargs = {
        "model": config.AZURE_OPENAI_DEPLOYMENT_ID,
        "max_tokens": 100,
        "temperature": 0.7,
        "top_p": 0.95,
    }
    default_kwargs.update(kwargs)
    response = await asyncio.to_thread(
        lambda: openai_client.chat.completions.create(
            messages=messages, **default_kwargs
        )
    )
    return response.choices[0].message.content.strip()

# ---------------------------------------------------------------------------
# Command Handling Functions
# ---------------------------------------------------------------------------
async def handle_commands(user_message: str) -> str:
    messages = [
        {"role": "system", "content": command_prompt},
        {"role": "user", "content": f"Current Command: {user_message}"}
    ]
    command = await _create_completion(messages)
    logger.info("Detected Command", intent=command)

    # Handle AC commands with state checking
    if command == "ac-control-on":
        if not device_state_manager.set_ac_on():
            return "AC is already turned on."
        return "Turning on the AC."
    elif command == "ac-control-off":
        if not device_state_manager.set_ac_off():
            return "AC is already turned off."
        return "Turning off the AC."
    elif command.startswith("ac-control-"):
        try:
            ac_temp = int(command.split("-")[-1])
            success, msg = device_state_manager.set_ac_temperature(ac_temp)
            return msg
        except ValueError:
            return "Invalid temperature setting for AC."
    
    # Handle Fan commands with state checking
    elif command == "fan-control-on":
        if not device_state_manager.set_fan_on():
            return "Fan is already turned on."
        return "Turning on the Fan."
    elif command == "fan-control-off":
        if not device_state_manager.set_fan_off():
            return "Fan is already turned off."
        return "Turning off the Fan."
    elif command.startswith("fan-control-"):
        try:
            fan_speed = int(command.split("-")[-1])
            if fan_speed not in [1, 2, 3]:
                return "Invalid fan speed. Please choose between 1, 2, or 3."
            success, msg = device_state_manager.set_fan_speed(fan_speed)
            return msg
        except ValueError:
            return "Invalid fan speed setting."
    
    # Handle Light commands with state checking
    elif command == "light-control-on":
        if not device_state_manager.set_light_on():
            return "Light is already turned on."
        return "Turning on the Light."
    elif command == "light-control-off":
        if not device_state_manager.set_light_off():
            return "Light is already turned off."
        return "Turning off the Light."
    elif command == "no-access":
        return "Sorry, I don't have access to that device."

    return "Sorry, I didn't understand your request."

async def handle_general(user_message: str) -> str:
    context = conversation_graph.get_relevant_context(user_message)
    messages = [
        {"role": "system", "content": general_prompt},
        {"role": "user", "content": f"Current Question: {user_message}"},
        {"role": "user", "content": f"User past message context: {context}"}
    ]
    return await _create_completion(messages)

async def process_user_query(user_message: str):
    try:
        conversation_graph.add_message(user_message, "user")
        intent_messages = [
            {"role": "system", "content": intent_prompt},
            {"role": "user", "content": user_message},
        ]
        detected_intent = (await _create_completion(intent_messages)).lower()
        logger.info("Detected Intent", intent=detected_intent)

        if detected_intent == "command-query":
            response_text = await handle_commands(user_message)
        elif detected_intent == "general-query":
            response_text = await handle_general(user_message)
        else:
            response_text = "I'm not sure what you're asking."
        
        conversation_graph.add_message(response_text, "assistant")
        return response_text
    except Exception as e:
        logger.error("Error in process_message", error=str(e))
        return "An error occurred while processing your request."

# ---------------------------------------------------------------------------
# Speak Response using Azure Neural TTS
# ---------------------------------------------------------------------------
def speak_response(response_text):
    print(f"GPT Response: {response_text}")
    result = speech_synthesizer.speak_text_async(response_text).get()
    if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
        print("Speech synthesized successfully.")
    else:
        cancellation_details = result.cancellation_details
        print("Speech synthesis canceled:", cancellation_details.reason)
        print("Error details:", cancellation_details.error_details)

# ---------------------------------------------------------------------------
# Background Task to Clear Conversation History Periodically
# ---------------------------------------------------------------------------
async def clear_history_periodically():
    while True:
        await asyncio.sleep(1800)
        conversation_graph.clear_history()

# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------
async def main():
    # Start the periodic conversation history clearing task.
    asyncio.create_task(clear_history_periodically())
    while True:
        user_text = recognize_speech()
        if user_text:
            response = await process_user_query(user_text)
            logger.info("Assistant Response", response=response)
            speak_response(response)

if __name__ == "__main__":
    asyncio.run(main())

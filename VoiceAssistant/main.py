import speech_recognition as sr
import asyncio
from pydantic_settings import BaseSettings, SettingsConfigDict
from openai import AzureOpenAI
import structlog
import sys
import logging
import azure.cognitiveservices.speech as speechsdk
from prompts import (intent_prompt, general_prompt, command_prompt)

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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

# Load config
config = Config()

# Initialize Azure OpenAI client
openai_client = AzureOpenAI(
    api_key=config.AZURE_OPENAI_API_KEY,
    api_version="2024-05-01-preview",
    azure_endpoint=config.AZURE_ENDPOINT,
)

# ---------------------------------------------------------------------------
# Azure Speech Service Configuration for Natural Neural Voice
# ---------------------------------------------------------------------------
SPEECH_KEY = "AmewBM3Olz7oZeVnhVp2tqAdQ6wbuHGFIhTUcO1GFNP2CmAYLOn9JQQJ99BCACqBBLyXJ3w3AAAYACOGeDlD"
SERVICE_REGION = "southeastasia"
TTS_ENDPOINT = "https://southeastasia.tts.speech.microsoft.com/cognitiveservices/v1"

speech_config = speechsdk.SpeechConfig(subscription=SPEECH_KEY, region=SERVICE_REGION)
speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_Endpoint, TTS_ENDPOINT)
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

    if command == "ac-control-on":
        return "Turning on the AC."
    elif command == "ac-control-off":
        return "Turning off the AC."
    elif command.startswith("ac-control-"):
        try:
            ac_temp = int(command.split("-")[-1])
            return f"Setting the AC temperature to {ac_temp}°C."
        except ValueError:
            return "Invalid temperature setting for AC."
    elif command == "fan-control-on":
        return "Turning on the Fan."
    elif command == "fan-control-off":
        return "Turning off the Fan."
    elif command.startswith("fan-control-"):
        try:
            fan_speed = int(command.split("-")[-1])
            if fan_speed in [1, 2, 3]:
                return f"Setting the fan speed to {fan_speed}."
            else:
                return "Invalid fan speed. Please choose between 1, 2, or 3."
        except ValueError:
            return "Invalid fan speed setting."
    elif command == "light-control-on":
        return "Turning on the Light."
    elif command == "light-control-off":
        return "Turning off the Light."
    elif command == "no-access":
        return "Sorry, I don't have access to that device."

    return "Sorry, I didn't understand your request."

async def handle_general(user_message: str) -> str:
    messages = [
        {"role": "system", "content": general_prompt},
        {"role": "user", "content": f"Current Question: {user_message}"}
    ]
    return await _create_completion(messages)

async def process_user_query(user_message: str):
    try:
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
        # Access cancellation details directly from the result
        cancellation_details = result.cancellation_details
        print("Speech synthesis canceled:", cancellation_details.reason)
        print("Error details:", cancellation_details.error_details)

# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------
async def main():
    while True:
        user_text = recognize_speech()
        if user_text:
            response = await process_user_query(user_text)
            logger.info("Assistant Response", response=response)
            speak_response(response)

if __name__ == "__main__":
    asyncio.run(main())

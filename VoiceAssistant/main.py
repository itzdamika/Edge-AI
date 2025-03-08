import speech_recognition as sr
import pyttsx3
import asyncio
from pydantic_settings import BaseSettings, SettingsConfigDict
from openai import AzureOpenAI
import structlog
import sys
import logging
from prompts import ( intent_prompt, general_prompt, command_prompt )

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
# Configuration Management with pydantic_settings
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

# Initialize Text-to-Speech Engine
engine = pyttsx3.init()
engine.setProperty("rate", 150)  # Adjust speech rate

# Function to capture voice input
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

async def handle_commands(user_message: str) -> str:
    messages = [
        {"role": "system", "content": command_prompt},
        {"role": "user", "content": f"Current Command: {user_message}"}
    ]
    command = await _create_completion(messages)
    logger.info("Detected Command", intent=command)

    if command.startswith("ac-control-"):
        ac_temp = command.split("-")[-1] if command != "ac-error" else None
        return f"Setting the AC temperature to {ac_temp}°C" if ac_temp else "AC command not recognized."

    elif command.startswith("fan-control-"):
        fan_speed = command.split("-")[-1] if command != "fan-error" else None
        return f"Setting the fan speed to {fan_speed}" if fan_speed else "Fan command not recognized."

    elif command == "light-control-on":
        return "Turning on the Light"
    elif command == "light-control-off":
        return "Turning off the Light"

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

def speak_response(response_text):
    print(f"GPT Response: {response_text}")
    engine.say(response_text)
    engine.runAndWait()

async def main():
    while True:
        user_text = recognize_speech()
        if user_text:
            response = await process_user_query(user_text)
            logger.info("Assistant Response", response=response)
            speak_response(response)

if __name__ == "__main__":
    asyncio.run(main())


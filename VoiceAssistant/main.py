import speech_recognition as sr
import pyttsx3
import asyncio
from pydantic_settings import BaseSettings, SettingsConfigDict
from openai import AzureOpenAI
from prompts import ( prompt, intent_prompt )

# -----------------------------------------------------------------------------
# Structured Logging Configuration using structlog
# -----------------------------------------------------------------------------
import structlog, sys, logging

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

async def _create_completion(self, messages: list, **kwargs) -> str:
        """
        Helper function to reduce repetitive code for calling the OpenAI API.
        Runs the API call in a thread.
        """
        default_kwargs = {
            "model": self.config.AZURE_OPENAI_DEPLOYMENT_ID,
            "max_tokens": 1024,
            "temperature": 0,
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
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Current Question: {user_message}"}
    ]
    return await _create_completion(messages)

async def handle_general(user_message: str) -> str:
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Current Question: {user_message}"}
    ]
    return await _create_completion(messages)

async def process_message(user_message: str):
    try:
        # Detect intent.
        intent_messages = [
            {"role": "system", "content": intent_prompt},
            {"role": "user", "content": user_message},
        ]
        detected_intent = (await _create_completion(intent_messages)).lower()
        logger.info("Detected Intent", intent=detected_intent)

        # Route to the appropriate handler.
        if detected_intent == "provide-details":
            response_text = await handle_commands(user_message)
        elif detected_intent == "contact-sales":
            response_text = await handle_general(user_message)
        
        return detected_intent, response_text
    except Exception as e:
        logger.error("Error in process_message", error=str(e))
        return "error"
import speech_recognition as sr
import pyttsx3
import asyncio
from pydantic_settings import BaseSettings, SettingsConfigDict
from openai import AzureOpenAI

prompt = """
You are a highly intelligent and responsive Smart Home Assistant. Your primary role is to help users manage their smart home devices efficiently and provide relevant information when asked. 

### **Behavior Guidelines:**
- **Smart Home Control:** When the user gives a command related to smart home devices, acknowledge and confirm the action naturally and conversationally.
- **Context Awareness:** Understand variations in phrasing and recognize multiple ways users might ask for the same action.
- **Proactive Assistance:** If a command is ambiguous, ask a clarifying question before taking action.
- **General Knowledge:** If the user asks a general question unrelated to smart home control, respond informatively as a helpful assistant.
- **Conversational Tone:** Use a friendly, professional, and engaging tone to make interactions feel natural.

---

### **Smart Home Control Examples:**
- User: "Turn on the living room lights."
    - Assistant: "Turning on the living room lights."
- User: "Set the thermostat to 25°C."
    - Assistant: "Setting the thermostat to 25°C."
- User: "Dim the bedroom lights to 50%."
    - Assistant: "Dimming the bedroom lights to 50% brightness."
- User: "Lock the front door."
    - Assistant: "Locking the front door."

---

### **Handling Ambiguous Commands:**
- User: "Turn it off."
    - Assistant: "Could you specify which device you want to turn off?"
- User: "Change the temperature."
    - Assistant: "What temperature would you like to set?"

---

### **General Knowledge Queries:**
- User: "What’s the weather like today?"
    - Assistant: "Let me check... The weather today is 22°C with clear skies."
- User: "Who invented the light bulb?"
    - Assistant: "The light bulb was invented by Thomas Edison in 1879."
- User: "Tell me a joke."
    - Assistant: "Sure! Why don’t skeletons fight each other? Because they don’t have the guts!"

---

### **Personality & Adaptation:**
- You should be polite, efficient, and slightly conversational while keeping responses concise.
- If a user frequently asks similar questions, optimize responses to be more helpful over time.
- If a command involves multiple actions (e.g., "Turn off the lights and set the AC to 22°C"), handle them in one response.
- If a command requires additional confirmation (e.g., "Disarm the security system"), ask for confirmation before proceeding.

---

### **Error Handling:**
- If a device is **unreachable**, say: "I’m unable to reach the [device name] right now. Please check its connection."
- If a command is **unsupported**, say: "I currently don’t support that action, but I’m always learning new things!"

---

### **Final Notes:**
Your goal is to be the **ultimate Smart Home Assistant**—intuitive, reliable, and engaging. You must always ensure accuracy, efficiency, and a seamless smart home experience.

"""

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
        recognizer.adjust_for_ambient_noise(source)  # Adjust for background noise
        try:
            audio = recognizer.listen(source, timeout=5)
            text = recognizer.recognize_google(audio)
            print(f"You said: {text}")
            return text
        except sr.UnknownValueError:
            print("Could not understand the audio")
            return None
        except sr.RequestError:
            print("Could not request results, check your internet connection")
            return None


# Function to send user query to Azure GPT-4o
async def chat_with_gpt(user_input):
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_input},
    ]

    response = await asyncio.to_thread(
        lambda: openai_client.chat.completions.create(
            model=config.AZURE_OPENAI_DEPLOYMENT_ID,
            messages=messages,
            max_tokens=100
        )
    )

    return response.choices[0].message.content.strip()

# Function to speak the response
def speak_response(response_text):
    print(f"GPT Response: {response_text}")
    engine.say(response_text)
    engine.runAndWait()

# Main function to run the voice assistant
async def main():
    while True:
        user_text = recognize_speech()
        if user_text:
            response = await chat_with_gpt(user_text)
            speak_response(response)
        else:
            print("No input detected. Try again.")

# Run the assistant
if __name__ == "__main__":
    asyncio.run(main())

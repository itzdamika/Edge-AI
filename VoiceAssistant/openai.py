import speech_recognition as sr
import pyttsx3
import asyncio
import os
from dotenv import load_dotenv
from openai import AzureOpenAI

# Load environment variables
load_dotenv()

# Azure OpenAI Credentials
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT_ID = os.getenv("AZURE_OPENAI_DEPLOYMENT_ID")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT")

# Initialize Azure OpenAI client
openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version="2024-05-01-preview",
    azure_endpoint=AZURE_ENDPOINT,
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
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": user_input},
    ]

    response = await asyncio.to_thread(
        lambda: openai_client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT_ID,
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

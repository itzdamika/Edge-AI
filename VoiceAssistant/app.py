import speech_recognition as sr
import google.auth
from googleapiclient.discovery import build

def recognize_speech():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

    try:
        command = recognizer.recognize_google(audio)
        print(f"You said: {command}")
        return command.lower()
    except sr.UnknownValueError:
        print("Sorry, I didn't understand that.")
    except sr.RequestError:
        print("Could not request results, check your internet connection.")

if __name__ == "__main__":
    while True:
        text = recognize_speech()
        if text:
            if "turn on the light" in text:
                print("Simulating turning ON the light")
            elif "turn off the light" in text:
                print("Simulating turning OFF the light")
            elif "exit" in text:
                print("Exiting...")
                break
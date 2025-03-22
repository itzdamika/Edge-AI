# pc_backend.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import threading, time, requests

app = FastAPI()

# Enable CORS so your React dashboard can access this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this in production to your dashboard domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# URL of your Raspberry Pi sensor backend.
RPi_BACKEND_URL = "http://192.168.1.13:8000/sensors"  # Replace with your Pi's IP

# Global variable to store the latest sensor data.
latest_sensor_data = {}

def poll_rpi_backend():
    global latest_sensor_data
    while True:
        try:
            response = requests.get(RPi_BACKEND_URL, timeout=5)
            if response.status_code == 200:
                latest_sensor_data = response.json()
                print("Updated sensor data:", latest_sensor_data)
            else:
                print("Error: Received status code", response.status_code)
        except Exception as e:
            print("Error polling RPi backend:", e)
        time.sleep(5)  # Poll every 5 seconds

# Start the polling thread
threading.Thread(target=poll_rpi_backend, daemon=True).start()

@app.get("/latest")
def get_latest_data():
    """Return the latest sensor data from the Raspberry Pi."""
    return latest_sensor_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)

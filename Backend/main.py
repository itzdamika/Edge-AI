from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Literal
import json
from datetime import datetime
import uuid
import cv2 # type: ignore

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize camera
camera = cv2.VideoCapture(0)

def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.get("/video_feed")
async def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# Data models
class User(BaseModel):
    id: str
    username: str
    password: str
    role: Literal["admin", "guest"]

class Device(BaseModel):
    id: str
    name: str
    type: Literal["ac", "fan", "light"]
    status: bool
    temperature: Optional[int] = None
    speed: Optional[int] = None

class LoginRequest(BaseModel):
    username: str
    password: str

# Load users from JSON file
def load_users():
    try:
        with open("users.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        # Create default users if file doesn't exist
        default_users = [
            {
                "id": str(uuid.uuid4()),
                "username": "admin",
                "password": "admin123",
                "role": "admin"
            },
            {
                "id": str(uuid.uuid4()),
                "username": "guest",
                "password": "guest123",
                "role": "guest"
            }
        ]
        with open("users.json", "w") as f:
            json.dump(default_users, f)
        return default_users

# Initialize devices
devices = [
    {
        "id": str(uuid.uuid4()),
        "name": "Living Room AC",
        "type": "ac",
        "status": False,
        "temperature": 24
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Bedroom Fan",
        "type": "fan",
        "status": False,
        "speed": 1
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Kitchen Light",
        "type": "light",
        "status": False
    }
]

@app.post("/login")
async def login(request: LoginRequest):
    users = load_users()
    user = next(
        (user for user in users if user["username"] == request.username and user["password"] == request.password),
        None
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user

@app.get("/devices")
async def get_devices():
    return devices

@app.put("/devices/{device_id}")
async def update_device(device_id: str, device: Device):
    device_index = next(
        (index for (index, d) in enumerate(devices) if d["id"] == device_id),
        None
    )
    if device_index is None:
        raise HTTPException(status_code=404, detail="Device not found")
    
    devices[device_index].update(device.dict(exclude_unset=True))
    return devices[device_index]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
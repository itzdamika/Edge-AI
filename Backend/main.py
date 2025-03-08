from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Literal
import json
from datetime import datetime
import uuid

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def load_users():
    try:
        with open("users.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
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
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: str

class User(BaseModel):
    username: str

@app.post("/login", response_model=User)
async def login(request: LoginRequest):
    if request.username == "user" and request.password == "123":
        return User(username=request.username)
    raise HTTPException(status_code=401, detail="Invalid credentials")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

class Message(BaseModel):
    text: str

@app.get("/")
async def read_root():
    return {"message": "Hello from gemini-scribe-tutor Python example"}

@app.post("/echo")
async def echo(msg: Message):
    return {"echo": msg.text}

if __name__ == "__main__":
    import uvicorn

    # Run with: python -m uvicorn python.example_app:app --reload
    uvicorn.run("python.example_app:app", host="127.0.0.1", port=8000, reload=True)

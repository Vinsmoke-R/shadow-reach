from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from sheets_reader import read_sheet

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}

# --- Request Models ---
class SheetRequest(BaseModel):
    sheet_id: str

class DecisionRequest(BaseModel):
    choice: str   # approve / rewrite / skip


# --- 1. Health check ---
@app.get("/")
def root():
    return {"message": "API is working"}

# --- 2. Set sheet ID ---
@app.post("/sheets")
def set_sheet(request: SheetRequest):
    sessions["sheet_id"] = request.sheet_id
    return {"message": f"Sheet ID saved: {request.sheet_id}"}


# --- 3. Upload resume + start agent ---
@app.post("/start")
async def start(resume: UploadFile = File(...)):
    resume_bytes = await resume.read()
    sessions["resume_bytes"] = resume_bytes
    return {"message": "Resume uploaded, agent starting..."}

# --- 4. Send decision ---
@app.post("/decision")
def decision(request: DecisionRequest):

    choice = request.choice

    if choice == "approve":
        return {
            "message": "Application approved"
        }

    elif choice == "rewrite":
        return {
            "message": "Rewrite requested"
        }

    elif choice == "skip":
        return {
            "message": "Application skipped"
        }

    return {
        "error": "Invalid choice"
    }
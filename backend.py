from typing import Optional
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.types import Command
import uuid

from main import cold_reach

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}    # holds the sheet_id between /sheets and /start


# --- Request Models ---
class SheetRequest(BaseModel):
    sheet_id: str


class DecisionRequest(BaseModel):
    choice: str                       # approve / rewrite / skip
    subject: Optional[str] = None
    body: Optional[str] = None
    thread_id: Optional[str] = None


# --- Helpers ---
def make_config(thread_id: str):
    # high recursion_limit because the graph loops once per contact
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 1000}


def build_response(config, thread_id: str):
    state = cold_reach.get_state(config)
    if state.tasks and state.tasks[0].interrupts:
        d = state.tasks[0].interrupts[0].value
        return {
            "status": "paused",
            "thread_id": thread_id,
            "draft": d["email_body"],
            "subject": d.get("subject", "Applying for AI Intern Role"),
            "contact": d["contact"],
            "progress": d.get("progress"),
            "options": d["options"],
        }
    return {
        "status": "done",
        "thread_id": thread_id,
        "sent_count": state.values.get("sent_count", 0),
    }


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
    thread_id = str(uuid.uuid4())
    config = make_config(thread_id)

    cold_reach.invoke(
        {
            "resume_bytes": resume_bytes,
            "resume_data": {},
            "sheet_id": sessions.get("sheet_id"),
            "doc_bytes": None,
            "file_type": None,
            "contacts": [],
            "sent_count": 0,
        },
        config=config,
    )
    return build_response(config, thread_id)


# --- 4. Send decision ---
@app.post("/decision")
def decision(request: DecisionRequest):
    if not request.thread_id:
        return {"error": "No active session. Please start first."}
    config = make_config(request.thread_id)

    cold_reach.invoke(
        Command(resume={
            "choice": request.choice,
            "subject": request.subject,
            "body": request.body,
        }),
        config=config,
    )
    return build_response(config, request.thread_id)
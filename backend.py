from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langgraph.types import Command
import uvicorn

from sheets_reader import read_sheet
from main import cold_reach

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = {}    # local session that we are going to use 

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
    initial_state = {
            "resume_bytes": resume_bytes,
            "resume_data": {},
            "sheet_id":None,
            "doc_bytes": None,
            "file_type": None,
            "contacts": [],
            "sent_count": 0
        }
    
    config = {
        "configurable": {
            "thread_id": "cold-reach-1"
        }
    }
    sessions["config"] = config   # storing config in session so that we can use same session it further 

    cold_reach.invoke(
        initial_state,
        config=config
    )

    state = cold_reach.get_state(config)

    # check if there are interrupts
    if state.tasks and state.tasks[0].interrupts:
        interrupt_data = state.tasks[0].interrupts[0].value
        return {
            "status": "paused",
            "draft": interrupt_data["email_body"],
            "contact": interrupt_data["contact"],
            "options": interrupt_data["options"]
        }

    return {"status": "done", "sent_count": 0}

# --- 4. Send decision ---
@app.post("/decision")
def decision(request: DecisionRequest):
    config = sessions.get("config")   # get the same config that we were using 

    if not config:
        return {"error": "No active session. Please start first."}

    # resume graph with user decision
    cold_reach.invoke(
        Command(resume=request.choice),  # resume graph with user decision 
        config=config
    )

    # get updated state
    state = cold_reach.get_state(config)  # get current graph state

    # check if done
    if state.next == ():   # this means graph is finished 
        sent = state.values.get("sent_count", 0)
        return {
            "status": "done",
            "sent_count": sent,
            "message": f"All done! Sent to {sent} contacts."
        }

    # get next interrupt
    if state.tasks and state.tasks[0].interrupts:
        interrupt_data = state.tasks[0].interrupts[0].value
        return {
            "status": "paused",
            "draft": interrupt_data["email_body"],
            "contact": interrupt_data["contact"],
            "options": interrupt_data["options"]
        }

    return {"status": "done"}
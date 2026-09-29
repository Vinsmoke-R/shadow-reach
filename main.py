from langgraph.graph import StateGraph, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from typing import TypedDict, List, Optional
from pydantic import BaseModel, EmailStr
from dotenv import load_dotenv
import os

load_dotenv()

from sheets_reader import read_sheet
from data_extract import extract_from_document, extract_resume_data
from llm import draft_mail
from sheets_reader import SHEET_ID, RANGE


llm = ChatGroq(
    model="openai/gpt-oss-120b",  # current and reliable
    temperature=0,
    max_tokens = 2000,
)

# --- Shared State ---
class AgentState(TypedDict):
    resume_bytes: bytes        # raw resume PDF
    resume_data: dict          # extracted resume details
    doc_bytes: Optional[bytes] # uploaded HR doc (optional)
    file_type: Optional[str]   # pdf/png/jpg
    contacts: List[dict]       # extracted HR contacts
    # approved: bool             # human approved sending?
    sent_count: int            # how many emails sent

@tool
def send_mail():
    pass

def load_resume(state: AgentState):
    resume = extract_resume_data(state['resume_bytes'])
    return {"resume_data": resume}   

def extract_data(state: AgentState):
    user_input = input("Please select your method").strip().lower()
    if user_input == "sheets":
        service = read_sheet()
        sheet = service.spreadsheets()
        result = sheet.values().get(
            spreadsheetId=SHEET_ID, range=RANGE).execute()
        rows = result.get('values', [])
        return {"contacts":rows}
    else:
        contacts = extract_from_document(state['doc_bytes'], state['file_type'])
        return {"contacts":contacts}

def draft_mails(state: AgentState):
    for contact in state['contacts']:
        draft_mail(contact, state['resume_data'])


graph = StateGraph()
graph.add_node("load_resume", load_resume)
graph.add_node("extract_data", extract_data)
graph.add_node("draft", draft_mails)
# graph.add_node("human_review", human_review)

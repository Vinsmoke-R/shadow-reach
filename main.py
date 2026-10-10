from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq
from typing import TypedDict, List, Optional
from dotenv import load_dotenv

load_dotenv()

from sheets_reader import read_sheet
from data_extract import extract_from_document, extract_resume_data
from llm import draft_mail, Contact
from gmail_reader import send_mail


llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    max_tokens=2000,
)

DEFAULT_SUBJECT = "Applying for AI Intern Role"


# --- Shared State ---
class AgentState(TypedDict):
    resume_bytes: bytes
    resume_data: dict
    sheet_id: Optional[str]
    doc_bytes: Optional[bytes]
    file_type: Optional[str]
    contacts: List[list]        # data rows only (header already removed)
    idx: int                    # which contact we're on
    current_contact: dict
    current_email: str
    decision: dict              # {"choice", "subject", "body"}
    sent_count: int


# --- Nodes ---
def load_resume(state: AgentState):
    return {"resume_data": extract_resume_data(state["resume_bytes"])}


def extract_data(state: AgentState):
    if state["sheet_id"]:
        rows = read_sheet(state["sheet_id"])
    else:
        rows = extract_from_document(state["doc_bytes"], state["file_type"])
    print(f"Loaded {len(rows)} rows (including header):", rows)
    return {"contacts": rows[1:], "idx": 0}      # skip header once, here


def prepare_contact(state: AgentState):
    rows, i = state["contacts"], state["idx"]
    while i < len(rows):
        row = rows[i]
        try:
            contact = Contact(
                name=row[0] if len(row) > 0 else "HR",
                company=row[1] if len(row) > 1 else "Company",
                email=row[2] if len(row) > 2 else None,
            )
            return {"idx": i, "current_contact": contact.model_dump()}
        except Exception:
            print(f"Skipping row {i}: invalid contact {row}")
            i += 1
    return {"idx": i}


def after_prepare(state: AgentState):
    return END if state["idx"] >= len(state["contacts"]) else "draft"


def draft(state: AgentState):
    contact = Contact(**state["current_contact"])
    return {"current_email": draft_mail(contact, state["resume_data"])}


def review(state: AgentState):
    # ONLY the interrupt here: no side effects before it
    decision = interrupt({
        "email_body": state["current_email"],
        "subject": DEFAULT_SUBJECT,
        "contact": state["current_contact"],
        "progress": {"current": state["idx"] + 1, "total": len(state["contacts"])},
        "options": ["approve", "rewrite", "skip"],
    })
    return {"decision": decision}


def after_review(state: AgentState):
    return {"approve": "send", "rewrite": "draft", "skip": "skip"}[state["decision"]["choice"]]


def send(state: AgentState):
    d = state["decision"]
    send_mail(
        to=state["current_contact"]["email"],
        subject=d.get("subject") or DEFAULT_SUBJECT,
        body=d.get("body") or state["current_email"],   # uses your edited text
        attachment_bytes=state["resume_bytes"],
        filename="resume.pdf",
    )
    return {"sent_count": state["sent_count"] + 1, "idx": state["idx"] + 1}


def skip(state: AgentState):
    return {"idx": state["idx"] + 1}


# --- Graph ---
graph = StateGraph(AgentState)
for name, fn in [
    ("load_resume", load_resume),
    ("extract_data", extract_data),
    ("prepare", prepare_contact),
    ("draft", draft),
    ("review", review),
    ("send", send),
    ("skip", skip),
]:
    graph.add_node(name, fn)

graph.add_edge(START, "load_resume")
graph.add_edge("load_resume", "extract_data")
graph.add_edge("extract_data", "prepare")
graph.add_conditional_edges("prepare", after_prepare, ["draft", END])
graph.add_edge("draft", "review")
graph.add_conditional_edges("review", after_review, ["send", "draft", "skip"])
graph.add_edge("send", "prepare")
graph.add_edge("skip", "prepare")

cold_reach = graph.compile(checkpointer=MemorySaver())
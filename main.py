from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq
from typing import TypedDict, List, Optional
from dotenv import load_dotenv
from pydantic import ValidationError

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
    col_map: dict   # {"name": 0, "company": 1, "email": 2}
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

def detect_columns(header: list[str]) -> dict:
    """Map 'email' / 'company' / 'name' to their column index using the header row."""
    cols = {}
    for idx, cell in enumerate(header):
        h = cell.strip().lower()
        if "mail" in h:
            cols.setdefault("email", idx)
        elif "company" in h or "organi" in h:      # check before 'name'
            cols.setdefault("company", idx)
        elif "name" in h:
            cols.setdefault("name", idx)
    return cols


def get_cell(row: list[str], col) -> str | None:
    # Sheets API drops trailing empty cells, so rows can be shorter than the header
    if col is None or col >= len(row):
        return None
    return row[col].strip() or None

def prepare_contact(state: AgentState):
    rows = state["contacts"]
    cols = state.get("col_map") or detect_columns(rows[0])   # detect once, then reuse

    if "email" not in cols:
        raise ValueError(f"No email column found in header: {rows[0]}")

    i = max(state["idx"], 1)          # row 0 is the header, so skip it
    while i < len(rows):
        row = rows[i]
        try:
            contact = Contact(
                name=get_cell(row, cols.get("name")) or "HR",
                company=get_cell(row, cols.get("company")) or "your company",
                email=get_cell(row, cols.get("email")),
            )
            return {"idx": i, "col_map": cols, "current_contact": contact.model_dump()}
        except ValidationError:
            print(f"Skipping row {i}: invalid contact {row}")
            i += 1
    return {"idx": i, "col_map": cols}


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
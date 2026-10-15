from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq
from typing import TypedDict, List, Optional
from dotenv import load_dotenv
from pydantic import ValidationError
import re

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
    sheet_range: Optional[str]
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
    if state.get("sheet_id") and state.get("sheet_range"):
        rows = read_sheet(state["sheet_id"],state["sheet_range"])
    else:
        rows = extract_from_document(state["doc_bytes"], state["file_type"])
    print(f"Loaded {len(rows)} rows (including header):", rows)

    header_idx, cols = find_header(rows)
    # header and below that 
    print(f"Header row: {header_idx}, columns: {cols}")

    # return what is below the header 
    return {
        "contacts": rows[header_idx + 1:],   
        "col_map": cols,
        "idx": 0,
    }

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

def looks_like_header(row: list[str]) -> dict:
    """Return a col_map if this row looks like a header, else {}."""
    cells = [str(c).strip() for c in row]

    # a row containing real email addresses is data, not a header
    if any(EMAIL_RE.fullmatch(c) for c in cells):
        return {}

    cols = {}
    for idx, cell in enumerate(cells):
        h = cell.lower()
        if len(h) > 30:            # headers are short; instructions are long sentences
            continue
        if "mail" in h:
            cols.setdefault("email", idx)
        elif "company" in h or "organi" in h:
            cols.setdefault("company", idx)
        elif "name" in h:
            cols.setdefault("name", idx)
    return cols


def find_header(rows: list[list[str]], scan: int = 10):
    """Return (header_row_index, col_map). header_row_index is -1 if there is no header."""
    best_idx, best_cols = -1, {}
    for i, row in enumerate(rows[:scan]):
        cols = looks_like_header(row)
        if "email" in cols and len(cols) > len(best_cols):
            best_idx, best_cols = i, cols
    if best_cols:
        return best_idx, best_cols

    # no header: find the email column from the data itself
    sample = rows[:50]
    width = max((len(r) for r in sample), default=0)
    hits = [
        sum(1 for r in sample if c < len(r) and EMAIL_RE.fullmatch(str(r[c]).strip()))
        for c in range(width)
    ]
    if hits and max(hits) > 0:
        return -1, {"email": hits.index(max(hits))}

    raise ValueError("Could not find an email column in the sheet")


def get_cell(row: list[str], col) -> str | None:
    if col is None or col >= len(row):
        return None
    return str(row[col]).strip() or None

def prepare_contact(state: AgentState):
    rows, cols, i = state["contacts"], state["col_map"], state["idx"]

    while i < len(rows):
        row = rows[i]
        try:
            contact = Contact(
                name=get_cell(row, cols.get("name")) or "HR",
                company=get_cell(row, cols.get("company")) or "your company",
                email=get_cell(row, cols.get("email")),
            )
            return {"idx": i, "current_contact": contact.model_dump()}
        except ValidationError:
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
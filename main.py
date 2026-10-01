from langgraph.graph import StateGraph, START, END
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
from llm import draft_mail, Contact
from sheets_reader import SHEET_ID, RANGE
from gmail_reader import send_mail


llm = ChatGroq(
    model="openai/gpt-oss-120b",  # current and reliable
    temperature=0,
    max_tokens = 2000,
)

# --- Shared State ---
class AgentState(TypedDict):
    resume_bytes: bytes        # raw resume PDF
    resume_data: dict          # extracted resume details
    sheet_id = Optional[str]
    doc_bytes: Optional[bytes] # uploaded HR doc (optional)
    file_type: Optional[str]   # pdf/png/jpg
    contacts: List[dict]       # extracted HR contacts
    # approved: bool             # human approved sending?
    sent_count: int            # how many emails sent


def load_resume(state: AgentState):
    resume = extract_resume_data(state['resume_bytes'])
    return {"resume_data": resume}   

def extract_data(state: AgentState):
    if state['sheet_id']:
        rows = read_sheet(state['sheet_id'])
        return {"contacts":rows}
    else:
        contacts = extract_from_document(state['doc_bytes'], state['file_type'])
        return {"contacts":contacts}


def draft_mails(state: AgentState):
    sent = 0
    for row in state['contacts'][1:]:
        try:

            contact = Contact(
                name =    row[0] if len(row) > 0 else "HR",
                email =   row[2] if len(row) > 2 else None,   # use index not key (we are not using key cuz read_sheet return list not dict)
                company = row[1] if len(row) > 1 else "Company"
            )
            # contact is a dict now 
        except Exception:
            print(f"⚠️ Skipping {row[0]} — invalid email: {row[2]}")
            continue 
        if not contact.email:
            print(f"⚠️ Skipping {contact['name']} — no email found")
            continue

        for i in range(1,5):        # max 5 retries
            email = draft_mail(contact, state['resume_data'])

            print(f"\n📧 Draft for {contact.name} at {contact.company}:")
            print("-" * 40)
            print(email)
            print("-" * 40)

            #Human in the loop
            decision = input("Choose what do you want with this mail ?")
            # decision = interrupt({
            #     "message" : "What do you think of this draft",
            #     "email_body" : email,
            #     "contact" : contact,
            #     "options": ["approve", "rewrite", "skip"]
            # })

            if decision == "approve":
                print(f"✅ Approved for {contact.name}")
                # mail 
                send_mail(
                    to=contact.email,              # ✅ fixed — was state['contacts']['email']
                    subject="Applying for AI Intern Role",
                    body=email,                       # ✅ reuse drafted email, don't redraft
                    attachment_bytes=state['resume_bytes'],
                    filename="resume.pdf",
                )
                sent += 1
                break   # move to next contact
            
            elif decision == "rewrite":
                print(f"🔄 Rewriting for {contact.name}...")
                continue                 # loop again → LLM rewrites
            
            elif decision == "skip":
                print(f"⏭️  Skipping {contact.name}")
                break
    return {"sent_count" : sent}



graph = StateGraph(AgentState)
graph.add_node("load_resume", load_resume)
graph.add_node("extract_data", extract_data)
graph.add_node("draft", draft_mails)
# graph.add_node("human_review", human_review)

graph.add_edge(START,"load_resume")
graph.add_edge("load_resume","extract_data")
graph.add_edge("extract_data", "draft")
graph.add_edge("draft", END)

memory = MemorySaver()
cold_reach = graph.compile(checkpointer = memory)



#invoke the graph 
if __name__ == "__main__":

    with open("resume.pdf", "rb") as f:
        resume_bytes = f.read()

    initial_state = {
        "resume_bytes": resume_bytes,
        "resume_data": {},
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

    result = cold_reach.invoke(
        initial_state,
        config=config
    )

    print(result)
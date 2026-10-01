import fitz
import json
import re
import os
import time
from langchain_groq import ChatGroq
from dotenv import load_dotenv

load_dotenv()

llm = ChatGroq(
    model="openai/gpt-oss-120b",  # current and reliable
    temperature=0,
    max_tokens = 2000,
)

def read_bytes(file_bytes: bytes, file_type: str) -> str:
    """Extract raw text from PDF or image bytes"""
    if file_type == "pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text
    else:
        raise ValueError(f"Unsupported file type: {file_type}")


# --- Function 1: Extract HR contacts from document ---
def extract_from_document(file_bytes: bytes, file_type: str):
    """
    Reads HR list document
    Returns list of HR contacts
    """
    text = read_bytes(file_bytes, file_type)

    for attempt in range(5):
        try:
            response = llm.invoke(f"""
Extract all persons with their details from this document.
Return ONLY a JSON array like:
[{{"name": "John Doe", "email": "john@company.com", "company": "Acme"}}]
If no email found for a person, skip them.

Document text:
{text}
""")
            result = re.sub(r"```json|```", "", response.content.strip()).strip()
            return json.loads(result)

        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1} failed: {e}")
            if attempt == 4:
                raise
            wait = 10 * (attempt + 1)
            print(f"⏳ Waiting {wait} seconds...")
            time.sleep(wait)


# --- Function 2: Extract YOUR data from resume ---
def extract_resume_data(resume_bytes: bytes):
    """
    Reads YOUR resume
    Returns your personal details
    """
    text = read_bytes(resume_bytes, "pdf")

    for attempt in range(5):
        try:
            response = llm.invoke(f"""
Extract the following details from this resume and return as JSON:
{{
    "name": "full name",
    "role": "current or desired job role",
    "skills": ["skill1", "skill2"],
    "experience": "X years",
    "education": "degree and university",
    "achievements": ["achievement1", "achievement2"]
}}
Return ONLY the JSON, nothing else.

Resume text:
{text}
""")
            result = re.sub(r"```json|```", "", response.content.strip()).strip()
            return json.loads(result)

        except Exception as e:
            print(f"⚠️ Attempt {attempt + 1} failed: {e}")
            if attempt == 4:
                raise
            wait = 10 * (attempt + 1)
            print(f"⏳ Waiting {wait} seconds...")
            time.sleep(wait)
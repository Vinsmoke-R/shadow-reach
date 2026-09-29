from google import genai
from google.genai import errors
import base64
import json
import re
import os
import time

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

MODEL = "gemini-3.8-flash"


# --- Function 1: Extract HR contacts from document ---

def extract_from_document(file_bytes: bytes, file_type: str):
    """
    Reads HR list document
    Returns list of HR contacts
    """

    mime_types = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg"
    }

    contents = [
        {
            "inline_data": {
                "mime_type": mime_types[file_type],
                "data": base64.standard_b64encode(file_bytes).decode()
            }
        },
        """
        Extract all persons with their details from this document.

        Return ONLY a JSON array like:

        [
            {
                "name": "John Doe",
                "email": "john@company.com",
                "company": "Acme"
            }
        ]

        If no email is found for a person, skip them.
        """
    ]

    # Retry when Gemini says 503 "high demand"
    for attempt in range(5):
        try:
            response = client.models.generate_content(model=MODEL, contents=contents)
            break
        except errors.ServerError:
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))

    text = response.text.strip()

    # Remove markdown code fences if Gemini adds them
    text = re.sub(r"```json|```", "", text).strip()

    return json.loads(text)


# --- Function 2: Extract YOUR data from resume ---

def extract_resume_data(resume_bytes: bytes):
    """
    Reads YOUR resume
    Returns your personal details
    """

    contents = [
        {
            "inline_data": {
                "mime_type": "application/pdf",
                "data": base64.standard_b64encode(resume_bytes).decode()
            }
        },
        """
        Extract the following details from this resume and return as JSON:

        {
            "name": "full name",
            "role": "current or desired job role",
            "skills": ["skill1", "skill2"],
            "experience": "X years",
            "education": "degree and university",
            "achievements": ["achievement1", "achievement2"]
        }

        Return ONLY the JSON, nothing else.
        """
    ]

    # Retry when Gemini says 503 "high demand"
    for attempt in range(5):
        try:
            response = client.models.generate_content(model=MODEL, contents=contents)
            break
        except errors.ServerError:
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))

    text = response.text.strip()

    # Remove markdown code fences
    text = re.sub(r"```json|```", "", text).strip()

    return json.loads(text)
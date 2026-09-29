import google.generativeai as genai
import base64
import json
import re
import os

genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

model = genai.GenerativeModel('gemini-1.5-flash')

# --- Function 1: Extract HR contacts from document ---
def extract_from_document(file_bytes: bytes, file_type: str):
    """
    Reads HR list document
    Returns list of HR contacts
    """
    mime_types = {
        'pdf':  'application/pdf',
        'png':  'image/png',
        'jpg':  'image/jpeg',
        'jpeg': 'image/jpeg'
    }

    response = model.generate_content([
        {
            "mime_type": mime_types[file_type],
            "data": base64.standard_b64encode(file_bytes).decode()
        },
        """Extract all persons with their details from this document.
Return ONLY a JSON array like:
[{"name": "John Doe", "email": "john@company.com", "company": "Acme"}]
If no email found for a person, skip them."""
    ])

    text = re.sub(r'```json|```', '', response.text).strip()
    return json.loads(text)


# --- Function 2: Extract YOUR data from resume ---
def extract_resume_data(resume_bytes: bytes):
    """
    Reads YOUR resume
    Returns your personal details
    """
    response = model.generate_content([
        {
            "mime_type": "application/pdf",
            "data": base64.standard_b64encode(resume_bytes).decode()
        },
        """Extract the following details from this resume and return as JSON:
{
    "name": "full name",
    "role": "current or desired job role",
    "skills": ["skill1", "skill2"],
    "experience": "X years",
    "education": "degree and university",
    "achievements": ["achievement1", "achievement2"]
}
Return ONLY the JSON, nothing else."""
    ])

    text = re.sub(r'```json|```', '', response.text).strip()
    return json.loads(text)
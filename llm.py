from langchain_groq import ChatGroq
from dotenv import load_dotenv
from pydantic import BaseModel, EmailStr
from typing import Optional

class Contact(BaseModel):
    name: str
    email: EmailStr        # validates email format automatically
    company: Optional[str] = None  # optional field

load_dotenv()

llm = ChatGroq(
    model="openai/gpt-oss-120b",  # current and reliable
    temperature=0,
    max_tokens = 2000,
)

def draft_mail(contact: Contact, resume_data: dict):
    "Write a draft for a mail to an hr sending your resume"
    prompt = f"""
You are a professional job seeker writing a cold email to an HR manager.

Here is YOUR information extracted from your resume:
- Name: {resume_data['name']}
- Role: {resume_data['role']}
- Skills: {', '.join(resume_data['skills'])}
- Experience: {resume_data['experience']}
- Education: {resume_data['education']}
- Achievements: {', '.join(resume_data['achievements'])}

Write a short, professional and friendly email to:
- HR Name: {contact.name}
- Company: {contact.company}

Instructions:
- Start with "Hi {contact.name},"
- Keep it under 150 words
- Sound human, not robotic or templated
- Use YOUR skills and experience naturally in the email
- Mention you are attaching your resume
- Express interest in opportunities at {contact.company}
- End with a call to action (ask for a quick call or meeting)
- Sign off as {resume_data['name']}

Return ONLY the email body, no subject line, no extra text.
"""
    response = llm.invoke(prompt)
    return response.content
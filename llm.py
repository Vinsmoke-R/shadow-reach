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
    """Draft a concise cold email with a separate subject line."""

    prompt = f"""
You are a job seeker writing a concise, natural email to HR
to share your resume and explore job opportunities.

CANDIDATE INFORMATION:
- Name: {resume_data['name']}
- Role: {resume_data['role']}
- Skills: {', '.join(resume_data['skills'])}
- Experience: {resume_data['experience']}
- Education: {resume_data['education']}
- Achievements: {', '.join(resume_data['achievements'])}

RECIPIENT:
- HR Name: {contact.name}
- Company: {contact.company}

INSTRUCTIONS:
- Write a relevant, professional subject line.
- Start the email body with "Hi {contact.name},"
- Keep the body between 70 and 100 words.
- Briefly introduce the candidate and the role they seek.
- Summarize their background in one simple sentence.
- Mention at most 1-2 relevant skills, if appropriate.
- Do not explain projects or list technical tools, frameworks,
  models, architectures, or implementation details.
- Do not repeat the resume or list all qualifications.
- Express interest in suitable opportunities at
  {contact.company}, without assuming a vacancy exists.
- Mention that the resume is attached.
- End with a polite request for a brief conversation.
- Sign off with "Best regards," followed by the candidate's name.
- Sound human, confident, friendly, and professional.
- Do not invent experience, achievements, or qualifications.
- Avoid generic phrases, exaggerated claims, and repetition.

OUTPUT FORMAT:
Subject: [Short, relevant subject line]

Body:
[Email greeting, message, and sign-off]

Return only the subject and email in this exact format.
"""

    response = llm.invoke(prompt)
    return response.content.strip()
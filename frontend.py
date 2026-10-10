import requests
import streamlit as st

API_URL = "http://localhost:8000"
TIMEOUT = 180  # LLM drafting can be slow

st.set_page_config(page_title="Shadow Reach", page_icon="📧", layout="centered")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
DEFAULTS = {
    "sheet_saved": False,
    "phase": "idle",          # idle | review | done
    "thread_id": None,
    "contact": {},
    "subject": "",
    "draft": "",
    "draft_version": 0,       # bumps on every new draft so widgets reset
    "progress": None,         # {"current": 2, "total": 10}
    "sent_count": 0,
    "error": None,
}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def call_api(method: str, path: str, **kwargs):
    """Call the backend. Returns parsed JSON, or None and stores an error."""
    try:
        r = requests.request(method, f"{API_URL}{path}", timeout=TIMEOUT, **kwargs)
        if not r.ok:
            st.session_state.error = f"{path} returned {r.status_code}: {r.text[:300]}"
            return None
        return r.json()
    except requests.exceptions.RequestException as e:
        st.session_state.error = f"Could not reach the backend at {path}: {e}"
    except ValueError:
        st.session_state.error = f"{path} did not return valid JSON."
    return None


def apply_response(data: dict):
    """Single place where a backend reply updates the UI state."""
    st.session_state.thread_id = data.get("thread_id", st.session_state.thread_id)

    if data.get("status") == "done":
        st.session_state.phase = "done"
        st.session_state.sent_count = data.get("sent_count", st.session_state.sent_count)
        return

    if not data.get("draft"):
        # Don't silently "finish": surface it so the real cause is visible.
        st.session_state.error = (
            "The backend replied without a draft and without status 'done'. "
            f"Reply was: {data}"
        )
        return

    st.session_state.phase = "review"
    st.session_state.contact = data.get("contact") or {}
    st.session_state.subject = data.get("subject", "")
    st.session_state.draft = data["draft"]
    st.session_state.progress = data.get("progress")
    st.session_state.draft_version += 1


def reset_all():
    for key, value in DEFAULTS.items():
        st.session_state[key] = value


def step_title(text: str):
    st.markdown(
        f"<div style='text-align:center;font-size:1.05rem;font-weight:600;"
        f"margin-bottom:.75rem'>{text}</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📧 Shadow Reach")
st.caption("AI cold email agent")

# ---------------------------------------------------------------------------
# Step 1 : Google sheet
# ---------------------------------------------------------------------------
with st.container(border=True):
    step_title("Step 1 : Google sheet")
    sheet_id = st.text_input(
        "Google Sheet ID",
        key="sheet_id_input",
        label_visibility="collapsed",
        placeholder="Paste your Google Sheet ID",
    )
    if st.button("Save sheet", disabled=not sheet_id.strip(), use_container_width=True):
        with st.spinner("Saving..."):
            data = call_api("POST", "/sheets", json={"sheet_id": sheet_id.strip()})
        if data is not None:
            st.session_state.sheet_saved = True
    if st.session_state.sheet_saved:
        st.success("Sheet saved")

# ---------------------------------------------------------------------------
# Step 2 : Upload resume
# ---------------------------------------------------------------------------
with st.container(border=True):
    step_title("Step 2 : Upload Resume")
    resume_file = st.file_uploader(
        "Resume (PDF)", type=["pdf"], label_visibility="collapsed"
    )
    running = st.session_state.phase == "review"
    if st.button(
        "Start agent",
        disabled=resume_file is None or running,
        use_container_width=True,
    ):
        with st.spinner("Reading your resume and drafting the first email..."):
            data = call_api(
                "POST",
                "/start",
                files={"resume": (resume_file.name, resume_file.getvalue(), "application/pdf")},
            )
        if data is not None:
            st.session_state.sent_count = 0
            apply_response(data)
        st.rerun()

# ---------------------------------------------------------------------------
# Step 3 : Review (loops once per contact)
# ---------------------------------------------------------------------------
with st.container(border=True):
    step_title("Step 3 : Review")

    # Errors persist across the rerun, then clear once shown.
    if st.session_state.error:
        st.error(st.session_state.error)
        st.session_state.error = None

    phase = st.session_state.phase

    if phase == "idle":
        st.info("Save your sheet and upload your resume. Drafts will show up here.")

    elif phase == "done":
        st.success(f"All contacts processed. {st.session_state.sent_count} email(s) sent.")
        if st.button("Start over", use_container_width=True):
            reset_all()
            st.rerun()

    elif phase == "review":
        v = st.session_state.draft_version
        contact = st.session_state.contact
        progress = st.session_state.progress

        if progress and progress.get("total"):
            st.progress(
                progress["current"] / progress["total"],
                text=f"Contact {progress['current']} of {progress['total']}",
            )

        to_line = contact.get("name", "Unknown")
        if contact.get("company"):
            to_line += f" at {contact['company']}"
        if contact.get("email"):
            to_line += f" ({contact['email']})"
        st.markdown(f"**To :** {to_line}")

        # Keys include the draft version, so each new draft gets fresh widgets
        # instead of reusing the previous draft's edited text.
        subject = st.text_input("Subject :", st.session_state.subject, key=f"subject_{v}")
        body = st.text_area("Summary :", st.session_state.draft, height=280, key=f"body_{v}")

        c1, c2, c3 = st.columns(3)
        choice = None
        if c1.button("Approve", type="primary", use_container_width=True, key=f"approve_{v}"):
            choice = "approve"
        if c2.button("Rewrite", use_container_width=True, key=f"rewrite_{v}"):
            choice = "rewrite"
        if c3.button("Skip", use_container_width=True, key=f"skip_{v}"):
            choice = "skip"

        if choice:
            labels = {
                "approve": "Sending and loading the next draft...",
                "rewrite": "Rewriting...",
                "skip": "Loading the next draft...",
            }
            payload = {
                "choice": choice,
                "subject": subject,
                "body": body,
                "thread_id": st.session_state.thread_id,
            }
            with st.spinner(labels[choice]):
                data = call_api("POST", "/decision", json=payload)
            if data is not None:
                apply_response(data)
            st.rerun()
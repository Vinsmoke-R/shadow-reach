import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="Shadow Reach", page_icon="📧")
st.title("📧 Shadow Reach")
st.subheader("AI Cold Email Agent")

# --- Session state ---
if "draft" not in st.session_state:
    st.session_state.draft = None
if "contact" not in st.session_state:
    st.session_state.contact = None
if "started" not in st.session_state:
    st.session_state.started = False

# --- Step 1: Sheet ID ---
st.markdown("### Step 1 — Google Sheet")
sheet_id = st.text_input("Enter your Google Sheet ID")

if st.button("Save Sheet ID"):
    response = requests.post(
        f"{API_URL}/sheets",
        json={"sheet_id": sheet_id}
    )
    if response.status_code == 200:
        st.success("✅ Sheet ID saved!")
    else:
        st.error("❌ Failed to save Sheet ID")

st.divider()

# --- Step 2: Upload Resume ---
st.markdown("### Step 2 — Upload Resume")
resume_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])

if resume_file and st.button("Start Agent"):
    response = requests.post(
        f"{API_URL}/start",
        files={"resume": (resume_file.name, resume_file.read(), "application/pdf")}
    )
    if response.status_code == 200:
        data = response.json()
        st.session_state.started = True
        st.session_state.draft = data.get("draft")
        st.session_state.contact = data.get("contact")
        st.success("✅ Agent started!")
    else:
        st.error("❌ Failed to start agent")

st.divider()

# --- Step 3: Review Drafts ---
if st.session_state.started and st.session_state.draft:
    st.markdown("### Step 3 — Review Draft")

    contact = st.session_state.contact
    if contact:
        st.markdown(f"**To:** {contact.get('name')} at {contact.get('company')}")
        st.markdown(f"**Email:** {contact.get('email')}")

    st.text_area("📧 Draft Email", st.session_state.draft, height=300)

    # --- Decision Buttons ---
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Approve", use_container_width=True):
            response = requests.post(
                f"{API_URL}/decision",
                json={"choice": "approve"}
            )
            data = response.json()
            if data.get("status") == "done":
                st.success(f"🎉 All done! Sent to {data.get('sent_count')} contacts.")
                st.session_state.draft = None
                st.session_state.started = False
            else:
                st.session_state.draft = data.get("draft")
                st.session_state.contact = data.get("contact")
                st.rerun()

    with col2:
        if st.button("🔄 Rewrite", use_container_width=True):
            response = requests.post(
                f"{API_URL}/decision",
                json={"choice": "rewrite"}
            )
            data = response.json()
            st.session_state.draft = data.get("draft")
            st.session_state.contact = data.get("contact")
            st.rerun()

    with col3:
        if st.button("⏭️ Skip", use_container_width=True):
            response = requests.post(
                f"{API_URL}/decision",
                json={"choice": "skip"}
            )
            data = response.json()
            if data.get("status") == "done":
                st.success(f"🎉 All done! Sent to {data.get('sent_count')} contacts.")
                st.session_state.draft = None
                st.session_state.started = False
            else:
                st.session_state.draft = data.get("draft")
                st.session_state.contact = data.get("contact")
                st.rerun()

elif st.session_state.started and not st.session_state.draft:
    st.success("🎉 All emails processed!")

else:
    st.info("👆 Fill in Sheet ID and upload your resume to get started!")
import streamlit as st
import requests
import uuid
import os

# --- CONFIGURATION ---
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Deep Researcher", layout="wide", page_icon="🧐")

# --- SESSION STATE INITIALIZATION ---
if "token" not in st.session_state:
    st.session_state.token = None
if "chat_id" not in st.session_state:
    st.session_state.chat_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "research_active" not in st.session_state:
    st.session_state.research_active = False


# --- AUTH HELPERS ---
def get_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"}


def login(email, password):
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/jwt/login",
            data={"username": email, "password": password}
        )
        if response.status_code == 200:
            st.session_state.token = response.json()["access_token"]
            st.session_state.login_email = email
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid email or password.")
    except Exception as e:
        st.error(f"Backend connection failed: {e}")


def register(email, password):
    try:
        payload = {"email": email, "password": password}
        response = requests.post(f"{API_BASE_URL}/auth/register", json=payload)
        if response.status_code == 201:
            st.success("Account created! Please switch to 'Sign In'.")
        else:
            st.error(f"Registration failed: {response.text}")
    except Exception as e:
        st.error(f"Connection error: {e}")


def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# --- API HELPERS ---
def fetch_chat_history(thread_id):
    try:
        resp = requests.get(f"{API_BASE_URL}/chat/{thread_id}", headers=get_headers())
        if resp.status_code == 200:
            return resp.json()
    except:
        return None
    return None


# --- POLLING FRAGMENT (Only for heavy research) ---
# --- REFINED POLLING FRAGMENT ---
@st.fragment(run_every="3s")
def poll_research_status(chat_id):
    if st.session_state.research_active:
        poll_data = fetch_chat_history(chat_id)
        if poll_data:
            current_status = poll_data.get("status")
            st.write(f"⏳ **Agent Activity:** {current_status}...")

            # Logic 1: If a new message appeared, update and keep polling if not done
            msgs = poll_data.get("messages", [])
            if len(msgs) > len(st.session_state.messages):
                st.session_state.messages = msgs
                # If we aren't 'COMPLETED' yet, we just update the list but stay in fragment
                if current_status != "COMPLETED":
                    st.rerun()

            # Logic 2: If the background worker marked the task as COMPLETED
            if current_status == "COMPLETED":
                st.session_state.messages = msgs
                st.session_state.research_active = False
                st.success("Research Complete!")
                st.rerun() # Final full rerun to show the report and re-enable input
            # --- UI: AUTHENTICATION ---


if not st.session_state.token:
    st.title("🧐 Deep Researcher")
    tab_login, tab_signup = st.tabs(["Sign In", "Create Account"])
    with tab_signup:
        reg_email = st.text_input("New Email", key="reg_email")
        reg_pwd = st.text_input("New Password", type="password", key="reg_pwd")
        if st.button("Register", use_container_width=True):
            register(reg_email, reg_pwd)
    with tab_login:
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pwd")
        if st.button("Sign In", use_container_width=True):
            login(email, password)
    st.stop()

# --- SIDEBAR ---
with st.sidebar:
    st.title("Settings")
    st.write(f"Logged in: `{st.session_state.get('login_email')}`")
    if st.button("🚪 Logout", use_container_width=True):
        logout()
    st.divider()
    if st.button("➕ New Chat", use_container_width=True):
        st.session_state.chat_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.session_state.research_active = False
        st.rerun()

# --- MAIN CHAT UI ---
st.title("🧐 Deep Research Agent")

# 1. Display History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 2. Polling Placeholder (Displays ONLY while research_active is True)
if st.session_state.research_active:
    with st.chat_message("assistant"):
        poll_research_status(st.session_state.chat_id)

# 3. Chat Input
if prompt := st.chat_input("What would you like to research?"):
    if not st.session_state.research_active:
        # Show User Message immediately
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Immediate Assistant Response (Synchronous for Clarifications)
        with st.chat_message("assistant"):
            with st.spinner("Analyzing request..."):
                try:
                    response = requests.post(
                        f"{API_BASE_URL}/chat/{st.session_state.chat_id}/messages",
                        json={"text": prompt},
                        headers=get_headers()
                    )

                    if response.status_code == 200:
                        data = response.json()
                        # If the backend sent a message (Clarification or Start message)
                        if data.get("messages"):
                            ai_msg = data["messages"][-1]["content"]
                            st.markdown(ai_msg)
                            st.session_state.messages.append({"role": "assistant", "content": ai_msg})

                            # Decide if we need to switch to background polling
                            # We trigger research if the AI says it's starting or searching
                            research_keywords = ["starting research", "deep dive", "searching", "analyzing"]
                            if any(word in ai_msg.lower() for word in research_keywords):
                                st.session_state.research_active = True
                                st.rerun()
                        else:
                            # Fallback if messages list is empty but 200 OK
                            st.session_state.research_active = True
                            st.rerun()
                    else:
                        st.error("Backend error. Please try again.")
                except Exception as e:
                    st.error(f"Failed to reach agent: {e}")
import streamlit as st
import requests
import uuid
import os
from datetime import datetime

# --- CONFIGURATION ---
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Deep Researcher",
    layout="wide",
    page_icon="🧐",
    initial_sidebar_state="expanded"
)

# --- SESSION STATE INITIALIZATION ---
if "token" not in st.session_state:
    st.session_state.token = None
if "chat_id" not in st.session_state:
    st.session_state.chat_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []
if "research_active" not in st.session_state:
    st.session_state.research_active = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_view" not in st.session_state:
    st.session_state.current_view = "auth"  # auth, chat, or signup
if "user_email" not in st.session_state:
    st.session_state.user_email = None


# --- AUTH HELPERS ---
def get_headers():
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def login(email, password):
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/jwt/login",
            data={"username": email, "password": password}
        )
        if response.status_code == 200:
            st.session_state.token = response.json()["access_token"]
            st.session_state.user_email = email
            st.session_state.current_view = "chat"
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
            st.success("Account created successfully! Please sign in.")
            st.session_state.current_view = "auth"
            st.rerun()
        else:
            error_msg = response.json().get("detail", "Registration failed")
            st.error(f"Registration failed: {error_msg}")
    except Exception as e:
        st.error(f"Connection error: {e}")


def logout():
    for key in ["token", "chat_id", "messages", "research_active",
                "chat_history", "user_email"]:
        if key in st.session_state:
            del st.session_state[key]
    st.session_state.current_view = "auth"
    st.rerun()


# --- API HELPERS ---
def fetch_chat_history():
    """Fetch list of all chats for the user"""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/history/",
            headers=get_headers(),
            params={"limit": 50}
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        st.error(f"Failed to load chat history: {e}")
    return []


def fetch_chat_details(thread_id):
    """Fetch messages for a specific chat"""
    try:
        resp = requests.get(
            f"{API_BASE_URL}/chat/{thread_id}",
            headers=get_headers()
        )
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None


def delete_chat(chat_id):
    """Delete a chat"""
    try:
        resp = requests.delete(
            f"{API_BASE_URL}/chat/{chat_id}",
            headers=get_headers()
        )
        return resp.status_code == 200
    except:
        return False


# --- POLLING FRAGMENT ---
@st.fragment(run_every="3s")
def poll_research_status(chat_id):
    if st.session_state.research_active:
        poll_data = fetch_chat_details(chat_id)
        if poll_data:
            # Check for completion
            if not st.session_state.research_active:  # If already marked as inactive
                return
            msgs = poll_data.get("messages", [])
            if len(msgs) > len(st.session_state.messages):
                st.session_state.messages = msgs
                st.rerun()


# --- AUTHENTICATION VIEWS ---
def show_auth_view():
    """Show login view"""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=150)
        st.title("🧐 Deep Researcher")
        st.markdown("### Welcome Back")
        st.markdown("Please sign in to continue your research")

        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_pwd")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Sign In", use_container_width=True):
                if email and password:
                    login(email, password)
                else:
                    st.error("Please fill in all fields")

        with col_b:
            if st.button("Create Account", use_container_width=True):
                st.session_state.current_view = "signup"
                st.rerun()


def show_signup_view():
    """Show registration view"""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("Create Account")
        st.markdown("Create a new account to start researching")

        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Password", type="password", key="reg_pwd")
        confirm_password = st.text_input("Confirm Password", type="password", key="confirm_pwd")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Register", use_container_width=True):
                if not email or not password:
                    st.error("Please fill in all fields")
                elif password != confirm_password:
                    st.error("Passwords do not match")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters")
                else:
                    register(email, password)

        with col_b:
            if st.button("Back to Login", use_container_width=True):
                st.session_state.current_view = "auth"
                st.rerun()


# --- SIDEBAR COMPONENTS ---
def show_sidebar():
    """Display sidebar with user info and chat history"""
    with st.sidebar:
        # User info at top
        st.markdown(f"""
        <div style="
            padding: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
            color: white;
            margin-bottom: 1rem;
        ">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="font-size: 2rem;">👤</div>
                <div>
                    <h4 style="margin: 0;">{st.session_state.user_email}</h4>
                    <small>Research Assistant</small>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # New Chat button
        if st.button("🆕 New Chat", use_container_width=True):
            st.session_state.chat_id = str(uuid.uuid4())
            st.session_state.messages = []
            st.session_state.research_active = False
            st.rerun()

        st.divider()

        # Chat History
        st.markdown("### 📚 Recent Chats")

        # Fetch chat history
        if st.session_state.token:
            with st.spinner("Loading chats..."):
                chat_history = fetch_chat_history()
                st.session_state.chat_history = chat_history

        if st.session_state.chat_history:
            for chat in st.session_state.chat_history:
                chat_id = chat.get("chat_id")
                title = chat.get("title", "Untitled Chat")
                last_updated = chat.get("last_updated", "")

                # Format date if available
                if last_updated:
                    try:
                        date_obj = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                        date_str = date_obj.strftime("%b %d, %H:%M")
                    except:
                        date_str = last_updated[:10]
                else:
                    date_str = ""

                # Create a button for each chat
                col1, col2 = st.columns([4, 1])
                with col1:
                    if st.button(
                            f"💬 {title[:30]}{'...' if len(title) > 30 else ''}",
                            key=f"chat_{chat_id}",
                            use_container_width=True,
                            type="secondary"
                    ):
                        st.session_state.chat_id = chat_id
                        st.session_state.messages = []
                        st.session_state.research_active = False
                        # Load chat details
                        chat_data = fetch_chat_details(chat_id)
                        if chat_data and "messages" in chat_data:
                            st.session_state.messages = chat_data["messages"]
                        st.rerun()

                with col2:
                    if st.button("🗑️", key=f"delete_{chat_id}", help="Delete chat"):
                        if delete_chat(chat_id):
                            st.success("Chat deleted")
                            st.session_state.chat_history = fetch_chat_history()
                            st.rerun()
                        else:
                            st.error("Failed to delete chat")

                # Show date under title
                if date_str:
                    st.caption(f"📅 {date_str}")

                st.divider()
        else:
            st.info("No chat history yet. Start a new conversation!")

        # Logout button at bottom
        st.divider()
        if st.button("🚪 Logout", use_container_width=True, type="primary"):
            logout()


# --- MAIN CHAT VIEW ---
def show_chat_view():
    """Display main chat interface"""
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Polling placeholder for active research
    if st.session_state.research_active:
        with st.chat_message("assistant"):
            with st.status("🔍 Research in progress...", expanded=True) as status:
                st.write("The agent is currently researching your query...")
                poll_research_status(st.session_state.chat_id)

    # Chat input
    if prompt := st.chat_input("What would you like to research?"):
        if not st.session_state.research_active:
            # Show user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Get AI response
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
                            if data.get("messages"):
                                ai_msg = data["messages"][-1]["content"]
                                st.markdown(ai_msg)
                                st.session_state.messages.append({"role": "assistant", "content": ai_msg})

                                # Check if research is starting
                                research_triggers = ["starting research", "deep dive", "searching",
                                                     "analyzing", "I'll research", "beginning research"]
                                if any(trigger in ai_msg.lower() for trigger in research_triggers):
                                    st.session_state.research_active = True
                                    st.rerun()
                            else:
                                st.session_state.research_active = True
                                st.rerun()
                        else:
                            st.error("Failed to send message. Please try again.")
                    except Exception as e:
                        st.error(f"Connection error: {e}")


# --- MAIN APP FLOW ---
def main():
    # Custom CSS for better styling
    st.markdown("""
    <style>
    .stButton button {
        transition: all 0.3s ease;
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .chat-history-button {
        text-align: left;
        justify-content: flex-start;
    }
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f8f9fa 0%, #ffffff 100%);
    }
    </style>
    """, unsafe_allow_html=True)

    # Route to appropriate view
    if st.session_state.current_view == "auth":
        show_auth_view()
    elif st.session_state.current_view == "signup":
        show_signup_view()
    elif st.session_state.current_view == "chat":
        # Two-column layout: sidebar + main chat
        col1, col2 = st.columns([1, 3])

        with col1:
            show_sidebar()

        with col2:
            # Chat header
            st.markdown(f"""
            <div style="
                padding: 1rem;
                background: white;
                border-radius: 10px;
                margin-bottom: 1rem;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            ">
                <h2 style="margin: 0; color: #333;">🧐 Deep Research Assistant</h2>
                <small style="color: #666;">Chat ID: {st.session_state.chat_id[:8]}...</small>
            </div>
            """, unsafe_allow_html=True)

            show_chat_view()


if __name__ == "__main__":
    main()
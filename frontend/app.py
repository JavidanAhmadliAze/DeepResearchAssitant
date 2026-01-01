import streamlit as st
import requests
import uuid
import os
import time
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
    st.session_state.current_view = "auth"
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "last_poll_time" not in st.session_state:  # 🆕 Track polling
    st.session_state.last_poll_time = 0
if "poll_count" not in st.session_state:  # 🆕 Track poll count
    st.session_state.poll_count = 0


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
                "chat_history", "user_email", "last_poll_time", "poll_count"]:
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


# --- SMART POLLING LOGIC ---
def check_research_status_once():
    if not st.session_state.research_active:
        return False

    current_time = time.time()
    if current_time - st.session_state.last_poll_time < 3:
        return False

    st.session_state.last_poll_time = current_time
    st.session_state.poll_count += 1

    chat_id = st.session_state.chat_id
    poll_data = fetch_chat_details(chat_id)

    if poll_data:
        # 1. Extract data from the new backend structure
        msgs = poll_data.get("messages", [])
        status = poll_data.get("status")

        # 2. Update messages if they exist
        # We use a length check OR a content hash check
        if len(msgs) > 0:
            # Only update and rerun if the count actually changed
            if len(msgs) != len(st.session_state.messages):
                st.session_state.messages = msgs
                return True

                # 3. Check for Completion
        # If the backend says it's done, or we have a report, stop polling
        if status == "COMPLETED" or any(m.get("is_report") for m in msgs):
            st.session_state.research_active = False
            st.sidebar.success("✅ Research Complete!")
            return True

        # 4. Handle Timeouts
        if st.session_state.poll_count > 100:  # Increased for deep research
            st.session_state.research_active = False
            st.sidebar.error("⏱️ Research timed out")
            return True

    return False


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
            st.session_state.poll_count = 0  # 🆕 Reset poll count
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
                status = chat.get("status", "COMPLETED")  # Get status if available

                # Format date if available
                if last_updated:
                    try:
                        date_obj = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
                        date_str = date_obj.strftime("%b %d, %H:%M")
                    except:
                        date_str = last_updated[:10]
                else:
                    date_str = ""

                # Create columns for button and status icon
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    # Unique key for each load button
                    if st.button(
                            f"💬 {title[:25]}{'...' if len(title) > 25 else ''}",
                            key=f"load_{chat_id}",  # Changed key format
                            use_container_width=True,
                            type="secondary"
                    ):
                        # 🟢 FIXED: Load chat properly using a helper function
                        load_existing_chat(chat_id, title, status)

                with col2:
                    # Show status icon
                    if status == "RESEARCHING":
                        st.markdown("🔍")
                    elif status == "SUMMARIZING":
                        st.markdown("📝")
                    elif status == "COMPLETED":
                        st.markdown("✅")
                    elif status == "FAILED":
                        st.markdown("❌")
                    elif status == "CLARIFYING":
                        st.markdown("❓")

                with col3:
                    if st.button("🗑️", key=f"delete_{chat_id}", help="Delete chat"):
                        if delete_chat(chat_id):
                            st.success("Chat deleted")
                            # Refresh chat list
                            st.session_state.chat_history = fetch_chat_history()
                            st.rerun()
                        else:
                            st.error("Failed to delete chat")

                # Show date under title
                if date_str:
                    st.caption(f"📅 {date_str} | {status.lower()}")

                st.divider()
        else:
            st.info("No chat history yet. Start a new conversation!")

        # Debug info (toggleable)
        with st.expander("🔧 Debug Info"):
            st.write(f"Research active: {st.session_state.research_active}")
            st.write(f"Poll count: {st.session_state.poll_count}")
            st.write(f"Current Chat ID: {st.session_state.chat_id[:8]}...")
            st.write(f"Messages in session: {len(st.session_state.messages)}")
            if st.button("🔄 Refresh Debug Info"):
                st.rerun()

        # Logout button at bottom
        st.divider()
        if st.button("🚪 Logout", use_container_width=True, type="primary"):
            logout()


def load_existing_chat(chat_id, title, status):
    """Load an existing chat into session state"""
    print(f"🔄 Loading chat: {chat_id} - '{title}' (status: {status})")

    # Store previous chat ID for comparison
    previous_chat_id = st.session_state.get("chat_id", "")

    # Show loading indicator immediately
    loading_placeholder = st.empty()
    with loading_placeholder.container():
        st.info(f"Loading '{title}'...")

    try:
        # Fetch chat details
        chat_data = fetch_chat_details(chat_id)

        if chat_data:
            print(f"✅ Chat data received for {chat_id}")
            print(f"📊 Data keys: {list(chat_data.keys())}")

            # Update session state
            st.session_state.chat_id = chat_id

            # Load messages
            if "messages" in chat_data and chat_data["messages"]:
                st.session_state.messages = chat_data["messages"]
                print(f"📝 Loaded {len(chat_data['messages'])} messages")
            else:
                st.session_state.messages = []
                print("ℹ️ No messages in chat data")

            # Update research status
            chat_status = chat_data.get("status", status)
            if chat_status in ["RESEARCHING", "SUMMARIZING", "SEARCHING"]:
                st.session_state.research_active = True
                print(f"🔍 Chat status is {chat_status}, setting research_active=True")
            else:
                st.session_state.research_active = False
                print(f"✅ Chat status is {chat_status}, setting research_active=False")

            # Reset polling
            st.session_state.poll_count = 0
            st.session_state.last_poll_time = 0

            # Clear loading indicator
            loading_placeholder.empty()

            # Show success message briefly
            success_msg = st.sidebar.success(f"✓ Loaded: {title}")
            time.sleep(1)  # Brief pause to show message
            success_msg.empty()

        else:
            loading_placeholder.empty()
            st.sidebar.error(f"Failed to load chat: {title}")
            print(f"❌ No data returned for {chat_id}")

    except Exception as e:
        loading_placeholder.empty()
        st.sidebar.error(f"Error loading chat: {str(e)[:100]}")
        print(f"🚨 Exception loading {chat_id}: {e}")

    # Always rerun to update UI
    st.rerun()


# Also update your fetch_chat_details for better debugging:
def fetch_chat_details(thread_id):
    """Fetch messages for a specific chat with enhanced debugging"""
    try:
        print(f"🌐 API Call: GET /chat/{thread_id}")
        resp = requests.get(
            f"{API_BASE_URL}/chat/{thread_id}",
            headers=get_headers(),
            timeout=60  # Increased timeout
        )

        print(f"📡 Response Code: {resp.status_code}")

        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Success! Chat ID: {data.get('chat_id')}")
            print(f"📊 Status: {data.get('status', 'unknown')}")
            print(f"📝 Messages count: {len(data.get('messages', []))}")

            # Log first few messages for debugging
            messages = data.get('messages', [])
            if messages:
                print("📄 Sample messages:")
                for i, msg in enumerate(messages[:3]):  # First 3 messages
                    print(f"  {i + 1}. [{msg.get('role', '?')}] {msg.get('content', '')[:50]}...")

            return data
        elif resp.status_code == 404:
            print(f"❌ Chat not found: {thread_id}")
        elif resp.status_code == 403:
            print(f"🚫 Access denied to chat: {thread_id}")
        else:
            print(f"⚠️ Unexpected status {resp.status_code}: {resp.text[:100]}")

    except requests.exceptions.Timeout:
        print(f"⏱️ Timeout fetching chat {thread_id}")
    except requests.exceptions.ConnectionError:
        print(f"🔌 Connection error fetching chat {thread_id}")
    except Exception as e:
        print(f"🚨 Exception fetching {thread_id}: {e}")

    return None
# --- MAIN CHAT VIEW ---
def show_chat_view():
    """Display main chat interface with proper research locking"""
    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 🟢 CRITICAL: Check research status at VERY BEGINNING
    if st.session_state.research_active:
        render_research_in_progress()
        return  # 🛑 EXIT IMMEDIATELY - no chat input shown

    # 🟢 Only show chat input if NOT researching
    if prompt := st.chat_input("What would you like to research?"):
        handle_user_message(prompt)


def render_research_in_progress():
    """Render the research in progress UI with disabled input"""
    # Show research status
    with st.chat_message("assistant"):
        # Create a nice research status display
        st.markdown("""
        <div style='
            padding: 1rem;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
            color: white;
            margin: 0.5rem 0;
        '>
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="font-size: 1.5rem;">🔍</div>
                <div>
                    <h4 style="margin: 0 0 4px 0;">Research in Progress</h4>
                    <p style="margin: 0; opacity: 0.9; font-size: 0.9rem;">
                        Gathering comprehensive information...
                    </p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Progress indicator
        progress_container = st.empty()
        with progress_container.container():
            progress_text = st.empty()
            progress_bar = st.progress(0)

            # Animate progress (optional, can be removed)
            for i in range(1, 101):
                progress_text.text(f"Processing... {i}%")
                progress_bar.progress(i)
                time.sleep(0.02)  # Very brief delay

    # 🛑 DISABLED CHAT INPUT - Show it as disabled
    disabled_input = st.chat_input(
        "⏳ Research in progress... Please wait",
        disabled=True
    )

    # Check for updates
    # 🟢 ADD THIS: Visual feedback that we are polling
    st.caption(f"Last checked: {datetime.now().strftime('%H:%M:%S')} (Poll #{st.session_state.poll_count})")

    # Check for updates
    if check_research_status_once():
        st.rerun()
    else:
        # 🟢 THE FIX: Force Streamlit to wait 5 seconds and then rerun itself
        time.sleep(5)
        st.rerun()


def handle_user_message(prompt):
    """Handle user message and start research if needed"""
    # 🟢 Show user message immediately
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("assistant"):
        thinking_placeholder = st.empty()
        with thinking_placeholder.container():
            st.info("🤔 Analyzing your request...")

    try:
        response = requests.post(
            f"{API_BASE_URL}/chat/{st.session_state.chat_id}/messages",
            json={"text": prompt},
            headers=get_headers(),
            timeout=60
        )

        thinking_placeholder.empty()

        # 🟢 FIX: Handle both 200 and 202 properly
        if response.status_code in [200, 202]:
            try:
                data = response.json()
            except:
                data = {}

            # 🟢 CRITICAL: Show ALL messages from backend, not just last one
            backend_messages = data.get("messages", [])

            # Clear and rebuild session messages from backend
            # This ensures consistency between frontend and backend
            st.session_state.messages = []

            for msg in backend_messages:
                # Add to session state
                st.session_state.messages.append(msg)

                # Show in chat (only if not already shown)
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

            # If backend returned no messages, show default
            if not backend_messages and response.status_code == 202:
                with st.chat_message("assistant"):
                    st.info("✅ Research started! This may take a few minutes...")
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "Research started! This may take a few minutes..."
                })

            # Set research flags based on status code
            if response.status_code == 202:
                st.session_state.research_active = True
                st.session_state.poll_count = 0
                st.session_state.last_poll_time = time.time()
                st.rerun()
            else:  # 200
                st.session_state.research_active = False

        else:
            st.session_state.research_active = False
            with st.chat_message("assistant"):
                st.error(f"Failed to process request (Status: {response.status_code})")

    except requests.exceptions.Timeout:
        st.session_state.research_active = False
        with st.chat_message("assistant"):
            st.error("Request timeout. Please try again.")
    except Exception as e:
        st.session_state.research_active = False
        with st.chat_message("assistant"):
            st.error(f"Error: {str(e)[:100]}")

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
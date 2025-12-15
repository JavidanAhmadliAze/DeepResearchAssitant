import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))

import streamlit as st
import asyncio
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage
from src.agents.workflow_executor import agent
from src.utils.tools import get_today_str
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Deep Research Agent", layout="wide")
st.title("🧠 Deep Research Agent Chat")

# --- Session State Setup (must be done before any access) ---
st.session_state.setdefault("conversation_history", [])
st.session_state.setdefault("thread", {"configurable": {"thread_id": "1", "recursion_limit": 50}})
st.session_state.setdefault("final_text", "")   # initialize final_text as empty string
st.session_state.setdefault("need_research", False)
# --- Vector store: initialize once (top-level) ---
# You can move this to its own module so it's not re-created repeatedly.

embedding = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")
VECTOR_DB_PATH = r"C:\Users\User\PythonProject\data\output"

vector_store = Chroma(
    collection_name="deep_research_texts",
    embedding_function=embedding,
    persist_directory=VECTOR_DB_PATH
)

# --- Chat Display ---
st.subheader("💬 Conversation")
for msg in st.session_state["conversation_history"]:
    if isinstance(msg, HumanMessage):
        st.chat_message("user").markdown(msg.content)
    elif isinstance(msg, AIMessage):
        st.chat_message("assistant").markdown(msg.content)

# --- Chat Input ---
user_input = st.chat_input("Ask your research question...")

# --- Handle Input ---
if user_input:
    st.session_state["conversation_history"].append(HumanMessage(content=user_input))
    st.chat_message("user").markdown(user_input)

    async def run_agent():
        # send full history to your agent
        result = await agent.ainvoke(
            {"messages": st.session_state["conversation_history"]},
            config=st.session_state["thread"]
        )

        # last AI message for chat display (keeps labeling)
        ai_msg = result["messages"][-1]
        st.session_state["conversation_history"].append(ai_msg)
        st.session_state["need_research"] = result.get("trigger_search", False)
        # store final_report (if present) into session_state
        notes = result.get("notes",[])
        findings = "\n".join(notes)
        st.session_state["final_text"] = findings or ""  # ensure string



        return ai_msg

    with st.spinner("🧩 Running deep research..."):
        ai_message = asyncio.run(run_agent())

    st.chat_message("assistant").markdown(ai_message.content)

# --- Persist final report into Chroma (only when present and not already stored) ---
# optional: you might want to track if a given final_text was already stored to avoid duplicates

if st.session_state.get("final_text"):

    final_text = st.session_state["final_text"]
    if  st.session_state.get("need_research", False):
        # you may want a flag to avoid re-adding the same final_text on each rerun
        doc = Document(
            page_content=final_text,
            metadata={
                "user_query": user_input,
                "timestamp": get_today_str(),
                "type": "final_report",
            }
        )

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1800,
            chunk_overlap=200,
            add_start_index=True
        )

        all_splits = text_splitter.split_documents([doc])
        vector_store.add_documents(documents=all_splits)
        print("Doc added to Database")
    else:
        print("Data is available in Database no need to add")


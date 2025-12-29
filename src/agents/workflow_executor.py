from src.agent_interface.states import AgentInputState, AgentOutputState
from src.utils.tools import get_today_str
from langchain_core.messages import HumanMessage, AIMessage
from src.llm.gemini_client import create_model
from src.prompt_engineering.templates import get_prompt
from src.agents.supervisor_agent import supervisor, supervisor_tools
from src.agents.scope_agent import clarify_with_user, write_research_brief
from langgraph.graph import StateGraph, START, END
from langsmith import traceable
from psycopg_pool import AsyncConnectionPool
import os
from dotenv import load_dotenv
load_dotenv()
raw_url = os.getenv("ASYNC_DATABASE_URL")
DATABASE_URL = raw_url.replace("+asyncpg", "")
model = create_model("final_reporter")
final_report_generation_prompt = get_prompt("final_reporter", "final_report_generation_prompt")

@traceable
async def final_report_generation(state: AgentOutputState):
    """
    Final report generation node.
    Synthesizes all research findings into a comprehensive final report
    and keeps the conversation labeled correctly.
    """
    # Retrieve previous notes and research brief
    notes = state.get("notes", [])
    raw_notes = state.get("raw_notes", [])

    raw_findings = "\n".join(raw_notes)
    findings = "\n".join(notes)
    research_brief = state.get("research_brief", "")

    # Build the final report prompt
    final_report_prompt = final_report_generation_prompt.format(
        research_brief=research_brief,
        findings=findings,
        date=get_today_str()
    )

    # Call the model
    final_report_response = await model.ainvoke([HumanMessage(content=final_report_prompt)])

    # Wrap final report in AIMessage to keep it labeled correctly
    ai_message = AIMessage(content=final_report_response.content)

    # Append to existing messages in state for memory continuity
    previous_messages = state.get("messages", [])
    updated_messages = previous_messages + [ai_message]
    print(80*"#")
    print(findings)
    print(80*"#")
    return {
        "final_report": final_report_response.content,
        "messages": updated_messages,  # keep conversation history
    }

deep_researcher_builder = StateGraph(AgentOutputState, input_schema=AgentInputState)

# Add workflow nodes
deep_researcher_builder.add_node("clarify_with_user", clarify_with_user)
deep_researcher_builder.add_node("write_research_brief", write_research_brief)
deep_researcher_builder.add_node("supervisor", supervisor)
deep_researcher_builder.add_node("supervisor_tools", supervisor_tools)
deep_researcher_builder.add_node("final_report_generation", final_report_generation)

# Add workflow edges
deep_researcher_builder.add_edge(START, "clarify_with_user")
deep_researcher_builder.add_edge("write_research_brief", "supervisor")
deep_researcher_builder.add_edge("supervisor", "supervisor_tools")
deep_researcher_builder.add_edge("supervisor_tools", "final_report_generation")
deep_researcher_builder.add_edge("final_report_generation", END)

connection_pool = AsyncConnectionPool(conninfo=DATABASE_URL, max_size=20)



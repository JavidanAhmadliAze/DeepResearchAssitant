from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from typing_extensions import Literal
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, get_buffer_string
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from src.agent_interface.states import AgentInputState, AgentOutputState
from src.agent_interface.schemas import ClarifyWithUser, ResearchQuestion
from src.llm.gemini_client import create_openai_model
from langsmith import traceable
from src.prompt_engineering.templates import get_prompt
from src.utils.tools import get_today_str
from backend.db import ResearchBrief, AgentMetrics
from langchain_core.runnables import RunnableConfig


load_dotenv()

clarification_instructions = get_prompt("scope_agent","clarification_instructions")
transform_messages_into_research_topic_prompt = get_prompt("scope_agent","transform_messages_into_research_topic_prompt")

model = create_openai_model("scope_agent")


@traceable
async def clarify_with_user(state: AgentInputState, config: RunnableConfig) -> Command[
    Literal["write_research_brief", "__end__"]]:

    db = config["configurable"].get("db_session")
    task_id = config["configurable"].get("task_id")

    structured_output_model = model.with_structured_output(ClarifyWithUser, include_raw=True)

    result = await structured_output_model.ainvoke([
        HumanMessage(content=clarification_instructions.format(
            messages=get_buffer_string(messages=state.get("messages", [])),
            date=get_today_str(), tools_optional=True
        ))
    ])

    # Extracting from the dict returned by include_raw=True
    brief_obj = result["parsed"]
    raw_msg = result["raw"]

    if db and task_id:
        usage = raw_msg.usage_metadata
        db.add(AgentMetrics(
            task_id=task_id,
            agent_name="scoping_agent_clarifier",
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            trace_id=str(config.get("run_id", ""))
        ))
        # Note: We commit in the final node or here if we exit
        await db.commit()

    if brief_obj.need_clarification:
        return Command(
            goto=END,
            update={"messages": [AIMessage(content=brief_obj.question)]}
        )
    else:
        return Command(
            goto="write_research_brief",
            update={"messages": [AIMessage(content=brief_obj.verification)]}
        )


@traceable
async def write_research_brief(state: AgentOutputState, config: RunnableConfig):
    db = config["configurable"].get("db_session")
    task_id = config["configurable"].get("task_id")

    structured_output_model = model.with_structured_output(ResearchQuestion, include_raw=True)

    # Use ainvoke for consistency
    result = await structured_output_model.ainvoke([
        HumanMessage(content=transform_messages_into_research_topic_prompt.format(
            messages=get_buffer_string(state.get("messages", [])),
            date=get_today_str(), tools_optional=True
        ))
    ])

    brief_obj = result["parsed"]
    raw_msg = result["raw"]

    if db and task_id:
        db.add(ResearchBrief(
            task_id=task_id,
            finalized_question=brief_obj.research_brief
        ))

        usage = raw_msg.usage_metadata
        db.add(AgentMetrics(
            task_id=task_id,
            agent_name="scoping_agent_writer",  # Changed name to be distinct
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            trace_id=str(config.get("run_id", ""))
        ))
        await db.commit()

    return {
        "research_brief": brief_obj.research_brief,
        "supervisor_messages": [HumanMessage(content=f"{brief_obj.research_brief}.")]
    }


deep_researcher_builder = StateGraph(AgentOutputState, input_schema=AgentInputState)

# Add workflow nodes
deep_researcher_builder.add_node("clarify_with_user", clarify_with_user)
deep_researcher_builder.add_node("write_research_brief", write_research_brief)

# Add workflow edges
deep_researcher_builder.add_edge(START, "clarify_with_user")
deep_researcher_builder.add_edge("write_research_brief", END)

# Compile the workflow
memory = InMemorySaver()
scope = deep_researcher_builder.compile(checkpointer = memory)

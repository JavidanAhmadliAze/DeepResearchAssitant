from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from typing_extensions import Literal
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, get_buffer_string
from dotenv import load_dotenv
from src.agent_interface.states import AgentInputState, AgentOutputState
from src.agent_interface.schemas import ClarifyWithUser, ResearchQuestion
from src.llm.gemini_client import create_model
from langsmith import traceable
from src.prompt_engineering.templates import get_prompt
from src.utils.tools import get_today_str


load_dotenv()

clarification_instructions = get_prompt("scope_agent","clarification_instructions")
transform_messages_into_research_topic_prompt = get_prompt("scope_agent","transform_messages_into_research_topic_prompt")

model = create_model("scope_agent")

@traceable
async def clarify_with_user(state: AgentInputState) -> Command[Literal["write_research_brief", "__end__"]]:

    structured_output_model = model.with_structured_output(schema=ClarifyWithUser)

    result = await structured_output_model.ainvoke([
        HumanMessage(content=clarification_instructions.format(
            messages = get_buffer_string(messages=state.get("messages", [])),
            date = get_today_str(),
            ))
        ])

    if result.need_clarification:
        return Command(
                goto="__end__",
                update={"messages": [AIMessage(content=result.question)]}
            )

    else:
        return Command(
            goto="write_research_brief",
            update={"messages": [AIMessage(content=result.verification)]}
        )

async def write_research_brief(state: AgentOutputState):

    structured_output_model = model.with_structured_output(schema=ResearchQuestion)

    result = await structured_output_model.ainvoke([
        HumanMessage(content=transform_messages_into_research_topic_prompt.format(
            messages=get_buffer_string(messages=state.get("messages",[])),
            date=get_today_str()
        ))])

    return {"research_brief": result.research_brief,
            "supervisor_messages": [HumanMessage(content=f"{result.research_brief}.")]}
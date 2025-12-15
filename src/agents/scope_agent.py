from datetime import datetime
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from typing_extensions import Literal
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, get_buffer_string
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from src.agent_interface.states import AgentInputState, AgentOutputState
from src.agent_interface.schemas import ClarifyWithUser, ResearchQuestion
from src.llm.gemini_client import create_gemini_model
from langsmith import traceable
from src.prompt_engineering.templates import get_prompt
from src.utils.tools import get_today_str


load_dotenv()

clarification_instructions = get_prompt("scope_agent","clarification_instructions")
transform_messages_into_research_topic_prompt = get_prompt("scope_agent","transform_messages_into_research_topic_prompt")

model = create_gemini_model("scope_agent")

@traceable
def clarify_with_user(state: AgentInputState) -> Command[Literal["write_research_brief", "__end__"]]:
    """
    Determine if the user's request contains sufficient information to proceed with research.

    Uses structured output to make deterministic decisions and avoid hallucination.
    Routes to either research brief generation or ends with a clarification question.
    """

    structured_output_model = model.with_structured_output(ClarifyWithUser)

    response = structured_output_model.invoke([
        HumanMessage(content=clarification_instructions.format(
            messages=get_buffer_string(messages=state.get("messages", [])),
            date=get_today_str(), tools_optional=True
        ))
    ])

    if response.need_clarification:
        return Command(
            goto=END,
            update={"messages": [AIMessage(content=response.question)]}
        )
    else:
        return Command(
            goto="write_research_brief",
            update={"messages": [AIMessage(content=response.verification)]}
        )

@traceable
def write_research_brief(state: AgentOutputState):
    """
    Transform the conversation history into a comprehensive research brief.

    Uses structured output to ensure the brief follows the required format
    and contains all necessary details for effective research.
    """
    # Set up structured output model
    structured_output_model = model.with_structured_output(ResearchQuestion)

    response = structured_output_model.invoke([
        HumanMessage(content=transform_messages_into_research_topic_prompt.format(
            messages=get_buffer_string(state.get("messages", [])),
            date=get_today_str(), tools_optional=True
        ))
    ])

    return {
        "research_brief": response.research_brief,
        "supervisor_messages": [HumanMessage(content=f"{response.research_brief}.")]
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

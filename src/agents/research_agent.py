from src.utils.tools import get_today_str, think_tool, tavily_search
from langgraph.graph import StateGraph, START, END
from src.agent_interface.states import ResearcherState, ResearcherOutputState
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, filter_messages
from typing_extensions import Literal
from langgraph.checkpoint.memory import InMemorySaver
from src.llm.gemini_client import create_model
from src.prompt_engineering.templates import get_prompt
from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv
load_dotenv()

model = create_model("research_agent")
research_agent_prompt = get_prompt("research_agent","research_agent_prompt")
compress_research_system_prompt = get_prompt("research_agent","compress_research_system_prompt")
compress_research_human_message = get_prompt("research_agent","compress_research_human_message")

tools = [tavily_search, think_tool]
tools_by_name = {tool.name: tool for tool in tools}
model_with_tools = model.bind_tools(tools)
checkpoint = InMemorySaver()


def llm_call(state: ResearcherState) :
    """Analyze current state and decide on next actions.

        The model analyzes the current conversation state and decides whether to:
        1. Call search tools to gather more information
        2. Provide a final answer based on gathered information

        Returns updated state with the model's response.
        """
    return {
        "researcher_messages": [
            model_with_tools.invoke(
                [SystemMessage(content=research_agent_prompt)] + state.get("researcher_messages",[])
            )
        ]
    }

def tool_node(state: ResearcherState):
    """Execute all tool calls from the previous LLM response and show outputs."""

    tool_calls = state["researcher_messages"][-1].tool_calls
    observations = []

    for tool_call in tool_calls:
        tool_name = getattr(tool_call, "name", tool_call.get("name"))
        tool_args = getattr(tool_call, "args", tool_call.get("args"))
        print(f"\n🧰 Tool call detected: {tool_name}")
        print(f"📥 Arguments: {tool_args}")

        tool = tools_by_name[tool_name]
        observation = tool.invoke(tool_args)

        print(f"📤 ToolMessage output:\n{observation}\n{'-'*80}")
        observations.append(observation)

    # Create ToolMessage objects for the next model input
    tool_outputs = [
        ToolMessage(
            content=observation,
            name=tool_call["name"],
            tool_call_id=tool_call["id"]
        ) for observation, tool_call in zip(observations, tool_calls)
    ]

    return {"researcher_messages": tool_outputs}


def compress_research(state: ResearcherState) -> dict:
    """Compress research findings into a concise summary.

    Takes all the research messages and tool outputs and creates
    a compressed summary suitable for the supervisor's decision-making.
    """

    system_message = compress_research_system_prompt.format(date=get_today_str())

    messages = [SystemMessage(content=system_message)] + state.get("researcher_messages", []) + [HumanMessage(content=compress_research_human_message)]
    response = model.invoke(messages)

    # Extract raw notes from tool and AI messages
    raw_notes = [
        str(m.content) for m in filter_messages(
            state["researcher_messages"],
            include_types=["tool", "ai", "ToolMessage", "AIMessage"]
        )
    ]

    return {
        "compressed_research": str(response.content),
        "raw_notes": ["\n".join(raw_notes)]
    }

def should_continue(state: ResearcherState) -> Literal["tool_node", "compress_research"]:
    """Determine whether to continue research or provide final answer.

    Determines whether the agent should continue the research loop or provide
    a final answer based on whether the LLM made tool calls.

    Returns:
        "tool_node": Continue to tool execution
        "compress_research": Stop and compress research
    """
    messages = state["researcher_messages"]
    last_message = messages[-1]

    # If the LLM makes a tool call, continue to tool execution
    if last_message.tool_calls:
        return "tool_node"
    # Otherwise, we have a final answer
    return "compress_research"


agent_builder = StateGraph(ResearcherState, output_schema=ResearcherOutputState)

# Add nodes to the graph
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)
agent_builder.add_node("compress_research", compress_research)

# Add edges to connect nodes
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {
        "tool_node": "tool_node", # Continue research loop
        "compress_research": "compress_research", # Provide final answer
    },
)
agent_builder.add_edge("tool_node", "llm_call") # Loop back for more research
agent_builder.add_edge("compress_research", END)

research_agent = agent_builder.compile(checkpointer=checkpoint)
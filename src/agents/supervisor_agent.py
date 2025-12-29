from src.agent_interface.states import SupervisorState
from src.agent_interface.tools import  ConductResearch, ResearchComplete
from langchain_core.messages import SystemMessage, ToolMessage, BaseMessage, HumanMessage, filter_messages
from src.utils.tools import get_today_str, think_tool
from langgraph.types import Command
from src.agents.research_agent import research_agent
from src.data_retriever.output_retriever import retrieve_data_with_score
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
import asyncio

from typing_extensions import Literal
from src.llm.gemini_client import create_model
from src.prompt_engineering.templates import get_prompt
from dotenv import load_dotenv
load_dotenv()

model = create_model("supervisor_agent")
lead_researcher_prompt = get_prompt("supervisor_agent","lead_researcher_prompt")
tools = [ConductResearch, ResearchComplete, think_tool, retrieve_data_with_score]
model_with_tools = model.bind_tools(tools)
# This prevents infinite loops and controls research depth per topic
max_researcher_iterations = 6 # Calls to think_tool + ConductResearch

# Maximum number of concurrent research agents the supervisor can launch
# This is passed to the lead_researcher_prompt to limit parallel research tasks
max_concurrent_researchers_unit = 3

def get_notes_from_tool_calls(messages: list[BaseMessage]) -> list[str]:
    """Extract research notes from ToolMessage objects in supervisor message history.

    This function retrieves the compressed research findings that sub-agents
    return as ToolMessage content. When the supervisor delegates research to
    sub-agents via ConductResearch tool calls, each sub-agent returns its
    compressed findings as the content of a ToolMessage. This function
    extracts all such ToolMessage content to compile the final research notes.

    Args:
        messages: List of messages from supervisor's conversation history

    Returns:
        List of research note strings extracted from ToolMessage objects
    """
    return [tool_msg.content for tool_msg in filter_messages(messages, include_types="tool")]

from langsmith import traceable

@traceable
async def supervisor(state: SupervisorState, config: RunnableConfig) ->  Command[Literal["supervisor_tools"]]:
    """Coordinate research activities.

       Analyzes the research brief and current progress to decide:
       - What research topics need investigation
       - Whether to conduct parallel research
       - When research is complete

       Args:
           state: Current supervisor state with messages and research progress

       Returns:
           Command to proceed to supervisor_tools node with updated state
       """

    supervisor_messages = state.get("supervisor_messages",[])
    print(supervisor_messages)
    system_message = lead_researcher_prompt.format(
        date=get_today_str(),
        max_researcher_iterations=max_researcher_iterations,
        max_concurrent_research_units=max_concurrent_researchers_unit  # match the template
    )

    messages = [SystemMessage(content=system_message)] + supervisor_messages

    response = await model_with_tools.ainvoke(messages, config=config)

    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": [response],
            "research_iterations": state.get("research_iterations", 0) + 1
        }
    )

@traceable
async def supervisor_tools(state: SupervisorState) -> Command[Literal["supervisor","__end__"]]:
    """
    Execute supervisor decisions - either conduct research or end the process.

   Handles:
   - Retrieve data from Vector database if relevant information exist there
   - Executing think_tool calls for strategic reflection
   - Launching parallel research agents for different topics
   - Aggregating research results
   - Determining when research is complete

   Args:
       state: Current supervisor state with messages and iteration count

   Returns:
       Command to continue supervision, end process, or handle errors
   """

    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    most_recent_message = supervisor_messages[-1]

    tool_messages = []
    all_raw_notes = []
    next_step = "supervisor"
    trigger_search = state.get("trigger_search", False)
    should_end = False

    exceeded_iterations = research_iterations>=max_researcher_iterations
    no_tool_calls = not most_recent_message.tool_calls

    research_complete = any(
        tool_call["name"] == "ResearchComplete"
        for tool_call in most_recent_message.tool_calls
    )

    if  exceeded_iterations or no_tool_calls or research_complete:
        should_end = True
        next_step = END

    else :
        try:
            think_tool_calls = [tool_call for tool_call in most_recent_message.tool_calls
                                if tool_call["name"]=="think_tool"]

            conduct_research_calls = [tool_call for tool_call in most_recent_message.tool_calls
                                if tool_call["name"]=="ConductResearch"]

            retriever_tool_calls = [tool_call for tool_call in most_recent_message.tool_calls
                                if tool_call["name"]=="retrieve_data_with_score"]

            for tool_call in think_tool_calls:
                observations = think_tool.invoke(tool_call["args"])
                tool_messages.append(ToolMessage(
                    content=observations,
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"]
                ))

            for tool_call in retriever_tool_calls:
                observations = retrieve_data_with_score.invoke(state.get("research_brief",""))
                tool_messages.append(ToolMessage(
                    content=observations,
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"]
                ))

            if conduct_research_calls:
                coros = [
                    research_agent.ainvoke({
                        "researcher_messages": [HumanMessage(content=tool_call["args"]["research_topic"])],
                        "research_topic": tool_call["args"]["research_topic"]
                    })
                    for tool_call in conduct_research_calls
                ]

                tool_results = await asyncio.gather(*coros)

                research_tool_messages = [
                    ToolMessage(
                        content=result.get("compressed_research", "Error synthesizing research report"),
                        name=tool_call["name"],
                        tool_call_id=tool_call["id"]
                    ) for result, tool_call in zip(tool_results, conduct_research_calls)
                ]

                tool_messages.extend(research_tool_messages)

                all_raw_notes = [
                    "\n".join(result.get("raw_notes", []))
                    for result in tool_results
                ]

        except Exception as e:
            print(f"Error in supervisor tools: {e}")
            should_end = True
            next_step = END

    if should_end:
        print(f"IS SEARCH NEEDED:{trigger_search}")
        return Command(
            goto=next_step,
            update={
                "notes": get_notes_from_tool_calls(supervisor_messages),
                "research_brief": state.get("research_brief", ""),
                "trigger_search": trigger_search
            }
        )
    else:
        return Command(
            goto=next_step,
            update={
                "supervisor_messages": tool_messages,
                "raw_notes": all_raw_notes,
                "trigger_search": trigger_search
            }
        )



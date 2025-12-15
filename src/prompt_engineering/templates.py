import yaml
from pathlib import Path

PROMPT_PATH = Path("config/prompt_templates.yaml")

with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATES = yaml.safe_load(f)


def get_prompt(agent_name: str, prompt_name: str) -> str:
    """
    Fetch a specific prompt string for an agent from YAML.

    Args:
        agent_name: Name of the agent (e.g., "scope_agent")
        prompt_name: Name of the prompt (e.g., "clarification_instructions")

    Returns:
        Prompt string ready for .format(...)
    """
    try:
        return PROMPT_TEMPLATES[agent_name][prompt_name]
    except KeyError:
        raise ValueError(f"Prompt '{prompt_name}' not found for agent '{agent_name}'")

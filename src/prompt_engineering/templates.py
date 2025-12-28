import yaml
from pathlib import Path

# 1. Get the directory where templates.py is located
# 2. Go up enough levels to reach the root (PythonProject)
# 3. Then go into config/
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROMPT_PATH = BASE_DIR / "config" / "prompt_templates.yaml"

# Debugging line - this will show up in 'docker logs research_backend'
print(f"DEBUG: Loading YAML from {PROMPT_PATH}")

if not PROMPT_PATH.exists():
    raise FileNotFoundError(f"Could not find the prompt file at {PROMPT_PATH}. "
                            f"Check if the 'config' folder is mapped correctly in Docker.")

with open(PROMPT_PATH, "r", encoding="utf-8") as f:
    PROMPT_TEMPLATES = yaml.safe_load(f)

# ... (rest of your get_prompt function)
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

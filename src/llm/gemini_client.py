import yaml
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
load_dotenv()

CONFIG_PATH = Path("config/model_config.yaml")

with open(CONFIG_PATH, "r") as f:
    MODEL_CONFIG = yaml.safe_load(f)

def create_gemini_model(agent_name: str):
    """
    Initialize a Gemini model for the given agent based on YAML config.
    """
    model_key = MODEL_CONFIG["routing"].get(agent_name)
    if not model_key:
        raise ValueError(f"No model configured for agent: {agent_name}")

    cfg = MODEL_CONFIG["models"][model_key]

    model = ChatGoogleGenerativeAI(
        model=cfg["model"],
        temperature=cfg["temperature"],
        max_output_tokens=cfg["max_tokens"],
        timeout=cfg["timeout"],
        max_retries=cfg["retries"],
    )

    return model

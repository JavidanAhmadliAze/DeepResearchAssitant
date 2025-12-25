import yaml
from pathlib import Path
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from typing import Optional, Dict, Any

load_dotenv()

CONFIG_PATH = Path("config/model_config.yaml")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    MODEL_CONFIG = yaml.safe_load(f)


def create_openai_model(agent_name: str) -> ChatOpenAI:
    """
    Initialize a ChatOpenAI model for the given agent based on YAML configuration.
    """

    # -------------------------------
    # Resolve model routing
    # -------------------------------
    model_key: Optional[str] = MODEL_CONFIG.get("routing", {}).get(agent_name)
    if not model_key:
        raise ValueError(f"No model configured for agent: {agent_name}")

    cfg: Dict[str, Any] = MODEL_CONFIG.get("models", {}).get(model_key)
    if not cfg:
        raise ValueError(f"No configuration found for model key: {model_key}")

    # -------------------------------
    # Build kwargs safely
    # -------------------------------
    model_kwargs: Dict[str, Any] = {
        "model_name": cfg["model"],
        "temperature": cfg.get("temperature", 0.0),
        "request_timeout": cfg.get("timeout", 30),
        "max_retries": cfg.get("retries", 2),
    }

    # Only pass max_tokens if it is a valid int
    if isinstance(cfg.get("max_tokens"), int):
        model_kwargs["max_tokens"] = cfg["max_tokens"]

    return ChatOpenAI(**model_kwargs)

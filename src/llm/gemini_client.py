import yaml
from pathlib import Path
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from typing import Optional, Dict, Any
from langchain_deepseek import ChatDeepSeek
import os
import httpx
granular_timeout = httpx.Timeout(
    connect=5.0,    # Time to establish connection
    read=180.0,     # MAXIMUM: Time waiting for server response (most important!)
    write=10.0,     # Time to send the request
    pool=5.0        # Time to wait for a connection from pool
)
load_dotenv()

CONFIG_PATH = Path("config/model_config.yaml")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    MODEL_CONFIG = yaml.safe_load(f)

def create_model(agent_name: str) -> ChatDeepSeek:
    """
    Initialize a ChatGoogleGenerativeAI model for the given agent based on YAML configuration.
    """
    # 1. Resolve model routing from YAML
    model_key: Optional[str] = MODEL_CONFIG.get("routing", {}).get(agent_name)
    if not model_key:
        raise ValueError(f"No model configured for agent: {agent_name}")

    cfg: Dict[str, Any] = MODEL_CONFIG.get("models", {}).get(model_key)
    if not cfg:
        raise ValueError(f"No configuration found for model key: {model_key}")

    # 2. Build Gemini-specific kwargs
    # Note: langchain-google-genai uses 'model' and 'google_api_key'
    model_kwargs: Dict[str, Any] = {
        "model": cfg["model"],
        "temperature": cfg.get("temperature", 0.0),
        "timeout": granular_timeout,
        "max_retries": cfg.get("retries", 2),
    }

    # Gemini uses 'max_output_tokens' instead of 'max_tokens'
    if isinstance(cfg.get("max_tokens"), int):
        model_kwargs["max_tokens"] = cfg["max_tokens"]

    return ChatDeepSeek(**model_kwargs,streaming= True)
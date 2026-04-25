import os

os.environ.setdefault(
    "KB_URL",
    "https://raw.githubusercontent.com/igortce/python-agent-challenge/refs/heads/main/python_agent_knowledge_base.md",
)
os.environ.setdefault("LLM_API_KEY", "test")
os.environ.setdefault("LLM_MODEL", "gpt-4o-mini")

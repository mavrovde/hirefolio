import sys
from unittest.mock import MagicMock


# Global mocks for dependencies that require Rust/tiktoken or other system deps
def pytest_configure(config):
    import os

    print(
        f"DEBUG: pytest_configure running. SKIP_DEPENDENCY_MOCKING={os.environ.get('SKIP_DEPENDENCY_MOCKING')}"
    )
    if os.environ.get("SKIP_DEPENDENCY_MOCKING"):
        return

    # Mock CrewAI
    mock_crewai = MagicMock()
    sys.modules["crewai"] = mock_crewai
    # Ensure nested modules and classes are available as mocks
    mock_crewai.Agent = MagicMock
    mock_crewai.Task = MagicMock
    mock_crewai.Crew = MagicMock
    mock_crewai.Process = MagicMock

    # Mock LangChain
    mock_lc = MagicMock()
    sys.modules["langchain_community"] = mock_lc
    sys.modules["langchain_community.chat_models"] = mock_lc
    mock_lc.ChatOllama = MagicMock

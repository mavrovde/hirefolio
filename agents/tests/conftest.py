"""Keep the A2A tests hermetic and offline: force the deterministic stub brain
so runs are deterministic and fast regardless of whether Ollama / an API key is
available in the environment."""
import os

os.environ["A2A_LLM_PROVIDER"] = "stub"

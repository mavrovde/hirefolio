import asyncio
import json
import os
import sys
import warnings

# Suppress Pydantic warnings
warnings.filterwarnings("ignore", message="Mixing V1 models and V2 models")

# Add the backend directory to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.multi_chat import multi_agent_conversation, AgentConfig  # noqa: E402


async def run_clean_transcript():
    agents = [
        AgentConfig(
            id=1,
            name="Leo",
            role="Leo",
            goal="Risotto is about tradition and heart.",
            description="Loud old-school Italian chef.",
        ),
        AgentConfig(
            id=2,
            name="Mia",
            role="Mia",
            goal="Risotto is about precision and science.",
            description="Cool analytical scientist.",
        ),
    ]
    topic = "What is the secret to a perfect risotto?"

    print("\n" + "=" * 50)
    print("AGENT CONFIGURATIONS:")
    for agent in agents:
        print(f"Agent {agent.id}: {agent.name}")
        print(f" - Role: {agent.role}")
        print(f" - Goal: {agent.goal}")
        print(f" - Description: {agent.description}")
        print("-" * 20)
    print("=" * 50 + "\n")

    print(f"TOPIC: {topic}\n")
    print("--- CONVERSATION START ---\n")
    current_agent_id = None

    try:
        async for chunk in multi_agent_conversation(agents, topic):
            try:
                data = json.loads(chunk)
                if data.get("done"):
                    break

                agent_id = data.get("agent", 0)
                content = data.get("content", "")

                if not content:
                    continue

                if agent_id != current_agent_id:
                    name = next((a.name for a in agents if a.id == agent_id), "System")
                    if current_agent_id is not None:
                        print("\n", end="", flush=True)
                    print(f"[{name}]: ", end="", flush=True)
                    current_agent_id = agent_id

                print(content, end="", flush=True)
            except Exception:
                pass
    except Exception as e:
        print(f"\nERROR: {e}")

    print("\nTRANSCRIPT_END")


if __name__ == "__main__":
    asyncio.run(run_clean_transcript())

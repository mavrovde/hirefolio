
import asyncio
import os
import sys

# Ensure backend path is in sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.multi_chat import multi_agent_conversation, AgentConfig

async def test_chat():
    print("Starting Multi-Chat Debug...")
    
    agents = [
        AgentConfig(id=1, name="Alice", role="Skeptic", goal="Question everything", description="A skeptical thinker"),
        AgentConfig(id=2, name="Bob", role="Believer", goal="Believe everything", description="An optimistic believer")
    ]
    topic = "Is the earth flat?"

    try:
        async for chunk in multi_agent_conversation(agents, topic):
            print(f"CHUNK: {chunk}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_chat())

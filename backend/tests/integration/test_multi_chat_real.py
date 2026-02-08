import pytest
import json
import asyncio
from app.services.multi_chat import multi_agent_conversation, AgentConfig


@pytest.mark.asyncio
async def test_real_multi_chat_ollama_connection():
    """
    Verifies that the multi-chat service can successfully connect to the
    real Ollama instance, run a dynamic loop, and yield chunks.
    """
    print("\n[Integration] Starting Multi-Chat Real Connection Test...")

    # Setup simple agents
    agents = [
        AgentConfig(
            id=1,
            name="TestAgent1",
            role="Greeter",
            goal="Say hello",
            description="A friendly bot",
        ),
        AgentConfig(
            id=2,
            name="TestAgent2",
            role="Responder",
            goal="Reply hello",
            description="Another friendly bot",
        ),
    ]
    topic = "Just say hello and then STOP. Do not continue."

    # Run conversation with a timeout to prevent hanging
    chunks = []
    try:
        # Set a generous timeout (60s) because loading models (like llama3.2) can take time on the first run
        async with asyncio.timeout(60):
            # We only need a few chunks to prove it works, don't wait for fully finished if it takes too long
            async for chunk in multi_agent_conversation(agents, topic):
                print(f"Received Chunk: {chunk.strip()}")
                chunks.append(chunk)

                # Parse check
                try:
                    data = json.loads(chunk)
                    if data.get("done"):
                        break

                    # If we got valid content from an agent, that's a huge success
                    if data.get("agent") and data.get("agent") > 0 and len(data.get("content", "")) > 0:
                        print(">> agent content received!")
                        # We can break early if we confirmed we got a real response
                        break
                except json.JSONDecodeError:
                    pass

                # Safety break to avoid infinite test hangs
                if len(chunks) > 50:
                    break

    except asyncio.TimeoutError:
        print("Test timed out waiting for Ollama response. This might be due to model loading.")
        # If we got at least some chunks (e.g. system init), we might still consider partial success,
        # but for now let's fail if we didn't get agent content.
        if not any("agent" in c for c in chunks):
             pytest.fail("Test timed out: No agent content received from Ollama.")

    except Exception as e:
        pytest.fail(f"Multi-chat execution failed with error: {e}")

    # Assertions
    assert len(chunks) > 0, "No chunks received from multi-chat service"

    # Check for specific success markers
    # We expect at least one message from an agent or the system finishing
    has_content = any(json.loads(c).get("agent", 0) > 0 for c in chunks if "agent" in c)
    has_done = any(json.loads(c).get("done") is True for c in chunks if "done" in c)

    # Determine pass condition
    assert has_content or has_done, "Conversation yielded nothing meaningful."

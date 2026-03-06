import httpx
import asyncio
import json


async def run_ollama_dialog():
    # Use localhost if running locally, or 'ollama' if in docker
    url = "http://localhost:11434/api/chat"

    payload_alice = {
        "model": "llama3.2",
        "messages": [{"role": "user", "content": "Alice: Hi. Respond in 5 words."}],
        "stream": True,
    }

    print("[Alice]: ", end="", flush=True)
    alice_text = ""
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST", url, json=payload_alice, timeout=30
            ) as response:
                if response.status_code != 200:
                    print(f"Error: {response.status_code}")
                    return
                async for line in response.aiter_lines():
                    if line:
                        chunk = json.loads(line)
                        text = chunk.get("message", {}).get("content", "")
                        print(text, end="", flush=True)
                        alice_text += text
        print("")

        # Bob speaks
        payload_bob = {
            "model": "llama3.2",
            "messages": [
                {
                    "role": "user",
                    "content": f"Bob the Believer here. Alice said: '{alice_text}'. Reply with a friendly optimistic sentence.",
                }
            ],
            "stream": False,
        }

        print("[Bob]: ", end="", flush=True)
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload_bob, timeout=30)
            if resp.status_code == 200:
                bob_text = resp.json()["message"]["content"].strip()
                print(bob_text)
            else:
                print(f"Error: {resp.status_code}")
    except Exception as e:
        print(f"\nCommunication Error: {e}")


if __name__ == "__main__":
    asyncio.run(run_ollama_dialog())

import httpx
import asyncio

async def run_ollama_dialog():
    url = "http://ollama:11434/api/chat"
    
    payload_alice = {
        "model": "tinyllama",
        "messages": [{"role": "user", "content": "Alice: Hi. Respond in 5 words."}],
        "stream": True
    }
    
    print("[Alice]: ", end="", flush=True)
    full_alice = ""
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload_alice, timeout=300) as response:
            async for line in response.aiter_lines():
                if line:
                    chunk = json.loads(line)
                    text = chunk.get("message", {}).get("content", "")
                    print(text, end="", flush=True)
                    full_alice += text
    print("")

    # Bob speaks
    payload_bob = {
        "model": "tinyllama",
        "messages": [
            {"role": "user", "content": f"Bob the Believer here. Alice said: '{alice_text}'. Reply with a friendly optimistic sentence."}
        ],
        "stream": False
    }
    
    print("[Bob]: ", end="", flush=True)
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload_bob, timeout=300)
        bob_text = resp.json()["message"]["content"].strip()
        print(bob_text)

if __name__ == "__main__":
    asyncio.run(run_ollama_dialog())

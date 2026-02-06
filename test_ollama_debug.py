import asyncio
import httpx
import json

async def test_ollama_generate():
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "llama3.1",
        "prompt": "Say 'Test' and nothing else.",
        "stream": False,
        "format": "json"
    }
    print(f"Testing Ollama at {url} with model {payload['model']}...")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            print(f"Status Code: {resp.status_code}")
            print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_ollama_generate())

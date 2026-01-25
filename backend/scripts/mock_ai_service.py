from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

@app.post("/api/generate")
async def generate(request: Request):
    """Mock Ollama generation."""
    body = await request.json()
    print(f"Mock AI Generate called with prompt: {body.get('prompt')[:50]}...")
    
    # Return a mocked generation response structure
    return {
        "model": "tinyllama",
        "created_at": "2023-01-01T00:00:00.000000Z",
        "response": "mocked-tag-1, mocked-tag-2, ai-generated",
        "done": True
    }

@app.post("/api/embeddings")
async def embeddings(request: Request):
    """Mock Ollama embeddings."""
    body = await request.json()
    # Return dummy embedding (768 dimensions for nomic-embed-text)
    return {
        "embedding": [0.1] * 768
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=11434)

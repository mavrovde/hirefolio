#!/usr/bin/env python3
"""
Script to create sample blog posts about Ollama for testing.
Run this after starting the backend service.
"""

import asyncio
import httpx


SAMPLE_POSTS = [
    {
        "title": "Getting Started with Ollama",
        "slug": "getting-started-ollama",
        "content": """# Getting Started with Ollama

Ollama is a powerful tool that allows you to run large language models locally on your machine. This guide will help you get started with Ollama and understand its key features.

## What is Ollama?

Ollama is an open-source project that makes it easy to run LLMs locally. It provides a simple API and command-line interface for managing and running models.

## Installation

Installing Ollama is straightforward:

```bash
# On macOS or Linux
curl https://ollama.ai/install.sh | sh

# On Windows
# Download from https://ollama.ai/download
```

## Running Your First Model

Once installed, you can pull and run models:

```bash
ollama pull llama2
ollama run llama2
```

## Why Use Ollama?

- **Privacy**: Your data stays on your machine
- **Cost-effective**: No API costs
- **Offline capability**: Works without internet
- **Fast**: Local inference is quick

Start exploring Ollama today and unlock the power of local AI!""",
        "summary": "Learn how to get started with Ollama, the tool for running LLMs locally",
        "language": "en",
        "published": True,
    },
    {
        "title": "Ollama Embeddings for Semantic Search",
        "slug": "ollama-embeddings-semantic-search",
        "content": """# Using Ollama for Embeddings and Semantic Search

Ollama isn't just for chat models - it's also excellent for generating embeddings for semantic search applications.

## The nomic-embed-text Model

The `nomic-embed-text` model is specifically designed for embeddings:

- **768 dimensions**: Compact yet powerful
- **Free**: No API costs
- **Fast**: Local processing
- **High quality**: Competitive with commercial solutions

## Implementation

Here's how to use Ollama for embeddings:

```python
import httpx

async def get_embedding(text: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:11434/api/embeddings",
            json={
                "model": "nomic-embed-text",
                "prompt": text,
            }
        )
        return response.json()["embedding"]
```

## Use Cases

- **Document search**: Find relevant documents
- **Recommendation systems**: Suggest similar content
- **Clustering**: Group similar items
- **Duplicate detection**: Find near-duplicates

## Performance

Ollama embeddings are surprisingly fast on modern hardware, making them perfect for production use.

Try it out and see how easy semantic search can be!""",
        "summary": "Discover how to use Ollama's nomic-embed-text model for semantic search",
        "language": "en",
        "published": True,
    },
    {
        "title": "Dockerizing Ollama for Production",
        "slug": "dockerizing-ollama-production",
        "content": """# Running Ollama in Docker for Production

Docker makes it easy to deploy Ollama in production environments. Here's everything you need to know.

## Docker Compose Setup

Create a `docker-compose.yml`:

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    command:
      - |
        /bin/ollama serve &
        sleep 5
        ollama pull nomic-embed-text
        wait

volumes:
  ollama_data:
```

## Benefits

- **Isolation**: Clean separation from host
- **Reproducibility**: Same environment everywhere
- **Scalability**: Easy to scale horizontally
- **Version control**: Pin specific Ollama versions

## Health Checks

Add health checks to ensure Ollama is ready:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
  interval: 10s
  timeout: 5s
  retries: 5
```

## Model Persistence

The volume ensures models persist across container restarts, saving download time.

## Production Tips

1. Use specific image tags, not `latest`
2. Set resource limits
3. Monitor memory usage
4. Use health checks
5. Implement proper logging

Docker + Ollama = Production-ready AI!""",
        "summary": "Learn how to deploy Ollama in Docker for production environments",
        "language": "en",
        "published": True,
    },
    {
        "title": "Ollama vs OpenAI: Cost Comparison",
        "slug": "ollama-vs-openai-cost",
        "content": """# Ollama vs OpenAI: A Cost Analysis

Let's compare the costs of using Ollama versus OpenAI's API for embeddings and LLM inference.

## Embeddings Cost Comparison

### OpenAI (text-embedding-3-small)
- $0.02 per 1M tokens
- 1000 documents (avg 500 tokens): $0.01
- 1M documents: $10

### Ollama (nomic-embed-text)
- **$0** - completely free
- One-time hardware cost
- Unlimited usage

## LLM Inference Costs

### OpenAI (GPT-3.5)
- Input: $0.50 per 1M tokens
- Output: $1.50 per 1M tokens
- 10k queries (avg 100 tokens): $0.50-$1.50

### Ollama (Llama 2)
- **$0** per query
- Only electricity costs
- No rate limits

## Break-Even Analysis

For embeddings:
- Break-even at ~500k documents
- After that, Ollama is pure savings

For LLM inference:
- Break-even at ~5-10k queries
- Depends on hardware costs

## Hidden Costs

### OpenAI
- API rate limits
- Potential price increases
- Data privacy concerns

### Ollama
- Hardware investment
- Maintenance time
- Electricity costs

## Conclusion

For high-volume applications, Ollama offers significant cost savings. For low-volume or experimental use, OpenAI's pay-as-you-go model might be simpler.

Choose based on your scale and requirements!""",
        "summary": "A detailed cost comparison between Ollama and OpenAI for embeddings and LLM usage",
        "language": "en",
        "published": True,
    },
    {
        "title": "Erste Schritte mit Ollama",
        "slug": "erste-schritte-ollama",
        "content": """# Erste Schritte mit Ollama

Ollama ist ein leistungsstarkes Tool, mit dem Sie große Sprachmodelle lokal auf Ihrem Computer ausführen können.

## Was ist Ollama?

Ollama ist ein Open-Source-Projekt, das die lokale Ausführung von LLMs vereinfacht. Es bietet eine einfache API und Befehlszeilenschnittstelle.

## Installation

Die Installation von Ollama ist unkompliziert:

```bash
# Auf macOS oder Linux
curl https://ollama.ai/install.sh | sh
```

## Ihr erstes Modell

Nach der Installation können Sie Modelle herunterladen und ausführen:

```bash
ollama pull llama2
ollama run llama2
```

## Warum Ollama verwenden?

- **Datenschutz**: Ihre Daten bleiben auf Ihrem Computer
- **Kosteneffektiv**: Keine API-Kosten
- **Offline-Fähigkeit**: Funktioniert ohne Internet
- **Schnell**: Lokale Inferenz ist schnell

Beginnen Sie noch heute mit Ollama!""",
        "summary": "Lernen Sie, wie Sie mit Ollama beginnen, dem Tool für lokale LLMs",
        "language": "de",
        "published": True,
    },
]


async def create_posts():
    """Create sample blog posts via API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        for post in SAMPLE_POSTS:
            try:
                response = await client.post(
                    "http://localhost:8000/api/posts", json=post
                )
                if response.status_code == 200:
                    print(f"✓ Created: {post['title']}")
                else:
                    print(f"✗ Failed to create {post['title']}: {response.status_code}")
                    print(f"  Error: {response.text}")
            except Exception as e:
                print(f"✗ Error creating {post['title']}: {e}")


if __name__ == "__main__":
    print("Creating sample blog posts about Ollama...")
    print("Make sure the backend is running on http://localhost:8000\n")
    asyncio.run(create_posts())
    print("\nDone!")

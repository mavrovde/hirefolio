
import asyncio
import sys
import logging

# Configure logging to see errors
logging.basicConfig(level=logging.INFO)

sys.path.append("backend")
from app.config import settings
from app.services import ai

# Ensure settings are loaded (mock if needed, but we want real keys)
# The backend/.env file should be loaded by app.config if running from root?
# No, app.config uses .env file relative to where it's run or CWD.
# We are running from project root, backend/.env is in subdir.
# valid pydantic settings might need explicit env_file.

# Let's force load env
from dotenv import load_dotenv
load_dotenv("backend/.env")

# Update settings in ai module if not already (it imports settings from app.config)
# We might need to patch it if app.config didn't load correctly.
import os
settings.gemini_api_key = os.getenv("GEMINI_API_KEY")

async def test_gen():
    print("--- Testing Full Post Generation ---")
    try:
        post = await ai.generate_full_post(
            topic="Angular Dependency Injection Guide",
            keywords=["angular", "di", "typescript"],
            language="en"
        )
        if post:
            print("Successfully generated post:")
            print(f"Title: {post.get('title')}")
            print(f"Slug: {post.get('slug')}")
            print(f"Tags: {post.get('tags')}")
            print(f"Content Length: {len(post.get('content', ''))}")
        else:
            print("Failed to generate post (returned empty/None).")
            
    except Exception as e:
        print(f"Exception during generation: {e}")

if __name__ == "__main__":
    asyncio.run(test_gen())


import asyncio
import os
from dotenv import load_dotenv

# Load env from backend/.env
load_dotenv("backend/.env")

# Mock settings
class Settings:
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    ollama_url = "http://localhost:11434"
    fast_generation_model = "tinyllama"

import sys
sys.path.append("backend")
from app.services import ai
ai.settings = Settings()

async def test_tags():
    title = "Understanding Angular Dependency Injection"
    content = """
    Dependency Injection (DI) is a core concept in Angular that allows classes to receive dependencies from an external source rather than creating them.
    
    In this article, we will explore:
    1. What is DI?
    2. Hierarchical injectors
    3. Resolution modifiers (@Optional, @Self, @SkipSelf, @Host)
    4. Providers (useClass, useValue, useFactory, useExisting)
    
    DI improves modularity and testability. By decoupling components from their dependencies, we can easily swap implementations, such as using a mock service during testing.
    
    Angular's DI system is hierarchical. This means that if a provider is not found in the current component's injector, Angular looks up the hierarchy to the parent component, and so on, until it reaches the root injector.
    """
    
    print(f"--- Testing Tag Generation ---")
    print(f"Title: {title}")
    
    tags = await ai.suggest_tags(title, content)
    print(f"Generated Tags: {tags}")

    print(f"\n--- Testing Post Details Suggestion ---")
    details = await ai.suggest_post_details(content)
    print(f"Generated Details: {details}")

if __name__ == "__main__":
    asyncio.run(test_tags())

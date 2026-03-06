import os
import asyncio
from app.services.ai import chat_with_gemini


async def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY is missing!")
        exit(1)

    print(f"✅ GEMINI_API_KEY found: {api_key[:5]}...")

    try:
        print("⏳ Sending test request to Gemini (via chat_with_gemini)...")
        # chat_with_gemini returns a string directly
        response = await chat_with_gemini("Hello from backend verification script!")

        if response and not response.startswith("Error:"):
            print(f"✅ Gemini Response: {response}")
            exit(0)
        else:
            print(f"❌ Gemini failed or returned error: {response}")
            exit(1)
    except Exception as e:
        print(f"❌ Gemini connection failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())

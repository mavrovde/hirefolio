import os
from google import genai

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("No API Key")
    exit(1)

client = genai.Client(api_key=api_key)
print("Client dir:", dir(client))
if hasattr(client, "models"):
    print("Client.models dir:", dir(client.models))
if hasattr(client, "chats"):
    print("Client.chats dir:", dir(client.chats))

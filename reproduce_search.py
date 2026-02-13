
import asyncio
import os
import httpx
import sys

# Add backend to path for config import
sys.path.append("backend")
from app.config import settings

async def test_search():
    base_url = "http://localhost:8000/api/app"
    query = "angular dependency injection"
    
    print(f"--- Testing Semantic Search for: '{query}' ---")
    
    async with httpx.AsyncClient() as client:
        # 1. Login to get token
        token = None
        try:
             resp = await client.post(
                 f"{base_url}/auth/login",
                 data={"username": "admin", "password": "admin"},
                 headers={"Content-Type": "application/x-www-form-urlencoded"}
             )
             if resp.status_code == 200:
                 token = resp.json()["access_token"]
                 print("Logged in successfully.")
             else:
                 print(f"Login failed: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"Login exception: {e}")

        headers = {"Authorization": f"Bearer {token}"} if token else {}

        # 2. Check Posts
        try:
            list_resp = await client.get(f"{base_url}/posts", params={"published_only": False}, headers=headers)
            if list_resp.status_code == 200:
                data = list_resp.json()
                total = data.get('total', 0)
                print(f"Total Posts in DB: {total}")
                
                # 3. Generate Seed if empty
                if total == 0 and token:
                    print("No posts found. Generating seed post...")
                    seed_payload = {
                        "topic": "Angular Dependency Injection Guide",
                        "keywords": ["angular", "di", "typescript"],
                        "language": "en"
                    }
                    gen_resp = await client.post(
                        f"{base_url}/posts/generate",
                        json=seed_payload,
                        headers=headers,
                        timeout=120.0
                    )
                    if gen_resp.status_code == 200:
                        print("Seed post generated successfully.")
                        post_data = gen_resp.json()
                        post_id = post_data["id"]
                        
                        # Publish it
                        pub_resp = await client.put(
                            f"{base_url}/posts/{post_id}",
                            json={"published": True},
                            headers=headers
                        )
                        if pub_resp.status_code == 200:
                            print(f"Seed post {post_id} published.")
                    else:
                        print(f"Failed to generate seed post: {gen_resp.text}")
                        return
            else:
                 print(f"List posts failed: {list_resp.status_code}")

        except Exception as e:
             print(f"List/Generate posts failed: {e}")
             return

        # 4. Search
        try:
            print(f"Searching for: {query}")
            response = await client.get(
                f"{base_url}/posts/search/semantic",
                params={"q": query, "limit": 5}
            )
            response.raise_for_status()
            results = response.json()
            
            print(f"Found {len(results)} results:")
            for res in results:
                print(f"- [{res['relevance']:.4f}] {res['title']} ({res['slug']})")
                
        except Exception as e:
            print(f"Search failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_search())

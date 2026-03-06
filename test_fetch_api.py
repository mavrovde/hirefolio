import httpx
import asyncio

async def test_fetch():
    async with httpx.AsyncClient() as client:
        # 1. Login to get token
        login_data = {
            "username": "admin",
            "password": "admin"
        }
        print("Logging in...")
        resp = await client.post("http://localhost:8000/api/app/auth/login", data=login_data)
        if resp.status_code != 200:
            print(f"Login failed: {resp.text}")
            return
            
        token = resp.json()["access_token"]
        print(f"Got token, fetching posts...")
        
        # 2. Fetch posts
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("http://localhost:8000/api/app/linkedin/posts", headers=headers, timeout=120.0)
        
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")

if __name__ == "__main__":
    asyncio.run(test_fetch())

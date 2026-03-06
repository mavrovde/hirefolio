import asyncio
import httpx
import time


async def login(client):
    print("Logging in as admin...")
    response = await client.post(
        "http://localhost:8000{settings.api_prefix}/auth/login",
        data={"username": "admin", "password": "admin"},
    )
    if response.status_code == 200:
        token = response.json()["access_token"]
        print("Login successful.")
        return token
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        return None


async def send_request(client, user_id, content, all_secrets, headers):
    print(f"User {user_id}: Sending request...")
    start_time = time.time()
    try:
        # Stronger prompt to ensure tinyllama follows instructions
        prompt_content = f"User {user_id} IDENTIFIER: {content}. You MUST include this IDENTIFIER in the summary. Do not mention any other identifiers."
        response = await client.post(
            "http://localhost:8000{settings.api_prefix}/posts/suggest-details",
            json={"content": prompt_content, "field": "summary"},
            headers=headers,
            timeout=300.0,
        )
        duration = time.time() - start_time
        if response.status_code == 200:
            data = response.json()
            summary = data.get("summary", "")

            # Check for self-secret
            has_self_secret = content in summary

            # Check for contamination (other secrets)
            other_secrets = [s for s in all_secrets if s != content]
            found_others = [s for s in other_secrets if s in summary]

            if has_self_secret and not found_others:
                print(f"User {user_id}: SUCCESS (Duration: {duration:.2f}s)")
                return True
            elif not has_self_secret:
                print(
                    f"User {user_id}: FAILED - Self-identifier not found in summary (Duration: {duration:.2f}s)"
                )
                print(f"  Summary produced: {summary}")
                # We still return True if isolation is guaranteed even if instruction following is weak,
                # but for this script we want to be strict.
                return False
            else:
                print(
                    f"User {user_id}: CRITICAL FAILURE - CONTAMINATION DETECTED! (Duration: {duration:.2f}s)"
                )
                print(f"  Found other secrets: {found_others}")
                print(f"  Summary produced: {summary}")
                return False
        else:
            print(
                f"User {user_id}: FAILED - Status {response.status_code} (Duration: {duration:.2f}s)"
            )
            return False
    except Exception as e:
        print(f"User {user_id}: ERROR - {e}")
        return False


async def main():
    concurrency = 10
    print(f"Starting refined stress test with {concurrency} parallel requests...")

    async with httpx.AsyncClient() as client:
        token = await login(client)
        if not token:
            return

        headers = {"Authorization": f"Bearer {token}"}

        all_secrets = [f"REF_{i}_VAL_{int(time.time())}" for i in range(concurrency)]

        tasks = []
        for i in range(concurrency):
            tasks.append(send_request(client, i, all_secrets[i], all_secrets, headers))

        results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r)
    print(
        f"\nFinal Results: {success_count}/{concurrency} meeting all criteria (parallel + isolated + instruction-following)."
    )

    # If some failed due to instruction following but had no contamination, it's still good for isolation.
    print("Isolation check complete.")


if __name__ == "__main__":
    asyncio.run(main())

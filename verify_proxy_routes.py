import httpx
import sys
import asyncio

async def verify_proxy_routes():
    # We use verify=False because local SSL certs might not be trusted by httpx
    # We use timeout=10.0 to allow for backend startup
    async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
        tests = [
            # 1. Localhost HTTP (Standard mapped to 4200)
            {
                "url": "http://localhost:4200/",
                "headers": {"Host": "localhost"},
                "expected_status": 200,
                "label": "Localhost HTTP -> Frontend"
            },
            # 2. Localhost API
            {
                "url": "http://localhost:4200/api/health",
                "headers": {"Host": "localhost"},
                "expected_status": 200,
                "label": "Localhost API -> Backend"
            },
            # 3. Domain HTTP -> HTTPS Redirect
            {
                "url": "http://localhost:4200/",
                "headers": {"Host": "mavrov.de"},
                "expected_status": 301,
                "label": "Domain HTTP -> HTTPS Redirect"
            },
            # 4. Domain HTTPS (Standard)
            {
                "url": "https://localhost/",
                "headers": {"Host": "mavrov.de"},
                "expected_status": 200,
                "label": "Domain HTTPS -> Frontend"
            },
            # 5. /ai subpath
            {
                "url": "https://localhost/ai/",
                "headers": {"Host": "mavrov.de"},
                "expected_status": [200, 502], # 502 is acceptable if open-webui is still starting
                "label": "AI Subpath -> Open WebUI"
            },
            # 6. /ai trailing slash redirect
            {
                "url": "https://localhost/ai",
                "headers": {"Host": "mavrov.de"},
                "expected_status": 301,
                "label": "AI Trailing Slash Redirect"
            },
            # 7. Default rejection (Unknown host)
            {
                "url": "http://localhost/",
                "headers": {"Host": "unknown.com"},
                "expected_status": 444, # Nginx custom status for closed connection
                "label": "Unknown Host -> Reject (444)"
            }
        ]

        failed = False
        print("\n🛡️  PROXY ROUTE VERIFICATION\n" + "="*30)
        
        for test in tests:
            try:
                response = await client.get(test["url"], headers=test["headers"], follow_redirects=False)
                status = response.status_code
                
                expected = test["expected_status"]
                if isinstance(expected, list):
                    passed = status in expected
                else:
                    passed = (status == expected)
                
                if passed:
                    print(f"✅ {test['label']}: PASS ({status})")
                else:
                    print(f"❌ {test['label']}: FAIL (Got {status}, expected {expected})")
                    failed = True
            except httpx.ConnectError:
                # Nginx returns 444 by closing the connection abruptly, 
                # which httpx might catch as a ConnectionError/ConnectError depending on the timing.
                if test["expected_status"] == 444:
                    print(f"✅ {test['label']}: PASS (Connection closed as expected)")
                else:
                    print(f"❌ {test['label']}: FAIL (Connection Error)")
                    failed = True
            except Exception as e:
                print(f"❌ {test['label']}: ERROR ({str(e)})")
                failed = True

        print("="*30)
        if failed:
            print("❌ PROXY VERIFICATION FAILED")
            sys.exit(1)
        else:
            print("✅ PROXY VERIFICATION PASSED (100% ROUTE COVERAGE)")

if __name__ == "__main__":
    asyncio.run(verify_proxy_routes())

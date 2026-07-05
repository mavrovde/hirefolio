import httpx
import json

def fetch_profile():
    with open('session.json', 'r') as f:
        cookies_list = json.load(f)
    
    cookies = {c['name']: c['value'] for c in cookies_list}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    # Try fetching the profile directly
    url = "https://www.linkedin.com/in/mavrov/"
    
    with httpx.Client(cookies=cookies, headers=headers, follow_redirects=True) as client:
        resp = client.get(url)
        print("Status code:", resp.status_code)
        print("URL:", resp.url)
        with open("python_profile.html", "w") as out:
            out.write(resp.text)
        print("Length:", len(resp.text))

if __name__ == "__main__":
    fetch_profile()

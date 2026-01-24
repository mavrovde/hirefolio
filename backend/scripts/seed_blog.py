import json
import urllib.request
import urllib.error
import os

API_URL = "http://localhost:8000/api/posts"


def seed_posts():
    base_dir = "../../frontend/src/assets"
    files = {"en": "blog_data_en.json", "de": "blog_data_de.json"}

    for lang, filename in files.items():
        script_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(script_dir, base_dir, filename)
        if not os.path.exists(path):
            print(f"File not found: {path}")
            continue

        with open(path, "r", encoding="utf-8") as f:
            posts = json.load(f)

        for post_data in posts:
            payload = {
                "title": post_data["title"],
                "slug": post_data["id"],
                "content": post_data["content"],
                "summary": post_data["summary"],
                "language": lang,
                "published": True,
            }

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(API_URL, data=data, method="POST")
            req.add_header("Content-Type", "application/json")

            try:
                with urllib.request.urlopen(req) as response:
                    if response.status in [200, 201]:
                        print(f"Successfully seeded: {post_data['id']} ({lang})")
                    else:
                        print(
                            f"Failed to seed {post_data['id']} ({lang}): {response.status}"
                        )
            except urllib.error.HTTPError as e:
                # If 400/409, might already exist
                if e.code in [400, 409]:
                    print(
                        f"Post {post_data['id']} ({lang}) might already exist: {e.code}"
                    )
                else:
                    print(
                        f"HTTP Error seeding {post_data['id']} ({lang}): {e.code} - {e.read().decode()}"
                    )
            except Exception as e:
                print(f"Error seeding {post_data['id']} ({lang}): {str(e)}")


if __name__ == "__main__":
    seed_posts()

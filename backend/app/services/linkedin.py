import logging
import os
import re
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

COOKIES_DIR = "/tmp/linkedin_cookies"  # nosec B108


class LinkedInService:
    """Pure Python LinkedIn service using linkedin-api library."""

    def __init__(self):
        self._client = None
        os.makedirs(COOKIES_DIR, exist_ok=True)

    def _get_client(self):
        """Lazy-initialize the LinkedIn API client."""
        if self._client is not None:
            return self._client

        if not settings.linkedin_email or not settings.linkedin_password:
            raise ValueError(
                "LinkedIn credentials are not configured. "
                "Set LINKEDIN_EMAIL and LINKEDIN_PASSWORD environment variables."
            )

        from linkedin_api import Linkedin

        logger.info("Initializing LinkedIn API client...")

        cookies = None
        if settings.linkedin_cookie_li_at and settings.linkedin_cookie_jsessionid:
            cookies = {
                "li_at": settings.linkedin_cookie_li_at,
                "JSESSIONID": settings.linkedin_cookie_jsessionid,
            }

        self._client = Linkedin(
            settings.linkedin_email,
            settings.linkedin_password,
            cookies=cookies,
            authenticate=False,
            cookies_dir=COOKIES_DIR,
        )

        # We manually authenticate so that if the environment variables aren't set
        # but the cookies directory has a valid session from the Admin UI, we can use it.
        if cookies:
            self._client.client._set_session_cookies(cookies)
            logger.info("Using `.env` provided cookies.")
        else:
            try:
                # This will silently fail if there's no session in the directory and we pass no username/password
                # However we want to attempt to load from the cookies_dir if it exists.
                # `authenticate=False` prevents it from doing it automatically in the constructor which throws on missing params.

                # Check if cookies file exists in the directory
                if os.listdir(COOKIES_DIR):
                    logger.info("Attempting to authenticate using saved cookies...")
                    self._client = Linkedin(
                        "", "", authenticate=True, cookies_dir=COOKIES_DIR
                    )
                    logger.info("Successfully authenticated using saved cookies.")
            except Exception as e:
                logger.warning(f"Could not authenticate using existing cookies: {e}")

        return self._client

    async def login(self, username, password) -> bool:
        """Dynamically logs into LinkedIn using the provided credentials and saves cookies to the volume."""
        from linkedin_api import Linkedin

        logger.info(f"Attempting manual dynamic login for user: {username}")
        try:
            # Setting authenticate=True tells the client to actually log in
            self._client = Linkedin(
                username,
                password,
                authenticate=True,
                cookies_dir=COOKIES_DIR,
                refresh_cookies=True,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to authenticate dynamically: {e}")
            raise Exception(f"Failed to authenticate: {e}")

    async def is_logged_in(self) -> bool:
        """Determines if there is a valid session available."""
        # Fast path 1: Env variabls are provided
        if settings.linkedin_cookie_li_at and settings.linkedin_cookie_jsessionid:
            return True

        # Fast path 2: Has cookies stored in the directory
        return os.path.exists(COOKIES_DIR) and len(os.listdir(COOKIES_DIR)) > 0

    def _get_public_id(self) -> str:
        """Get the LinkedIn public ID from settings."""
        if not settings.linkedin_public_id:
            raise ValueError(
                "LinkedIn public ID is not configured. "
                "Set LINKEDIN_PUBLIC_ID environment variable."
            )
        return settings.linkedin_public_id

    async def fetch_posts(self, count: int = 20) -> list[dict[str, Any]]:
        """
        Fetches recent LinkedIn posts using the Python linkedin-api library.
        Returns posts dynamically — no caching, no Node.js, no rebuild needed.
        """
        client = self._get_client()
        public_id = self._get_public_id()

        logger.info(f"Fetching {count} posts for LinkedIn user: {public_id}")

        try:
            raw_posts = client.get_profile_posts(
                public_id=public_id,
                post_count=count,
            )
        except Exception as e:
            logger.error(f"Failed to fetch LinkedIn posts: {e}")
            raise RuntimeError(f"Failed to fetch LinkedIn posts: {e}")

        # Transform raw Voyager API data into a clean format
        posts = []
        for raw in raw_posts:
            post = self._parse_post(raw)
            if post:
                posts.append(post)

        logger.info(f"Fetched {len(posts)} posts from LinkedIn.")
        return posts

    async def sync_profile(self) -> dict[str, Any]:
        """
        Fetches the complete LinkedIn profile data using Python.
        """
        client = self._get_client()
        public_id = self._get_public_id()

        logger.info(f"Fetching profile for LinkedIn user: {public_id}")

        try:
            profile = client.get_profile(public_id=public_id)
        except Exception as e:
            logger.error(f"Failed to fetch LinkedIn profile: {e}")
            raise RuntimeError(f"Failed to fetch LinkedIn profile: {e}")

        return profile

    @staticmethod
    def _parse_post(raw: dict) -> dict | None:
        """Parse a raw Voyager post into a clean dict."""
        try:
            commentary = ""
            image_url = None
            urn = None

            # Extract URN
            if "updateMetadata" in raw:
                urn = raw.get("updateMetadata", {}).get("urn", "")
            elif "*updateMetadata" in raw:
                urn = raw.get("*updateMetadata", "")

            # Extract text content from commentary
            content = raw.get("commentary", {})
            if isinstance(content, dict):
                commentary = content.get("text", "")
            elif isinstance(content, str):
                commentary = content

            # Try alternative text locations
            if not commentary:
                commentary = raw.get("text", "")

            if not commentary:
                # Some posts have nested structure
                update_content = raw.get("content", {})
                if isinstance(update_content, dict):
                    article = update_content.get("article", {})
                    if article:
                        commentary = article.get("title", "")

            # Extract image
            content_obj = raw.get("content", {})
            if isinstance(content_obj, dict):
                images = content_obj.get("images", [])
                if images and len(images) > 0:
                    img = images[0]
                    if isinstance(img, dict):
                        artifacts = img.get("attributes", [])
                        if artifacts:
                            image_url = (
                                artifacts[0].get("vectorImage", {}).get("rootUrl", "")
                            )

            if not commentary:
                return None

            return {
                "content": commentary,
                "image_url": image_url,
                "urn": urn or "",
            }
        except Exception as e:
            logger.warning(f"Failed to parse post: {e}")
            return None


linkedin_service = LinkedInService()

# ---------------------------------------------------------------------------
# Pure text-normalization helpers (no I/O, no network)
# ---------------------------------------------------------------------------

_ZERO_WIDTH = re.compile(r"[\u200b\u200e\u200f\ufeff]")
_EXCESS_NEWLINES = re.compile(r"\n{3,}")
_HASHTAG_TOKEN = re.compile(r"#([A-Za-z]\w*)")


def normalize_linkedin_text(text: str) -> str:
    """Return a cleaned version of raw scraped LinkedIn post text."""
    if not text or not text.strip():
        return ""
    # Strip zero-width / bidi chars
    text = _ZERO_WIDTH.sub("", text)
    # NBSP → regular space
    text = text.replace("\u00a0", " ")
    # Remove bare 'hashtag' label lines (LinkedIn UI artefact) — line-based scan is
    # linear / ReDoS-safe (the old `[ \t]*hashtag[ \t]*\n` regex was O(n^2) on crafted
    # whitespace input; CodeQL py/polynomial-redos, alert #28).
    text = "\n".join(
        line for line in text.split("\n") if line.strip().lower() != "hashtag"
    )
    # Collapse 3+ consecutive newlines to exactly two
    text = _EXCESS_NEWLINES.sub("\n\n", text)
    # Trim leading/trailing whitespace
    return text.strip()


def extract_hashtags(text: str) -> list[str]:
    """Return up to 5 unique hashtags (without #) in first-seen order."""
    if not text or not text.strip():
        return []
    seen: dict[str, str] = {}
    for match in _HASHTAG_TOKEN.finditer(text):
        word = match.group(1)
        key = word.lower()
        if key not in seen:
            seen[key] = word
        if len(seen) == 5:
            break
    return list(seen.values())

import logging
from typing import Dict, Any, List

from app.config import settings

logger = logging.getLogger(__name__)


class LinkedInService:
    """Pure Python LinkedIn service using linkedin-api library."""

    def __init__(self):
        self._client = None

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
        self._client = Linkedin(
            settings.linkedin_email,
            settings.linkedin_password,
        )
        return self._client

    def _get_public_id(self) -> str:
        """Get the LinkedIn public ID from settings."""
        if not settings.linkedin_public_id:
            raise ValueError(
                "LinkedIn public ID is not configured. "
                "Set LINKEDIN_PUBLIC_ID environment variable."
            )
        return settings.linkedin_public_id

    async def fetch_posts(self, count: int = 20) -> List[Dict[str, Any]]:
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

    async def sync_profile(self) -> Dict[str, Any]:
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

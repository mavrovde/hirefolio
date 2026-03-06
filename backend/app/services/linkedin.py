import os
import json
import asyncio
import logging
from typing import Dict, Any, List

from app.config import settings

logger = logging.getLogger(__name__)


class LinkedInService:
    def __init__(self):
        # We assume the scraper directory is at the root of the project
        self.scraper_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../scraper"))
        self.node_executable = "node"

    async def _run_scraper(self, script_name: str, output_file: str) -> List | Dict[str, Any]:
        """
        Runs a Node.js scraper script and returns the parsed JSON output.
        """
        if not settings.linkedin_email or not settings.linkedin_password:
            raise ValueError("LinkedIn credentials are not configured in the environment.")

        # Prepare environment variables for the Node.js script
        env = os.environ.copy()
        env["LINKEDIN_EMAIL"] = settings.linkedin_email
        env["LINKEDIN_PASSWORD"] = settings.linkedin_password
        env["HEADLESS"] = "true"

        script_path = os.path.join(self.scraper_dir, script_name)
        output_path = os.path.join(self.scraper_dir, output_file)

        logger.info(f"Running LinkedIn scraper script: {script_name}")
        
        # We use asyncio.create_subprocess_exec to run the node script without blocking the event loop
        process = await asyncio.create_subprocess_exec(
            self.node_executable,
            script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.scraper_dir,
            env=env
        )

        try:
            # Enforce a 120-second timeout to prevent indefinite hanging if UI changes break the scraper
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120.0)
        except asyncio.TimeoutError:
            logger.error(f"Scraper timed out after 120 seconds: {script_name}")
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                pass
            raise RuntimeError(f"LinkedIn scraper timed out. LinkedIn might have changed their UI or blocked the request.")

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"Scraper failed with code {process.returncode}: {error_msg}")
            raise RuntimeError(f"LinkedIn scraper failed: {error_msg}")

        # Try to read the output file
        if not os.path.exists(output_path):
            raise FileNotFoundError(f"Scraper output file not found: {output_path}. Check server logs for details.")

        try:
            with open(output_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scraper output: {e}")
            raise ValueError("Invalid JSON returned from scraper")

    async def fetch_posts(self) -> List[Dict[str, Any]]:
        """
        Fetches recent LinkedIn posts using the Node.js scraper.
        """
        posts = await self._run_scraper("scrape-posts.js", "posts_data.json")
        if not isinstance(posts, list):
            logger.warning("Expected a list of posts, got something else.")
            return []
        return posts

    async def sync_profile(self) -> Dict[str, Any]:
        """
        Fetches the complete LinkedIn profile data.
        """
        profile_data = await self._run_scraper("scrape-linkedin.js", "profile_data.json")
        return profile_data


linkedin_service = LinkedInService()

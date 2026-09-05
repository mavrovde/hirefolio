"""Public site-identity configuration (#65).

The frontend is shipped as a prebuilt image; identity must therefore be a
RUNTIME concern. This endpoint is the single source the public app reads at
bootstrap — owner name, headline, canonical URL, social links, analytics id —
all derived from env-driven settings (`app.config.Settings`), never hardcoded
in components. The payload is public by design: everything in it is already
rendered on the public site.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/config", tags=["config"])


class SiteConfig(BaseModel):
    site_name: str
    site_url: str
    owner_name: str
    owner_headline: str
    owner_description: str
    contact_email: str
    social_links: list[str]
    analytics_id: str


@router.get("/site", response_model=SiteConfig)
async def get_site_config() -> SiteConfig:
    """Return the site's public identity configuration."""
    return SiteConfig(
        site_name=settings.site_name,
        site_url=settings.site_url.rstrip("/"),
        owner_name=settings.owner_name,
        owner_headline=settings.owner_headline,
        owner_description=settings.owner_description,
        contact_email=settings.admin_email,
        social_links=[s.strip() for s in settings.social_links.split(",") if s.strip()],
        analytics_id=settings.analytics_id,
    )

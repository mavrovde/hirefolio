"""Public site-identity configuration (#65).

The frontend is shipped as a prebuilt image; identity must therefore be a
RUNTIME concern. This endpoint is the single source the public app reads at
bootstrap — owner name, headline, canonical URL, social links, analytics id —
all derived from env-driven settings (`app.config.Settings`), never hardcoded
in components. The payload is public by design and must contain ONLY data the
public site already renders — notably NOT admin_email, which doubles as the
admin login username (#255 review: publishing it unauthenticated was an
information leak with zero consumers). Visitor-facing contact comes from the
profile data, not from here.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.site_settings import read_availability
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/config", tags=["config"])


class SiteConfig(BaseModel):
    site_name: str
    site_url: str
    owner_name: str
    owner_headline: str
    owner_description: str
    social_links: list[str]
    analytics_id: str
    # Runtime, admin-editable (#271) — the job-search state the hero renders.
    # Public by design: its whole purpose is to be shown to visitors.
    availability: str


@router.get("/site", response_model=SiteConfig)
async def get_site_config(db: AsyncSession = Depends(get_db)) -> SiteConfig:
    """Return the site's public identity configuration."""
    return SiteConfig(
        site_name=settings.site_name,
        site_url=settings.site_url.rstrip("/"),
        owner_name=settings.owner_name,
        owner_headline=settings.owner_headline,
        owner_description=settings.owner_description,
        social_links=[s.strip() for s in settings.social_links.split(",") if s.strip()],
        analytics_id=settings.analytics_id,
        availability=await read_availability(db),
    )

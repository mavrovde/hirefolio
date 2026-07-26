from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.profile_snapshot import ProfileSnapshot
from app.logger import logger

router = APIRouter(prefix="/profile", tags=["profile"])

# Languages the site serves. Keep in sync with the frontend LanguageService.
SUPPORTED_LANGUAGES = ("en", "de")

# Only these top-level fields are exposed publicly. The raw uploaded scraper JSON
# is stored as-is but NEVER served as-is: a LinkedIn export can carry non-public
# PII (phone, address, birthday, connections, contactInfo). Serving through this
# allowlist guarantees only portfolio-safe fields reach unauthenticated callers.
PUBLIC_PROFILE_FIELDS = frozenset(
    {
        "name",
        "headline",
        "location",
        "about",
        "experience",
        "education",
        "skills",
        "certifications",
        "languages",
        "recommendations",
        "projects",
    }
)
# Within `contact`, only these are public (email + linkedin are shown on the site).
PUBLIC_CONTACT_FIELDS = frozenset({"email", "linkedin"})


def public_profile_view(data: object) -> dict:
    """Project stored profile data down to the public allowlist."""
    if not isinstance(data, dict):
        return {}
    view: dict = {k: v for k, v in data.items() if k in PUBLIC_PROFILE_FIELDS}
    contact = data.get("contact")
    if isinstance(contact, dict):
        view["contact"] = {
            k: v for k, v in contact.items() if k in PUBLIC_CONTACT_FIELDS
        }
    return view


@router.get("")
async def get_active_profile(
    lang: str = Query("en", description="Profile language (en|de)"),
    db: AsyncSession = Depends(get_db),
):
    """Return the raw ``data`` of the active profile for ``lang``.

    404 when no version has been uploaded/activated for that language yet — the
    frontend falls back to its bundled static asset in that case, so the site is
    never blank before the first upload.
    """
    language = lang.lower()
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{lang}'. Supported: {', '.join(SUPPORTED_LANGUAGES)}.",
        )

    result = await db.execute(
        select(ProfileSnapshot).where(
            ProfileSnapshot.is_active.is_(True),
            ProfileSnapshot.language == language,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        logger.info("No active profile for language=%s", language)
        raise HTTPException(
            status_code=404, detail=f"No active profile for language '{language}'."
        )
    # Never serve the raw uploaded blob — project to the public allowlist so an
    # uploaded scraper JSON cannot leak non-public PII.
    return public_profile_view(profile.data)

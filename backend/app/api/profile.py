from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.logger import logger
from app.models.profile_snapshot import ProfileSnapshot
from app.services.rate_limit import SlidingWindowRateLimiter, rate_limit_dependency
from app.services.readiness import is_undefined_table_error

router = APIRouter(prefix="/profile", tags=["profile"])

# Public, unauthenticated GETs on this router are rate-limited per client IP
# (defense-in-depth against scraping/abuse) — see `app.services.rate_limit`.
profile_rate_limiter = SlidingWindowRateLimiter(
    max_requests=settings.profile_rate_limit_requests,
    window_seconds=settings.profile_rate_limit_window_seconds,
)
_enforce_rate_limit = rate_limit_dependency(profile_rate_limiter)

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


@router.get("", dependencies=[Depends(_enforce_rate_limit)])
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

    try:
        result = await db.execute(
            select(ProfileSnapshot).where(
                ProfileSnapshot.is_active.is_(True),
                ProfileSnapshot.language == language,
            )
        )
    except ProgrammingError as exc:
        # Startup race (#124): the entrypoint's `alembic upgrade head` has not
        # created `profile_snapshots` yet. Return a graceful, retryable 503
        # instead of leaking a raw 500 UndefinedTableError during warm-up.
        if is_undefined_table_error(exc):
            logger.warning(
                "profile_snapshots not yet migrated (startup warm-up, #124): %s", exc
            )
            raise HTTPException(
                status_code=503,
                detail="Service is starting up, please retry shortly.",
            ) from exc
        raise
    profile = result.scalar_one_or_none()
    if profile is None:
        logger.info("No active profile for language=%s", language)
        raise HTTPException(
            status_code=404, detail=f"No active profile for language '{language}'."
        )
    # Never serve the raw uploaded blob — project to the public allowlist so an
    # uploaded scraper JSON cannot leak non-public PII.
    return public_profile_view(profile.data)

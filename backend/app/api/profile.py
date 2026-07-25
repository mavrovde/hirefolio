from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.profile_version import ProfileVersion
from app.logger import logger

router = APIRouter(prefix="/profile", tags=["profile"])

# Languages the site serves. Keep in sync with the frontend LanguageService.
SUPPORTED_LANGUAGES = ("en", "de")


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
        select(ProfileVersion).where(
            ProfileVersion.is_active.is_(True),
            ProfileVersion.language == language,
        )
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        logger.info("No active profile for language=%s", language)
        raise HTTPException(
            status_code=404, detail=f"No active profile for language '{language}'."
        )
    return profile.data

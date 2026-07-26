import json
import uuid
from math import ceil

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.logger import logger
from app.models.profile_snapshot import ProfileSnapshot
from app.models.user import User
from app.services.auth import get_current_admin_user

router = APIRouter(prefix="/admin/profile", tags=["admin-profile"])

SUPPORTED_LANGUAGES = ("en", "de")

# Bound the uploaded profile JSON so even an authenticated admin (or a stolen
# admin token) can't exhaust memory with a huge body.
MAX_PROFILE_JSON_BYTES = 5 * 1024 * 1024  # 5 MB

# Only these columns may drive ORDER BY (prevents an uncaught 500 from a
# non-orderable class attribute reaching order_by).
SORTABLE_COLUMNS = frozenset({"created_at", "version", "language", "is_active"})


def _validate_language(language: str) -> str:
    lang = (language or "").lower()
    if lang not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{language}'. Supported: {', '.join(SUPPORTED_LANGUAGES)}.",
        )
    return lang


@router.post("/upload")
async def upload_profile(
    file: UploadFile = File(...),
    version: str = Form(...),
    language: str = Form("en"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Upload a scraper ``profile_data.json`` as a new active version for a language.

    The raw JSON object is stored as-is. Uploading deactivates every other version
    **for that language only** and makes the new one active immediately.
    """
    lang = _validate_language(language)

    version_clean = (version or "").strip()
    if not version_clean:
        raise HTTPException(status_code=400, detail="Version must not be empty.")

    raw = await file.read(MAX_PROFILE_JSON_BYTES + 1)
    if len(raw) > MAX_PROFILE_JSON_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Profile JSON exceeds {MAX_PROFILE_JSON_BYTES // (1024 * 1024)} MB limit.",
        )
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="File is not valid JSON.")
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=400, detail="Profile JSON must be a top-level object."
        )

    # Reject duplicate (version, language) up front for a clean 409.
    existing = await db.scalar(
        select(ProfileSnapshot).where(
            ProfileSnapshot.version == version_clean,
            ProfileSnapshot.language == lang,
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Version '{version_clean}' already exists for language '{lang}'.",
        )

    try:
        # Deactivate other versions for THIS language only (multilanguage-safe).
        await db.execute(
            update(ProfileSnapshot)
            .where(ProfileSnapshot.language == lang)
            .values(is_active=False)
        )
        row = ProfileSnapshot(
            version=version_clean, language=lang, data=data, is_active=True
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        logger.info(
            "Admin %s uploaded profile version %s (%s)",
            admin.email,
            version_clean,
            lang,
        )
        return {"success": True, "version": version_clean, "language": lang}
    except Exception as e:
        logger.error("Error uploading profile: %s", e)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to upload profile")


@router.get("/versions")
async def get_profile_snapshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    language: str = Query(None, description="Filter by language (en|de)"),
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Paginated version list (metadata only — the raw ``data`` blob is omitted)."""
    query = select(ProfileSnapshot)
    if language:
        query = query.where(ProfileSnapshot.language == language.lower())

    total_raw = await db.scalar(select(func.count()).select_from(query.subquery()))
    total = int(total_raw) if total_raw is not None else 0

    if sort_by in SORTABLE_COLUMNS:
        order_column = getattr(ProfileSnapshot, sort_by)
        query = query.order_by(
            order_column.desc() if sort_order == "desc" else order_column.asc()
        )
    else:
        query = query.order_by(ProfileSnapshot.created_at.desc())

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    rows = result.scalars().all()
    total_pages = ceil(total / page_size) if total > 0 else 1

    return {
        "items": [
            {
                "id": row.id,
                "version": row.version,
                "language": row.language,
                "is_active": row.is_active,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.patch("/versions/{version_id}/activate")
async def activate_profile_version(
    version_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_user),
):
    """Make an existing version the active one for its language."""
    row = await db.get(ProfileSnapshot, version_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Profile version not found.")

    try:
        await db.execute(
            update(ProfileSnapshot)
            .where(ProfileSnapshot.language == row.language)
            .values(is_active=False)
        )
        row.is_active = True
        await db.commit()
        await db.refresh(row)
        logger.info(
            "Admin %s activated profile version %s (%s)",
            admin.email,
            row.version,
            row.language,
        )
        return {
            "success": True,
            "id": row.id,
            "version": row.version,
            "language": row.language,
        }
    except Exception as e:
        logger.error("Error activating profile version: %s", e)
        await db.rollback()
        raise HTTPException(
            status_code=500, detail="Failed to activate profile version"
        )

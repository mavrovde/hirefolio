import logging
import random
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.post import Post
from app.models.user import User
from app.services.auth import get_current_admin_user
from app.services.embeddings import get_embedding
from app.services.linkedin import linkedin_service
from app.config import settings

router = APIRouter(prefix="/linkedin", tags=["linkedin"])
logger = logging.getLogger(__name__)


class LinkedInLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login_linkedin(
    login_data: LinkedInLoginRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """
    Dynamically authenticates with LinkedIn and saves session cookies to the server.
    """
    logger.info(f"[LinkedIn] Dynamic login requested by user: {current_user.username}")
    try:
        success = await linkedin_service.login(login_data.username, login_data.password)
        if success:
            return {"message": "Successfully logged in and saved session."}
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Login failed. Check credentials and MFA.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[LinkedIn] Dynamic login FAILED: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Login failed: {str(e)}",
        )


@router.get("/status")
async def get_linkedin_status(
    current_user: User = Depends(get_current_admin_user),
):
    """
    Checks if there is an active valid LinkedIn session available.
    """
    is_logged_in = await linkedin_service.is_logged_in()
    return {"logged_in": is_logged_in}


@router.get("/profile-sync")
async def sync_linkedin_profile(
    current_user: User = Depends(get_current_admin_user),
):
    """
    Fetches the LinkedIn profile data using the Playwright scraper.
    """
    logger.info(
        "[LinkedIn] profile-sync requested by user=%s | creds_configured: email=%s, public_id=%s",
        current_user.username,
        bool(settings.linkedin_email),
        bool(settings.linkedin_public_id),
    )
    try:
        profile_data = await linkedin_service.sync_profile()
        logger.info(
            "[LinkedIn] profile-sync SUCCESS: returned %d fields",
            len(profile_data) if isinstance(profile_data, dict) else 0,
        )
        return profile_data
    except ValueError as e:
        logger.error("[LinkedIn] profile-sync CONFIG ERROR: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LinkedIn config error: {e}",
        )
    except Exception as e:
        logger.error("[LinkedIn] profile-sync FAILED: %s (%s)", e, type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LinkedIn profile sync failed: {e}",
        )


@router.get("/posts")
async def get_linkedin_posts(
    current_user: User = Depends(get_current_admin_user),
):
    """
    Fetches recent LinkedIn posts using the Playwright scraper.
    """
    logger.info(
        "[LinkedIn] /posts requested by user=%s | creds_configured: email=%s, public_id=%s",
        current_user.username,
        bool(settings.linkedin_email),
        bool(settings.linkedin_public_id),
    )
    try:
        posts = await linkedin_service.fetch_posts()
        posts_with_images = sum(1 for p in posts if p.get("image_url"))
        logger.info(
            "[LinkedIn] /posts SUCCESS: %d posts fetched (%d with images)",
            len(posts),
            posts_with_images,
        )
        return posts
    except ValueError as e:
        logger.warning("[LinkedIn] /posts NOT CONFIGURED: %s", e)
        return []
    except Exception as e:
        logger.error("[LinkedIn] /posts FAILED: %s (%s)", e, type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LinkedIn posts fetch failed: {e}",
        )


class TransferPostRequest(BaseModel):
    content: str
    image_url: str | None = None
    urn: str | None = None


async def _create_post_from_transfer(post_data: TransferPostRequest) -> Post:
    """Shared helper to create a Post from a TransferPostRequest."""
    title = post_data.content[:50].strip()
    if not title:
        title = "LinkedIn Post"
        if post_data.content and len(post_data.content) > 50:
            title += "..."

    slug_base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug_base:
        slug_base = "linkedin-post"
    slug = f"{slug_base}-{random.randint(1000, 9999)}"

    text_for_embedding = f"{title}\n\n{post_data.content}"
    embedding = await get_embedding(text_for_embedding)

    logger.debug(
        "[LinkedIn] _create_post: title=%r, slug=%s, image_url=%s, content_len=%d",
        title,
        slug,
        post_data.image_url or "none",
        len(post_data.content),
    )

    return Post(
        title=title,
        slug=slug,
        content=post_data.content,
        summary="Imported from LinkedIn",
        image_url=post_data.image_url,
        language="en",
        published=False,
        tags=["LinkedIn"],
        embedding=embedding,
    )


@router.post("/transfer-post")
async def transfer_linkedin_post(
    post_data: TransferPostRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Transfers a single scraped LinkedIn post into the local database as a draft.
    """
    logger.info(
        "[LinkedIn] transfer-post: user=%s, content_len=%d, has_image=%s, urn=%s",
        current_user.username,
        len(post_data.content),
        bool(post_data.image_url),
        post_data.urn or "none",
    )
    try:
        post = await _create_post_from_transfer(post_data)
        db.add(post)
        await db.commit()
        await db.refresh(post)
        logger.info(
            "[LinkedIn] transfer-post SUCCESS: id=%s, title=%r", post.id, post.title
        )
        return {"id": post.id, "message": "Post transferred successfully"}
    except Exception as e:
        await db.rollback()
        logger.error("[LinkedIn] transfer-post FAILED: %s (%s)", e, type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transfer failed: {e}",
        )


@router.post("/transfer-posts")
async def transfer_linkedin_posts(
    posts_data: list[TransferPostRequest],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Transfers multiple LinkedIn posts into the local database as drafts.
    """
    logger.info(
        "[LinkedIn] transfer-posts BULK: user=%s, count=%d",
        current_user.username,
        len(posts_data),
    )
    transferred = []
    try:
        for i, post_data in enumerate(posts_data):
            logger.info(
                "[LinkedIn] transfer-posts [%d/%d]: content_len=%d, has_image=%s",
                i + 1,
                len(posts_data),
                len(post_data.content),
                bool(post_data.image_url),
            )
            post = await _create_post_from_transfer(post_data)
            db.add(post)
            transferred.append(post)
        await db.commit()
        for post in transferred:
            await db.refresh(post)
        logger.info(
            "[LinkedIn] transfer-posts SUCCESS: %d posts transferred, ids=%s",
            len(transferred),
            [p.id for p in transferred],
        )
        return {
            "transferred": len(transferred),
            "ids": [p.id for p in transferred],
            "message": f"Successfully transferred {len(transferred)} posts",
        }
    except Exception as e:
        await db.rollback()
        logger.error(
            "[LinkedIn] transfer-posts FAILED at post %d: %s (%s)",
            len(transferred) + 1,
            e,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk transfer failed: {e}",
        )

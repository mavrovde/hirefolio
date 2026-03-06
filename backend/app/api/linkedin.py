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

router = APIRouter(prefix="/linkedin", tags=["linkedin"])
logger = logging.getLogger(__name__)


@router.get("/profile-sync")
async def sync_linkedin_profile(
    current_user: User = Depends(get_current_admin_user),
):
    """
    Fetches the LinkedIn profile data using the Playwright scraper.
    """
    try:
        profile_data = await linkedin_service.sync_profile()
        return profile_data
    except ValueError as e:
        logger.error(f"Configuration error checking LinkedIn: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error syncing LinkedIn profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to sync LinkedIn profile. Please check server logs.",
        )


@router.get("/posts")
async def get_linkedin_posts(
    current_user: User = Depends(get_current_admin_user),
):
    """
    Fetches recent LinkedIn posts using the Playwright scraper.
    """
    try:
        posts = await linkedin_service.fetch_posts()
        return posts
    except ValueError as e:
        logger.error(f"Configuration error fetching LinkedIn posts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error fetching LinkedIn posts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch LinkedIn posts. Please check server logs.",
        )


class TransferPostRequest(BaseModel):
    content: str
    image_url: str | None = None
    urn: str | None = None


@router.post("/transfer-post")
async def transfer_linkedin_post(
    post_data: TransferPostRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """
    Transfers a scraped LinkedIn post into the local database as a draft.
    """
    # Create a basic title from the content (first 50 chars)
    title = post_data.content[:50].strip()
    if not title:
        title = "LinkedIn Post"
        if post_data.content and len(post_data.content) > 50:
            title += "..."

    # Generate a slug

    slug_base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not slug_base:
        slug_base = "linkedin-post"
    slug = f"{slug_base}-{random.randint(1000, 9999)}"

    # Generate embedding
    text_for_embedding = f"{title}\n\n{post_data.content}"
    embedding = await get_embedding(text_for_embedding)

    post = Post(
        title=title,
        slug=slug,
        content=post_data.content,
        summary="Imported from LinkedIn",
        image_url=post_data.image_url,
        language="en",  # Defaulting to English, could be changed in UI
        published=False,  # Save as draft by default
        tags=["LinkedIn"],
        embedding=embedding,
    )

    try:
        db.add(post)
        await db.commit()
        await db.refresh(post)
        return {"id": post.id, "message": "Post transferred successfully"}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error transferring LinkedIn post: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save the post to the database.",
        )

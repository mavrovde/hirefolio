from fastapi import APIRouter, Depends
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Dict

from app.database import get_db
from app.models.post import Post
from app.models.user import User
from app.services.auth import get_current_admin_user

router = APIRouter(prefix="/api/stats", tags=["stats"])

class PostStats(BaseModel):
    total: int
    published: int
    drafts: int
    by_language: Dict[str, int]

class PostSummary(BaseModel):
    title: str
    slug: str
    created_at: str
    views: int = 0

class SystemStats(BaseModel):
    posts: PostStats
    users: int
    subscribers: int
    visitors: str
    top_tags: Dict[str, int] = {}
    recent_posts: List[PostSummary] = []
    system_health: Dict[str, bool] = {"database": True, "ai_service": False}

@router.get("", response_model=SystemStats)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Get system statistics for the dashboard.
    Requires admin privileges.
    """
    
    # Posts Stats
    total_posts = await db.scalar(select(func.count(Post.id)))
    published_posts = await db.scalar(select(func.count(Post.id)).where(Post.published == True))
    draft_posts = total_posts - published_posts
    
    # By Language
    langs_result = await db.execute(select(Post.language, func.count(Post.id)).group_by(Post.language))
    by_lang = {lang:count for lang, count in langs_result.all()}
    
    # Users Stats
    total_users = await db.scalar(select(func.count(User.id)))
    
    # Top Tags (Top 5)
    tags_query = (
        select(
            func.unnest(Post.tags).label("tag"),
            func.count(Post.id).label("count")
        )
        .group_by("tag")
        .order_by(text("count DESC"))
        .limit(5)
    )
    tags_res = await db.execute(tags_query)
    top_tags = {row.tag: row.count for row in tags_res.all()}
    
    # Recent Posts (Top 5)
    recent_query = select(Post).order_by(Post.created_at.desc()).limit(5)
    recent_res = await db.execute(recent_query)
    recent_posts_data = [
        PostSummary(
            title=p.title,
            slug=p.slug,
            created_at=p.created_at.isoformat()
        )
        for p in recent_res.scalars().all()
    ]
    
    # System Health Check (Ollama)
    import httpx
    from app.config import settings
    ai_status = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(settings.ollama_url)
            ai_status = resp.status_code == 200
    except:
        ai_status = False
    
    return SystemStats(
        posts=PostStats(
            total=total_posts,
            published=published_posts,
            drafts=draft_posts,
            by_language=by_lang
        ),
        users=total_users,
        subscribers=0,
        visitors="See Google Analytics",
        top_tags=top_tags,
        recent_posts=recent_posts_data,
        system_health={"database": True, "ai_service": ai_status}
    )

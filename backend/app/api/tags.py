from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List

from app.database import get_db
from app.models.post import Post
from app.models.user import User
from app.services.auth import get_current_admin_user

router = APIRouter(prefix="/api/tags", tags=["tags"])

class TagStat(BaseModel):
    name: str
    count: int

class TagRename(BaseModel):
    new_name: str

@router.get("", response_model=List[TagStat])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """List all tags and their usage counts."""
    # Since tags are in an ARRAY column, we need to unnest them to count.
    # PostgreSQL specific query using unnest
    query = (
        select(
            func.unnest(Post.tags).label("tag"),
            func.count(Post.id).label("count")
        )
        .group_by("tag")
        .order_by(text("count DESC"))
    )
    
    result = await db.execute(query)
    tags = result.all()
    
    return [
        TagStat(name=row.tag, count=row.count)
        for row in tags
    ]

@router.put("/{old_name}")
async def rename_tag(
    old_name: str,
    tag_data: TagRename,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Rename a tag across all posts."""
    # This requires finding all posts with the old tag and replacing it.
    # Postgres array_replace can do this efficiently.
    
    # Check if any posts have this tag
    # Using raw SQL for array_replace might be easiest with SQLAlchemy if ORM doesn't support it directly easily
    # update(Post).where(Post.tags.contains([old_name])).values(tags=func.array_replace(Post.tags, old_name, new_name))
    
    stmt = (
        update(Post)
        .where(Post.tags.contains([old_name]))
        .values(tags=func.array_replace(Post.tags, old_name, tag_data.new_name))
        .execution_options(synchronize_session=False) 
    )
    # synchronize_session=False because we are calling a db function array_replace
    
    result = await db.execute(stmt)
    await db.commit()
    
    return {"message": f"Tag renamed. Affected {result.rowcount} posts."}

@router.delete("/{name}")
async def delete_tag(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Remove a tag from all posts."""
    # Postgres array_remove
    stmt = (
        update(Post)
        .where(Post.tags.contains([name]))
        .values(tags=func.array_remove(Post.tags, name))
        .execution_options(synchronize_session=False)
    )
    
    result = await db.execute(stmt)
    await db.commit()
    
    return {"message": f"Tag removed. Affected {result.rowcount} posts."}

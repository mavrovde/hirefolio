from math import ceil
from typing import cast

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.post import Post
from app.models.user import User
from app.services.auth import get_current_admin_user

router = APIRouter(prefix="/tags", tags=["tags"])


class TagStat(BaseModel):
    name: str
    count: int


class PaginatedTagStats(BaseModel):
    items: list[TagStat]
    total: int
    page: int
    page_size: int
    total_pages: int


class TagRename(BaseModel):
    new_name: str


@router.get("", response_model=PaginatedTagStats)
async def list_tags(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("count", description="Field to sort by (name or count)"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    search: str = Query(None, description="Search in tag names"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """List all tags with pagination, sorting, and search."""
    # PostgreSQL specific query using unnest to count tags
    query = select(
        func.unnest(Post.tags).label("tag"),
        func.count(Post.id).label("usage_count"),
    ).group_by("tag")

    # Execute to get all tags with counts
    result = await db.execute(query)
    all_tags = [TagStat(name=row.tag, count=row.usage_count) for row in result.all()]

    # Apply search filter (client-side since tags are aggregated)
    if search:
        search_lower = search.lower()
        all_tags = [tag for tag in all_tags if search_lower in tag.name.lower()]

    # Apply sorting
    if sort_by == "name":
        all_tags.sort(key=lambda x: x.name, reverse=(sort_order == "desc"))
    else:  # sort by count (default)
        all_tags.sort(key=lambda x: x.count, reverse=(sort_order == "desc"))

    # Get total count after filtering
    total = len(all_tags)

    # Apply pagination
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_tags = all_tags[start_idx:end_idx]

    # Calculate total pages
    total_pages = ceil(total / page_size) if total > 0 else 1

    return PaginatedTagStats(
        items=paginated_tags,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.put("/{old_name}")
async def rename_tag(
    old_name: str,
    tag_data: TagRename,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
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

    return {
        "message": f"Tag renamed. Affected {cast(CursorResult, result).rowcount} posts."
    }


@router.delete("/{name}")
async def delete_tag(
    name: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
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

    return {
        "message": f"Tag removed. Affected {cast(CursorResult, result).rowcount} posts."
    }

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from math import ceil
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, field_validator, ConfigDict

from app.database import get_db
from app.models.post import Post
from app.services.embeddings import get_embedding
from app.services.auth import get_current_admin_user, get_current_user_optional
from app.models.user import User

router = APIRouter(prefix="/api/posts", tags=["posts"])


class PostCreate(BaseModel):
    title: str
    slug: str
    content: str
    summary: Optional[str] = None
    language: str = "en"
    published: bool = False
    tags: List[str] = []

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        if len(v) > 5:
            raise ValueError("Max 5 tags allowed")
        return v


class PostUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    language: Optional[str] = None
    published: Optional[bool] = None
    tags: Optional[List[str]] = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v):
        if v is not None and len(v) > 5:
            raise ValueError("Max 5 tags allowed")
        return v


class PostResponse(BaseModel):
    id: int
    title: str
    slug: str
    content: str
    summary: Optional[str]
    language: str
    published: bool
    tags: List[str]
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class PostListResponse(BaseModel):
    id: int
    title: str
    slug: str
    summary: Optional[str]
    language: str
    published: bool
    tags: List[str]
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class PaginatedPostListResponse(BaseModel):
    items: List[PostListResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class SimilarPostResponse(BaseModel):
    id: int
    title: str
    slug: str
    summary: Optional[str]
    similarity: float


class TagSuggestionRequest(BaseModel):
    title: str
    content: str


class PostDetailSuggestionRequest(BaseModel):
    content: str
    field: Optional[str] = "all"


class PostDetailSuggestionResponse(BaseModel):
    title: str
    slug: str
    summary: str
    tags: List[str]


@router.get("", response_model=PaginatedPostListResponse)
async def list_posts(
    published_only: bool = True,
    lang: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Field to sort by"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    search: Optional[str] = Query(None, description="Search in title and summary"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """List posts with pagination, sorting, and search."""
    # Restrict access to drafts
    if not published_only:
        if not current_user or not current_user.is_admin:
            published_only = True

    # Build base query
    query = select(Post)
    if published_only:
        query = query.where(Post.published.is_(True))
    if lang:
        query = query.where(Post.language == lang)
    if tag:
        query = query.where(Post.tags.contains([tag]))

    # Apply search filter
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Post.title.ilike(search_term)) | (Post.summary.ilike(search_term))
        )

    # Get total count before pagination
    from sqlalchemy import func

    count_query = select(func.count()).select_from(query.subquery())
    total_raw = await db.scalar(count_query)
    total = int(total_raw) if total_raw is not None else 0

    # Apply sorting
    if hasattr(Post, sort_by):
        order_column = getattr(Post, sort_by)
        if sort_order == "desc":
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())
    else:
        # Default to created_at desc if invalid sort field
        query = query.order_by(Post.created_at.desc())

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    posts = result.scalars().all()

    # Calculate total pages
    total_pages = ceil(total / page_size) if total > 0 else 1

    return PaginatedPostListResponse(
        items=[
            PostListResponse(
                id=p.id,
                title=p.title,
                slug=p.slug,
                summary=p.summary,
                language=p.language,
                published=p.published,
                tags=p.tags,
                created_at=p.created_at.isoformat(),
            )
            for p in posts
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{id:int}", response_model=PostResponse)
async def get_post_by_id(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get a single post by ID."""
    result = await db.execute(select(Post).where(Post.id == id))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check permissions for drafts
    if not post.published:
        if not current_user or not current_user.is_admin:
            raise HTTPException(status_code=404, detail="Post not found")

    return PostResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        summary=post.summary,
        language=post.language,
        published=post.published,
        tags=post.tags,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.get("/{slug}", response_model=PostResponse)
async def get_post(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Get a single post by slug."""
    result = await db.execute(select(Post).where(Post.slug == slug))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Check permissions for drafts
    if not post.published:
        if not current_user or not current_user.is_admin:
            raise HTTPException(status_code=404, detail="Post not found")

    return PostResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        summary=post.summary,
        language=post.language,
        published=post.published,
        tags=post.tags,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.post("", response_model=PostResponse)
async def create_post(
    post_data: PostCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Create a new post with embedding."""
    # Generate embedding from title + content
    text_for_embedding = f"{post_data.title}\n\n{post_data.content}"
    embedding = await get_embedding(text_for_embedding)

    post = Post(
        title=post_data.title,
        slug=post_data.slug,
        content=post_data.content,
        summary=post_data.summary,
        language=post_data.language,
        published=post_data.published,
        tags=post_data.tags,
        embedding=embedding,
    )

    db.add(post)
    await db.commit()
    await db.refresh(post)

    return PostResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        summary=post.summary,
        language=post.language,
        published=post.published,
        tags=post.tags,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.get("/{slug}/similar", response_model=List[SimilarPostResponse])
async def get_similar_posts(
    slug: str,
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
):
    """Find similar posts using vector similarity."""
    result = await db.execute(select(Post).where(Post.slug == slug))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    if post.embedding is None:
        return []

    # Find similar posts using cosine distance
    similar_query = (
        select(
            Post,
            Post.embedding.cosine_distance(post.embedding).label("distance"),
        )
        .where(Post.id != post.id)
        .where(Post.published.is_(True))
        .where(Post.language == post.language)
        .where(Post.embedding.isnot(None))
        .order_by("distance")
        .limit(limit)
    )

    result = await db.execute(similar_query)
    similar_posts = result.all()

    return [
        SimilarPostResponse(
            id=p.id,
            title=p.title,
            slug=p.slug,
            summary=p.summary,
            similarity=1 - distance,  # Convert distance to similarity
        )
        for p, distance in similar_posts
    ]


@router.get("/search/semantic")
async def semantic_search(
    q: str,
    lang: Optional[str] = "en",
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Search posts using semantic similarity."""
    query_embedding = await get_embedding(q)

    if query_embedding is None:
        raise HTTPException(status_code=400, detail="Embedding service unavailable")

    search_query = (
        select(
            Post,
            Post.embedding.cosine_distance(query_embedding).label("distance"),
        )
        .where(Post.published.is_(True))
        .where(Post.embedding.isnot(None))
    )

    if lang:
        search_query = search_query.where(Post.language == lang)

    search_query = search_query.order_by("distance").limit(limit)

    result = await db.execute(search_query)
    posts = result.all()

    return [
        {
            "id": p.id,
            "title": p.title,
            "slug": p.slug,
            "summary": p.summary,
            "relevance": 1 - distance,
        }
        for p, distance in posts
    ]


@router.post("/suggest-details")
async def suggest_post_details_endpoint(
    request: PostDetailSuggestionRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """Suggest title, slug, and/or summary for a post using AI."""
    from app.services.ai import suggest_field, suggest_post_details

    if not request.field or request.field == "all":
        return await suggest_post_details(request.content)

    return await suggest_field(request.content, request.field)


@router.post("/suggest-tags")
async def suggest_tags_endpoint(
    request: TagSuggestionRequest, current_user: User = Depends(get_current_admin_user)
):
    """Suggest tags for a post using AI."""
    from app.services.ai import suggest_tags

    tags = await suggest_tags(request.title, request.content)
    return {"tags": tags}


@router.put("/{id:int}", response_model=PostResponse)
async def update_post_by_id(
    id: int,
    post_data: PostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Update a post by ID."""
    result = await db.execute(select(Post).where(Post.id == id))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    update_embedding = False
    if post_data.title is not None:
        post.title = post_data.title
        update_embedding = True
    if post_data.content is not None:
        post.content = post_data.content
        update_embedding = True
    if post_data.summary is not None:
        post.summary = post_data.summary
    if post_data.language is not None:
        post.language = post_data.language
    if post_data.published is not None:
        post.published = post_data.published
    if post_data.tags is not None:
        post.tags = post_data.tags

    # Regenerate embedding if content changed
    if update_embedding:
        text_for_embedding = f"{post.title}\n\n{post.content}"
        post.embedding = await get_embedding(text_for_embedding)

    await db.commit()
    await db.refresh(post)

    return PostResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        summary=post.summary,
        language=post.language,
        published=post.published,
        tags=post.tags,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.delete("/{id:int}")
async def delete_post_by_id(
    id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    """Delete a post by ID."""
    result = await db.execute(select(Post).where(Post.id == id))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    await db.delete(post)
    await db.commit()

    return {"message": "Post deleted"}

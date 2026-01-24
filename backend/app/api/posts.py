from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, field_validator

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
    summary: str | None = None
    language: str = "en"
    published: bool = False
    tags: list[str] = []

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        if len(v) > 5:
            raise ValueError('Max 5 tags allowed')
        return v


class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    language: str | None = None
    published: bool | None = None
    tags: list[str] | None = None

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        if v is not None and len(v) > 5:
            raise ValueError('Max 5 tags allowed')
        return v


class PostResponse(BaseModel):
    id: int
    title: str
    slug: str
    content: str
    summary: str | None
    language: str
    published: bool
    tags: list[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    id: int
    title: str
    slug: str
    summary: str | None
    language: str
    published: bool
    tags: list[str]
    created_at: str

    class Config:
        from_attributes = True


class SimilarPostResponse(BaseModel):
    id: int
    title: str
    slug: str
    summary: str | None
    similarity: float


class TagSuggestionRequest(BaseModel):
    title: str
    content: str


@router.get("", response_model=list[PostListResponse])
async def list_posts(
    published_only: bool = True,
    lang: str | None = None,
    tag: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """List all posts."""
    # Restrict access to drafts
    if not published_only:
        if not current_user or not current_user.is_admin:
            # Force published_only if not admin
            published_only = True

    query = select(Post).order_by(Post.created_at.desc())
    if published_only:
        query = query.where(Post.published == True)
    if lang:
        query = query.where(Post.language == lang)
    if tag:
        query = query.where(Post.tags.contains([tag]))

    result = await db.execute(query)
    posts = result.scalars().all()
    return [
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
    ]


@router.get("/{slug}", response_model=PostResponse)
async def get_post(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
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
    current_user: User = Depends(get_current_admin_user)
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


@router.put("/{slug}", response_model=PostResponse)
async def update_post(
    slug: str,
    post_data: PostUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Update a post."""
    result = await db.execute(select(Post).where(Post.slug == slug))
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


@router.delete("/{slug}")
async def delete_post(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """Delete a post."""
    result = await db.execute(select(Post).where(Post.slug == slug))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    await db.delete(post)
    await db.commit()

    return {"message": "Post deleted"}


@router.get("/{slug}/similar", response_model=list[SimilarPostResponse])
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
        .where(Post.published == True)
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
    lang: str | None = "en",
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
        .where(Post.published == True)
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


@router.post("/suggest-tags")
async def suggest_tags_endpoint(
    request: TagSuggestionRequest,
    current_user: User = Depends(get_current_admin_user)
):
    """Suggest tags for a post using AI."""
    from app.services.ai import suggest_tags
    tags = await suggest_tags(request.title, request.content)
    return {"tags": tags}

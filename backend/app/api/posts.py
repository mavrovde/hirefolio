from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.models.post import Post
from app.services.embeddings import get_embedding

router = APIRouter(prefix="/api/posts", tags=["posts"])


class PostCreate(BaseModel):
    title: str
    slug: str
    content: str
    summary: str | None = None
    published: bool = False


class PostUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    published: bool | None = None


class PostResponse(BaseModel):
    id: int
    title: str
    slug: str
    content: str
    summary: str | None
    published: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    id: int
    title: str
    slug: str
    summary: str | None
    published: bool
    created_at: str

    class Config:
        from_attributes = True


class SimilarPostResponse(BaseModel):
    id: int
    title: str
    slug: str
    summary: str | None
    similarity: float


@router.get("", response_model=list[PostListResponse])
async def list_posts(
    published_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """List all posts."""
    query = select(Post).order_by(Post.created_at.desc())
    if published_only:
        query = query.where(Post.published == True)

    result = await db.execute(query)
    posts = result.scalars().all()
    return [
        PostListResponse(
            id=p.id,
            title=p.title,
            slug=p.slug,
            summary=p.summary,
            published=p.published,
            created_at=p.created_at.isoformat(),
        )
        for p in posts
    ]


@router.get("/{slug}", response_model=PostResponse)
async def get_post(slug: str, db: AsyncSession = Depends(get_db)):
    """Get a single post by slug."""
    result = await db.execute(select(Post).where(Post.slug == slug))
    post = result.scalar_one_or_none()

    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    return PostResponse(
        id=post.id,
        title=post.title,
        slug=post.slug,
        content=post.content,
        summary=post.summary,
        published=post.published,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.post("", response_model=PostResponse)
async def create_post(post_data: PostCreate, db: AsyncSession = Depends(get_db)):
    """Create a new post with embedding."""
    # Generate embedding from title + content
    text_for_embedding = f"{post_data.title}\n\n{post_data.content}"
    embedding = await get_embedding(text_for_embedding)

    post = Post(
        title=post_data.title,
        slug=post_data.slug,
        content=post_data.content,
        summary=post_data.summary,
        published=post_data.published,
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
        published=post.published,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.put("/{slug}", response_model=PostResponse)
async def update_post(
    slug: str,
    post_data: PostUpdate,
    db: AsyncSession = Depends(get_db),
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
    if post_data.published is not None:
        post.published = post_data.published

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
        published=post.published,
        created_at=post.created_at.isoformat(),
        updated_at=post.updated_at.isoformat(),
    )


@router.delete("/{slug}")
async def delete_post(slug: str, db: AsyncSession = Depends(get_db)):
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
        .order_by("distance")
        .limit(limit)
    )

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
